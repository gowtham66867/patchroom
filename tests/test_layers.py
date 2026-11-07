import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from patchroom.adapters import FIXTURE, ROOT, snapshot
from patchroom.core import (export, handoff, information, initialize, load,
                            propose, recover, reproduce)
from patchroom.packaging import prepare_pr
from patchroom.runner import execute
from patchroom.store import Store, TRANSITIONS
from patchroom.switch_client import SwitchClient, intake, review


class FakeSwitch:
    base = 'https://switch.example'

    def __init__(self):
        self.messages = {}

    def message(self, room_id, message_id):
        message = dict(self.messages[message_id])
        if message['room_id'] != room_id:
            raise ValueError('wrong room')
        return message


class LayeredWorkflow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.client = FakeSwitch()
        self.client.messages['report'] = dict(id='report', room_id='room-1', sender='human-1',
            sender_kind='user', body='Exactly $100 should have free shipping', timestamp=1)
        intake(self.work, 'case-1', self.client, 'room-1', 'report')

    def fixed(self, suffix=''):
        source = (FIXTURE / 'checkout.py').read_text().replace(
            'amount > Decimal("100.00")', 'amount >= Decimal("100.00")')
        path = self.work / 'fix.py'
        path.write_text(source + suffix)
        return path

    def verified(self):
        reproduce(self.work, 'case-1')
        return propose(self.work, 'case-1', self.fixed())

    def decision(self, result, sender_kind='user', sender='human-1', message_id='decision', body=None):
        self.client.messages[message_id] = dict(id=message_id, room_id='room-1', sender=sender,
            sender_kind=sender_kind,
            body=body or 'accept case-1 ' + result['proposal_id'] + ' ' + result['source_sha256'],
            timestamp=datetime.now(timezone.utc).timestamp() * 1000 + 1)
        return review(self.work, 'case-1', result['proposal_id'], self.client, message_id)

    def test_state_transitions_reject_invalid_transition(self):
        store = Store(self.work)
        with self.assertRaisesRegex(ValueError, 'invalid transition'), store.transaction() as db:
            state = store.get('case-1', db)
            store.transition(db, state, 'accepted', 'invalid')
        self.assertEqual(store.get('case-1')['status'], 'reported')
        self.assertNotIn('accepted', TRANSITIONS['reported'])

    def test_needs_information_and_response(self):
        information(self.work, 'case-1', questions=['What amount?'])
        self.assertEqual(load(self.work, 'case-1')[1]['status'], 'needs_information')
        information(self.work, 'case-1', response='$100')
        self.assertEqual(load(self.work, 'case-1')[1]['status'], 'reported')

    def test_idempotent_reproduction_survives_new_store(self):
        first = reproduce(self.work, 'case-1', event_id='room:message:repro')
        count = len(Store(self.work).timeline('case-1'))
        with patch('patchroom.core.execute', side_effect=AssertionError('must not execute twice')):
            second = reproduce(self.work, 'case-1', event_id='room:message:repro')
        self.assertEqual(first, second)
        self.assertEqual(count, len(Store(self.work).timeline('case-1')))

    def test_duplicate_proposal_is_not_executed_again(self):
        reproduce(self.work, 'case-1')
        source = self.fixed()
        first = propose(self.work, 'case-1', source, event_id='verify-1')
        with patch('patchroom.core.execute', side_effect=AssertionError('duplicate execution')):
            second = propose(self.work, 'case-1', source, event_id='verify-1')
        self.assertEqual(first, second)
        self.assertEqual(len(Store(self.work).proposals('case-1')), 1)

    def test_failed_attempts_are_preserved_and_bounded(self):
        reproduce(self.work, 'case-1')
        for attempt in range(3):
            path = self.fixed()
            path.write_text(path.read_text().replace('Decimal("100.00")', 'Decimal("99.00")') + '\n' * attempt)
            self.assertFalse(propose(self.work, 'case-1', path)['passed'])
        proposals = Store(self.work).proposals('case-1')
        self.assertEqual([p['id'] for p in proposals], ['p001', 'p002', 'p003'])
        self.assertTrue(all((self.work / 'case-1/proposals' / p['id'] / 'tests.txt').exists() for p in proposals))
        with self.assertRaisesRegex(ValueError, 'retry limit'):
            propose(self.work, 'case-1', self.fixed())

    def test_environment_error_is_not_reproduced(self):
        result = dict(passed=False, completed=False, summary=None, classification='environment_error',
                      output='missing interpreter', duration_seconds=0)
        with patch('patchroom.core.execute', return_value=result):
            reproduce(self.work, 'case-1')
        self.assertEqual(load(self.work, 'case-1')[1]['status'], 'reproduction_error')
        with self.assertRaisesRegex(ValueError, 'reproduce'):
            propose(self.work, 'case-1', self.fixed())

    def test_approval_uses_server_human_and_exact_hash(self):
        result = self.verified()
        self.decision(result)
        self.assertEqual(load(self.work, 'case-1')[1]['status'], 'accepted')
        # Duplicate server message is idempotent.
        self.decision(result)
        self.assertEqual(sum(e['kind'] == 'human_review' for e in Store(self.work).timeline('case-1')), 1)

    def test_agent_cannot_approve(self):
        result = self.verified()
        with self.assertRaisesRegex(ValueError, 'sender_kind=user'):
            self.decision(result, sender_kind='agent')
        self.assertEqual(load(self.work, 'case-1')[1]['status'], 'awaiting_human_review')

    def test_unknown_sender_kind_and_other_human_cannot_approve(self):
        result = self.verified()
        with self.assertRaisesRegex(ValueError, 'sender_kind=user'):
            self.decision(result, sender_kind=None)
        with self.assertRaisesRegex(ValueError, 'original human'):
            self.decision(result, sender='human-2')

    def test_quoted_approval_cannot_approve(self):
        result = self.verified()
        with self.assertRaisesRegex(ValueError, 'exact message'):
            self.decision(result, body='> accept case-1 p001 ' + result['source_sha256'])

    def test_wrong_hash_and_old_timestamp_cannot_approve(self):
        result = self.verified()
        with self.assertRaisesRegex(ValueError, 'hash'):
            self.decision(result, body='accept case-1 p001 ' + '0' * 64)
        self.client.messages['old'] = dict(self.client.messages['decision'], timestamp=1,
            body='accept case-1 p001 ' + result['source_sha256'])
        with self.assertRaisesRegex(ValueError, 'predates'):
            review(self.work, 'case-1', 'p001', self.client, 'old')

    def test_new_candidate_invalidates_approval(self):
        result = self.verified()
        self.decision(result)
        replacement = propose(self.work, 'case-1', self.fixed('\n# second proposal\n'))
        state = load(self.work, 'case-1')[1]
        self.assertEqual(state['status'], 'awaiting_human_review')
        self.assertIsNone(state['decision'])
        self.assertEqual(replacement['proposal_id'], 'p002')
        with self.assertRaisesRegex(ValueError, 'current proposal'):
            review(self.work, 'case-1', 'p001', self.client, 'decision')

    def test_modified_exported_candidate_is_not_approved(self):
        result = self.verified()
        (self.work / 'case-1/proposals/p001/source/checkout.py').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'changed after testing'):
            self.decision(result)
        export(self.work, 'case-1')
        self.decision(result)

    def test_local_case_cannot_claim_switch_approval(self):
        initialize(self.work, 'local-case', 'local report')
        with self.assertRaisesRegex(ValueError, 'authenticated Switch intake'):
            review(self.work, 'local-case', 'p001', self.client, 'decision')

    def test_handoff_deduplicates_and_keeps_context(self):
        first = handoff(self.work, 'case-1', 'event-1', 'engineer', 'Investigate')
        second = handoff(self.work, 'case-1', 'event-1', 'engineer', 'Investigate')
        self.assertEqual(first, second)
        self.assertIn('source_sha256', first)
        self.assertEqual(sum(e['kind'] == 'handoff_prepared' for e in Store(self.work).timeline('case-1')), 1)

    def test_recovery_marks_orphaned_verification_interrupted(self):
        reproduce(self.work, 'case-1')
        with patch('patchroom.core.execute', side_effect=RuntimeError('simulated worker crash')):
            with self.assertRaises(RuntimeError):
                propose(self.work, 'case-1', self.fixed(), event_id='crashed-worker')
        with Store(self.work).transaction() as db:
            db.execute("UPDATE requests SET owner_pid=99999999 WHERE status='active'")
        recover(self.work, 'case-1')
        self.assertEqual(Store(self.work).proposals('case-1')[0]['status'], 'interrupted')
        self.assertEqual(load(self.work, 'case-1')[1]['status'], 'patching')
        self.assertTrue(propose(self.work, 'case-1', self.fixed(), event_id='replacement-worker')['passed'])

    def test_recovery_refuses_live_worker(self):
        with patch('patchroom.core.execute', side_effect=RuntimeError('interrupted')):
            with self.assertRaises(RuntimeError):
                reproduce(self.work, 'case-1')
        with self.assertRaisesRegex(ValueError, 'still running'):
            recover(self.work, 'case-1')

    def test_pr_materials_are_local_and_complete(self):
        self.verified()
        result = prepare_pr(self.work, 'case-1')
        self.assertFalse(result['published'])
        self.assertIn('Contract SHA-256', Path(result['body']).read_text())

    def test_local_python_adapter_works_in_separate_copies(self):
        config = ROOT / 'examples/local-python/adapter.json'
        case = initialize(self.work, 'tax', 'Tax rounding is wrong at a half cent.', config)
        self.assertFalse(reproduce(self.work, 'tax')['passed'])
        source = (case / 'tax.py').read_text().replace('from decimal import Decimal',
            'from decimal import Decimal, ROUND_HALF_UP').replace("quantize(Decimal('0.01'))",
            "quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)")
        path = self.work / 'tax_fixed.py'
        path.write_text(source)
        self.assertTrue(propose(self.work, 'tax', path)['passed'])
        self.assertNotIn('ROUND_HALF_UP', (ROOT / 'examples/local-python/tax.py').read_text())


