"""Case workflow and immutable-attempt evidence, with transactional SQLite state."""
import difflib
import json
import os
import re
import uuid
from pathlib import Path

from .adapters import ROOT, FIXTURE, candidate_files, digest, manifest, snapshot
from .runner import execute
from .store import Store, now


def case_path(work, case_id):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', case_id):
        raise ValueError('case ID must use 1–64 letters, numbers, underscores or hyphens')
    return Path(work).resolve() / case_id


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.replace(path)


def initialize(work, case_id, report, config_path=None, expected='', observed='', origin=None):
    if not report.strip():
        raise ValueError('a bug report is required')
    directory = case_path(work, case_id)
    adapter = snapshot(config_path)
    state = dict(id=case_id, report=report, status='reported', created_at=now(),
                 expected=expected, observed=observed, adapter=adapter,
                 origin=origin, max_attempts=3, reproduction_attempts=0,
                 current_proposal=None, decision=None, outstanding_questions=[])
    if adapter['config']['name'] == 'checkout':
        state.update(baseline_source=adapter['sources']['checkout.py'],
                     contract=adapter['tests']['test_checkout.py'])
    state.update(baseline_sha256=adapter['source_sha256'], contract_sha256=adapter['contract_sha256'])
    store = Store(work)
    with store.transaction() as db:
        if db.execute('SELECT 1 FROM cases WHERE id=?', (case_id,)).fetchone() or directory.exists():
            raise FileExistsError('case already exists: ' + case_id)
        directory.mkdir(parents=True)
        db.execute('INSERT INTO cases(id,data) VALUES(?,?)', (case_id, json.dumps(state)))
        store.event(db, case_id, 'case_created', dict(adapter=adapter['config']['name'], origin=origin))
    for name, content in dict(adapter['sources'], **adapter['tests']).items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    export(work, case_id)
    return directory


def load(work, case_id):
    directory = case_path(work, case_id)
    return directory, Store(work).get(case_id)


def _request(db, store, case_id, operation, event_id, fingerprint):
    key = operation + ':' + (event_id or uuid.uuid4().hex)
    row = db.execute('SELECT * FROM requests WHERE key=?', (key,)).fetchone()
    if row:
        if row['case_id'] != case_id or row['fingerprint'] != fingerprint:
            raise ValueError('event ID already belongs to a different request')
        if row['status'] == 'complete':
            return key, json.loads(row['result'])
        raise ValueError('request is active or interrupted; recover it and use a new event ID')
    db.execute('INSERT INTO requests VALUES(?,?,?,?,?,?,?,NULL)',
               (key, case_id, operation, fingerprint, 'active', os.getpid(), now()))
    return key, None


def _finish(db, key, result):
    db.execute('UPDATE requests SET status=?,result=? WHERE key=?',
               ('complete', json.dumps(result), key))


def _result(files, state):
    config = state['adapter']['config']
    result = execute(dict(files, **state['adapter']['tests']), config)
    result.update(source_sha256=manifest(files), contract_sha256=state['contract_sha256'])
    return result


def _baseline_status(result, state):
    summary = result.get('summary') or {}
    if result['passed']:
        return 'not_reproduced'
    if result['classification'] != 'failed':
        return 'reproduction_error'
    if state['adapter']['config']['reproduction_test'] in summary.get('failures', []):
        return 'reproduced'
    return 'not_reproduced'


def reproduce(work, case_id, event_id=None):
    store = Store(work)
    with store.transaction() as db:
        state = store.get(case_id, db)
        key, cached = _request(db, store, case_id, 'reproduce', event_id, state['baseline_sha256'])
        if cached is not None:
            return cached
        if 'candidate' in state:
            raise ValueError('this case already has a verified candidate; create a new case to rerun')
        if state['reproduction_attempts'] >= state['max_attempts']:
            raise ValueError('reproduction retry limit reached; human investigation required')
        store.transition(db, state, 'reproducing', 'baseline execution started')
        state['reproduction_attempts'] += 1
        store.put(db, state)
    result = _result(state['adapter']['sources'], state)
    with store.transaction() as db:
        state = store.get(case_id, db)
        state['baseline'] = result
        state['baseline_history'] = state.get('baseline_history', []) + [result]
        store.transition(db, state, _baseline_status(result, state), 'baseline execution completed')
        store.event(db, case_id, 'baseline_completed', dict(classification=result['classification'],
                                                          duration_seconds=result['duration_seconds']))
        store.put(db, state)
        _finish(db, key, result)
    export(work, case_id)
    return result


def _diff(old, new):
    return ''.join(''.join(difflib.unified_diff(old[name].splitlines(True), new[name].splitlines(True),
                                             fromfile='a/' + name, tofile='b/' + name))
                   for name in sorted(old) if old[name] != new[name])


