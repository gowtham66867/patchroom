import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from .core import ROOT, export, handoff, information, initialize, load, propose, recover, reproduce
from .store import Store


def doctor(credentials_file=None):
    result = {'python': sys.version.split()[0], 'python_supported': sys.version_info >= (3, 9),
              'switch_console_installed': any(p.exists() for p in [
                  Path('/Applications/Switch Console.app'), Path.home() / 'Applications/Switch Console.app']),
              'live_workflow_status': 'see docs/VALIDATION.md; health alone does not demonstrate a workflow'}
    if shutil.which('docker'):
        try:
            probe = subprocess.run(['docker', 'info', '--format', '{{.ServerVersion}}'],
                                   text=True, capture_output=True, timeout=10)
            result['docker'] = probe.stdout.strip() if probe.returncode == 0 else 'daemon unavailable'
        except subprocess.TimeoutExpired:
            result['docker'] = 'probe timed out'
    else:
        result['docker'] = 'not installed'
    try:
        from .switch_client import SwitchClient
        client = SwitchClient(credentials_file=credentials_file)
        result['switch_health'] = client.health()
        result['switch_operations'] = sorted(client.discover())
    except (ValueError, OSError) as error:
        result['switch_connection'] = str(error)
    return result


def main():
    parser = argparse.ArgumentParser(description='PatchRoom: report → evidence → patch → human review')
    parser.add_argument('--work', type=Path, default=ROOT / 'work')
    parser.add_argument('--switch-credentials', type=Path, help='read existing local Switch agent credentials without copying or printing them')
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='create a local case, without authenticated review identity')
    init.add_argument('case_id')
    report = init.add_mutually_exclusive_group(required=True)
    report.add_argument('--report')
    report.add_argument('--report-file', type=Path)
    init.add_argument('--adapter', type=Path)
    init.add_argument('--expected', default='')
    init.add_argument('--observed', default='')
    for name in ['reproduce', 'status', 'timeline', 'export', 'recover', 'prepare-pr']:
        sub = commands.add_parser(name)
        sub.add_argument('case_id')
        if name == 'reproduce':
            sub.add_argument('--event-id')
    candidate = commands.add_parser('propose', help='preserve and independently verify a candidate')
    candidate.add_argument('case_id')
    source = candidate.add_mutually_exclusive_group(required=True)
    source.add_argument('--source', type=Path)
    source.add_argument('--candidate-dir', type=Path)
    candidate.add_argument('--event-id')
    candidate.add_argument('--explanation', default='')
    info = commands.add_parser('information')
    info.add_argument('case_id')
    info_args = info.add_mutually_exclusive_group(required=True)
    info_args.add_argument('--question', action='append')
    info_args.add_argument('--response')
    transfer = commands.add_parser('handoff', help='prepare a deduplicated handoff for posting through Switch')
    transfer.add_argument('case_id')
    transfer.add_argument('--event-id', required=True)
    transfer.add_argument('--to', choices=['triager', 'engineer', 'verifier', 'human'], required=True)
    transfer.add_argument('--action', required=True)
    intake = commands.add_parser('intake-switch', help='fetch the original human report from Switch')
    intake.add_argument('case_id')
    intake.add_argument('--room-id', required=True)
    intake.add_argument('--message-id', required=True)
    intake.add_argument('--adapter', type=Path)
    review = commands.add_parser('review-switch', help='record a server-identified human review')
    review.add_argument('case_id')
    review.add_argument('--proposal-id', required=True)
    review.add_argument('--message-id', required=True)
    demo = commands.add_parser('demo', help='local scripted replay; no live agents or human approval')
    demo.add_argument('--case-id', default='checkout-demo')
    commands.add_parser('doctor')
    args = parser.parse_args()
    try:
        result = None
        if args.command == 'init':
            text = args.report if args.report is not None else args.report_file.read_text()
            result = str(initialize(args.work, args.case_id, text, args.adapter, args.expected, args.observed))
        elif args.command == 'status':
            _, state = load(args.work, args.case_id)
            result = {k: v for k, v in state.items() if k not in ['baseline_source', 'contract', 'adapter']}
            result['adapter'] = {k: v for k, v in state['adapter'].items() if k not in ['sources', 'tests']}
            result['proposals'] = [{k: p[k] for k in ['id', 'status', 'source_sha256', 'created_at']}
                                   for p in Store(args.work).proposals(args.case_id)]
        elif args.command == 'reproduce':
            result = reproduce(args.work, args.case_id, args.event_id)
            print(result['output'])
            status = load(args.work, args.case_id)[1]['status']
            print(status.upper())
            return 1 if status == 'reproduction_error' else 0
        elif args.command == 'propose':
            result = propose(args.work, args.case_id, args.source, args.candidate_dir,
                             args.event_id, args.explanation)
            print(json.dumps(result, indent=2))
            return 0 if result['passed'] else 1
        elif args.command == 'timeline':
            result = Store(args.work).timeline(args.case_id)
        elif args.command == 'export':
            result = str(export(args.work, args.case_id))
        elif args.command == 'recover':
            result = recover(args.work, args.case_id)['status']
        elif args.command == 'information':
            result = information(args.work, args.case_id, args.question, args.response)['status']
        elif args.command == 'handoff':
            result = handoff(args.work, args.case_id, args.event_id, args.to, args.action)
        elif args.command == 'prepare-pr':
            from .packaging import prepare_pr
            result = prepare_pr(args.work, args.case_id)
        elif args.command == 'intake-switch':
            from .switch_client import SwitchClient, intake
            result = str(intake(args.work, args.case_id, SwitchClient(credentials_file=args.switch_credentials), args.room_id,
                                args.message_id, args.adapter))
        elif args.command == 'review-switch':
            from .switch_client import SwitchClient, review
            result = review(args.work, args.case_id, args.proposal_id, SwitchClient(credentials_file=args.switch_credentials), args.message_id)
        elif args.command == 'doctor':
            result = doctor(args.switch_credentials)
        elif args.command == 'demo':
            print('LOCAL SCRIPTED REPLAY — no live agents, Switch connection or human approval')
            directory = initialize(args.work, args.case_id,
                                   'An order of exactly $100 is incorrectly charged $5 shipping.')
            baseline = reproduce(args.work, args.case_id)
            source = (directory / 'checkout.py').read_text().replace(
                'amount > Decimal("100.00")', 'amount >= Decimal("100.00")')
            candidate = directory / 'proposed.py'
            candidate.write_text(source)
            verified = propose(args.work, args.case_id, candidate,
                               explanation='Include the $100 boundary in the free-shipping condition.')
            print('Baseline:', 'FAIL' if not baseline['passed'] else 'PASS')
            print('Candidate:', 'PASS' if verified['passed'] else 'FAIL')
            print('Review:', directory / 'review.md')
            return 0 if not baseline['passed'] and verified['passed'] else 1
        print(json.dumps(result, indent=2) if not isinstance(result, str) else result)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(2, 'patchroom: ' + str(error) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