class RunnerAndAdapter(unittest.TestCase):
    def setUp(self):
        self.config = dict(test_pattern='test*.py', min_tests=1, timeout_seconds=2, output_limit=1024)

    def test_syntax_error_is_environment_failure(self):
        result = execute({'test_broken.py': 'this is invalid python !'}, self.config)
        self.assertEqual(result['classification'], 'environment_error')

    def test_skipped_tests_are_insufficient_evidence(self):
        result = execute({'test_skip.py': 'import unittest\nclass T(unittest.TestCase):\n @unittest.skip("skip")\n def test_a(self): pass\n'}, self.config)
        self.assertEqual(result['classification'], 'insufficient_evidence')

    def test_timeout_and_output_limit(self):
        slow = execute({'test_slow.py': 'import time\ntime.sleep(20)\n'}, dict(self.config, timeout_seconds=0.2))
        self.assertEqual(slow['reason'], 'timeout')
        noisy = execute({'test_noisy.py': 'print("x" * 100000)\n'}, self.config)
        self.assertEqual(noisy['reason'], 'output_limit')
        self.assertLessEqual(len(noisy['output'].encode()), 1024)

    def test_config_rejects_shell_command_override_and_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'adapter.json'
            path.write_text(json.dumps({'test_command': 'rm -rf anything'}))
            with self.assertRaisesRegex(ValueError, 'unknown adapter fields'):
                snapshot(path)
            path.write_text(json.dumps(dict(name='invalid', root='.', source_files=['../escape.py'],
                test_files=['test.py'], reproduction_test='test.T.test_a')))
            with self.assertRaisesRegex(ValueError, 'relative .py paths'):
                snapshot(path)

    def test_remote_plaintext_and_credential_urls_rejected(self):
        for url in ['http://remote.example', 'https://user:password@remote.example']:
            with self.assertRaises(ValueError):
                SwitchClient(url, 'agent', 'secret')


if __name__ == '__main__':
    unittest.main()