def propose(work, case_id, source_path=None, candidate_dir=None, event_id=None, explanation=''):
    store = Store(work)
    state = store.get(case_id)
    sources = candidate_files(state, source_path, candidate_dir)
    fingerprint = manifest(sources)
    with store.transaction() as db:
        state = store.get(case_id, db)
        key, cached = _request(db, store, case_id, 'propose', event_id, fingerprint)
        if cached is not None:
            return cached
        if fingerprint == state['baseline_sha256']:
            raise ValueError('candidate is unchanged from the failing baseline')
        if 'baseline' not in state or _baseline_status(state['baseline'], state) != 'reproduced':
            raise ValueError('reproduce a failing baseline before proposing a patch')
        proposals = store.proposals(case_id, db)
        if len(proposals) >= state['max_attempts']:
            raise ValueError('proposal retry limit reached; human investigation required')
        if state['status'] != 'patching':
            store.transition(db, state, 'patching', 'new candidate; prior approval invalidated')
        if state.get('decision'):
            store.event(db, case_id, 'approval_invalidated', state['decision'])
        state['decision'] = None
        state.pop('candidate', None)
        proposal_id = 'p' + str(len(proposals) + 1).zfill(3)
        proposal = dict(id=proposal_id, created_at=now(), sources=sources,
                        source_sha256=fingerprint, contract_sha256=state['contract_sha256'],
                        baseline_revision=state['adapter']['git_revision'],
                        explanation=explanation or 'Review the candidate diff; no cause explanation supplied.',
                        changed_files=[n for n in sources if sources[n] != state['adapter']['sources'][n]],
                        patch=_diff(state['adapter']['sources'], sources), status='verifying')
        state['current_proposal'] = proposal_id
        store.transition(db, state, 'verifying', 'independent verification started')
        store.save_proposal(db, case_id, proposal)
        store.put(db, state)
    baseline = _result(state['adapter']['sources'], state)
    result = _result(sources, state)
    expected_ids = set((baseline.get('summary') or {}).get('executed', []))
    actual_ids = set((result.get('summary') or {}).get('executed', []))
    if _baseline_status(baseline, state) != 'reproduced':
        result.update(passed=False, classification='insufficient_evidence', reason='baseline_no_longer_reproduces')
    elif expected_ids != actual_ids:
        result.update(passed=False, classification='insufficient_evidence', reason='test_inventory_changed')
    result['proposal_id'] = proposal_id
    with store.transaction() as db:
        state = store.get(case_id, db)
        proposal.update(verification=result, baseline_recheck=baseline,
                        status='verified' if result['passed'] else 'failed')
        store.save_proposal(db, case_id, proposal)
        if result['passed']:
            state['candidate'] = result
        store.transition(db, state, 'awaiting_human_review' if result['passed'] else 'patching',
                         'candidate verification completed')
        store.event(db, case_id, 'proposal_completed', dict(proposal_id=proposal_id,
                    source_sha256=fingerprint, classification=result['classification']))
        store.put(db, state)
        _finish(db, key, result)
    export(work, case_id)
    return result


def information(work, case_id, questions=None, response=None):
    store = Store(work)
    with store.transaction() as db:
        state = store.get(case_id, db)
        if questions:
            store.transition(db, state, 'needs_information', 'missing reproduction information')
            state['outstanding_questions'] = questions
        elif response:
            store.transition(db, state, 'reported', 'additional information received')
            state['additional_information'] = state.get('additional_information', []) + [response]
            state['outstanding_questions'] = []
        else:
            raise ValueError('provide questions or a response')
        store.put(db, state)
    export(work, case_id)
    return state


def recover(work, case_id):
    store = Store(work)
    with store.transaction() as db:
        state = store.get(case_id, db)
        rows = db.execute('SELECT * FROM requests WHERE case_id=? AND status=?',
                          (case_id, 'active')).fetchall()
        for row in rows:
            try:
                os.kill(row['owner_pid'], 0)
            except ProcessLookupError:
                pass
            else:
                raise ValueError('request owner is still running; refusing to recover active work')
        if not rows:
            return state
        for row in rows:
            db.execute('UPDATE requests SET status=? WHERE key=?', ('interrupted', row['key']))
        if state['status'] == 'reproducing':
            store.transition(db, state, 'reproduction_error', 'interrupted baseline recovered')
        elif state['status'] == 'verifying':
            for proposal in store.proposals(case_id, db):
                if proposal['status'] == 'verifying':
                    proposal['status'] = 'interrupted'
                    store.save_proposal(db, case_id, proposal)
            store.transition(db, state, 'patching', 'interrupted proposal recovered')
        store.event(db, case_id, 'work_recovered', {'requests': [r['key'] for r in rows]})
        store.put(db, state)
    export(work, case_id)
    return state


def handoff(work, case_id, event_id, recipient, action):
    if not event_id.strip() or not action.strip():
        raise ValueError('handoff needs an event ID and action')
    if recipient not in {'triager', 'engineer', 'verifier', 'human'}:
        raise ValueError('unknown handoff recipient')
    store = Store(work)
    with store.transaction() as db:
        state = store.get(case_id, db)
        payload = dict(case_id=case_id, recipient=recipient, action=action,
                       proposal_id=state['current_proposal'], baseline_revision=state['adapter']['git_revision'],
                       source_sha256=(state.get('candidate') or {}).get('source_sha256', state['baseline_sha256']),
                       evidence_path=str(case_path(work, case_id)), status=state['status'])
        row = db.execute('SELECT data FROM handoffs WHERE case_id=? AND event_id=?', (case_id, event_id)).fetchone()
        if row:
            previous = json.loads(row['data'])
            if previous['recipient'] != recipient or previous['action'] != action:
                raise ValueError('handoff event ID already belongs to a different action')
            return previous
        db.execute('INSERT INTO handoffs VALUES(?,?,?)', (case_id, event_id, json.dumps(payload)))
        store.event(db, case_id, 'handoff_prepared', dict(event_id=event_id, **payload))
    return payload


def export(work, case_id):
    store = Store(work)
    with store.transaction() as db:
        state = store.get(case_id, db)
        proposals = store.proposals(case_id, db)
        timeline = [dict(seq=row['seq'], at=row['at'], kind=row['kind'], data=json.loads(row['data']))
                    for row in db.execute('SELECT * FROM events WHERE case_id=? ORDER BY seq', (case_id,))]
        return _render_export(work, case_id, state, proposals, timeline)


def _render_export(work, case_id, state, proposals, timeline):
    directory = case_path(work, case_id)
    directory.mkdir(parents=True, exist_ok=True)
    write_json(directory / 'case.json', state)
    write_json(directory / 'timeline.json', timeline)
    (directory / 'events.jsonl').write_text(''.join(json.dumps(dict(case_id=case_id, **event)) + '\n' for event in timeline))
    write_json(directory / 'export.json', dict(case=state, proposals=proposals, timeline=timeline))
    if 'baseline' in state:
        (directory / 'baseline.txt').write_text(state['baseline']['output'])
    for proposal in proposals:
        folder = directory / 'proposals' / proposal['id']
        folder.mkdir(parents=True, exist_ok=True)
        write_json(folder / 'proposal.json', proposal)
        (folder / 'candidate.patch').write_text(proposal['patch'])
        for name, content in proposal['sources'].items():
            path = folder / 'source' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        if 'verification' in proposal:
            (folder / 'tests.txt').write_text(proposal['verification']['output'])
            (folder / 'baseline.txt').write_text(proposal['baseline_recheck']['output'])
    # Only a currently verified proposal gets a current review packet.
    current = next((p for p in proposals if p['id'] == state['current_proposal']), None)
    for name in ['review.md', 'candidate.py', 'candidate.patch', 'pr-body.md', 'pr-title.txt']:
        (directory / name).unlink(missing_ok=True)
    if current and current['status'] == 'verified':
        result = current['verification']
        review = ('# PatchRoom review: ' + case_id + ' / ' + current['id'] + '\n\n'
                  + 'Status: ' + state['status'] + '\n\nReport (untrusted input):\n\n' + state['report']
                  + '\n\nExplanation: ' + current['explanation']
                  + '\n\nBaseline: assertion failure reproduced. Candidate: configured checks pass.\n\n'
                  + 'Source SHA-256: `' + current['source_sha256'] + '`\n\n'
                  + 'Contract SHA-256: `' + current['contract_sha256'] + '`\n\n'
                  + '```diff\n' + current['patch'] + '```\n\n'
                  + '## Verification output\n\n```text\n' + result['output'] + '```\n\n'
                  + 'Tests establish configured behavior only. No merge or deployment is performed.\n'
                  + 'Human review must refer to this proposal and full source hash.\n')
        (directory / 'review.md').write_text(review)
        (directory / 'candidate.patch').write_text(current['patch'])
        if len(current['sources']) == 1:
            (directory / 'candidate.py').write_text(next(iter(current['sources'].values())))
    return directory / 'export.json'


def run_contract(source, contract):
    """Compatibility helper for the bundled fixture."""
    result = execute({'checkout.py': source, 'test_checkout.py': contract},
                     dict(test_pattern='test*.py', min_tests=6, timeout_seconds=15, output_limit=131072))
    result.update(source_sha256=digest(source), contract_sha256=digest(contract))
    return result
