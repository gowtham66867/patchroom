"""Small HTTP integration; Console owns agent event transport and model sessions.

Wire shapes are checked against sandbox-quantum/switch at the pinned commit.
Unknown message identity schemas fail closed for review decisions.
"""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

from .core import case_path, export, initialize
from .store import Store, now


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Switch redirects are refused to avoid forwarding credentials')


class SwitchClient:
    def __init__(self, base_url=None, agent_id=None, api_key=None, credentials_file=None):
        credentials = {}
        selected = credentials_file or os.environ.get('PATCHROOM_SWITCH_CREDENTIALS_FILE')
        if selected:
            path = Path(selected).expanduser()
            if path.is_symlink() or not path.is_file():
                raise ValueError('Switch credentials must be a regular local file')
            if path.stat().st_size > 65536:
                raise ValueError('Switch credential file is too large')
            credentials = json.loads(path.read_text()).get('env', {})
            required = ['SWITCH_API_ENDPOINT', 'SWITCH_AGENT_ID', 'SWITCH_API_TOKEN']
            if any(not isinstance(credentials.get(key), str) or not credentials[key] for key in required):
                raise ValueError('Switch credential file has an unsupported schema')
        self.base = (base_url or os.environ.get('PATCHROOM_SWITCH_URL') or os.environ.get('SWITCH_API_ENDPOINT') or credentials.get('SWITCH_API_ENDPOINT', '')).rstrip('/')
        self.agent_id = agent_id or os.environ.get('PATCHROOM_SWITCH_AGENT_ID') or os.environ.get('SWITCH_AGENT_ID') or credentials.get('SWITCH_AGENT_ID', '')
        self.key = api_key or os.environ.get('PATCHROOM_SWITCH_API_KEY') or os.environ.get('SWITCH_API_TOKEN') or credentials.get('SWITCH_API_TOKEN', '')
        parsed = urllib.parse.urlsplit(self.base)
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment):
            raise ValueError('set PATCHROOM_SWITCH_URL to the Switch bridge base URL')
        if parsed.scheme == 'http' and parsed.hostname not in ('localhost', '127.0.0.1', '::1'):
            raise ValueError('remote Switch servers must use HTTPS')
        if not self.agent_id or not self.key:
            raise ValueError('set PATCHROOM_SWITCH_AGENT_ID and PATCHROOM_SWITCH_API_KEY')
        self.prefix = '/agents/' + urllib.parse.quote(self.agent_id, safe='')
        self.opener = urllib.request.build_opener(NoRedirect)
        self.operations = None

    def request(self, path, body=None, authenticated=True, room_id=None):
        headers = {'Accept': 'application/json'}
        if authenticated:
            headers['Authorization'] = 'Bearer ' + self.key
        if room_id is not None:
            headers['X-Switch-Room-Id'] = room_id
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(self.base + path, data=data, headers=headers)
        try:
            with self.opener.open(request, timeout=15) as response:
                content = response.read(2_000_001)
        except urllib.error.HTTPError as error:
            raise ValueError('Switch HTTP ' + str(error.code) + ' on ' + path) from None
        except urllib.error.URLError:
            raise ValueError('Switch server is unreachable; check the bridge URL and server') from None
        if len(content) > 2_000_000:
            raise ValueError('Switch response exceeded 2 MB')
        return json.loads(content)

    def discover(self):
        response = self.request(self.prefix + '/ops')
        operations = response.get('operations')
        if not isinstance(operations, dict):
            raise ValueError('unsupported Switch operations schema')
        self.operations = operations
        return operations

    def operation(self, name, arguments, room_id=None):
        operations = self.operations if self.operations is not None else self.discover()
        if name not in operations:
            raise ValueError('Switch does not expose required operation: ' + name)
        schema = operations[name].get('input_schema', {})
        properties = schema.get('properties', {})
        if any(key not in properties for key in arguments):
            raise ValueError('installed Switch operation has an incompatible argument schema: ' + name)
        response = self.request(self.prefix + '/ops/' + name, arguments, room_id=room_id)
        if 'result' not in response:
            raise ValueError('unsupported Switch operation response schema')
        result = response['result']
        if isinstance(result, dict) and result.get('error'):
            raise ValueError('Switch operation reported failure: ' + name)
        return result

    def message(self, room_id, message_id):
        before = None
        for _ in range(10):
            arguments = dict(room_id=room_id, limit=100)
            if before is not None:
                arguments['before'] = before
            context = self.operation('read_context', arguments)
            for thread in context.get('threads', []):
                for message in [thread.get('root', {})] + thread.get('replies', []):
                    if message.get('id') == message_id and message.get('kind') == 'message':
                        return dict(message, room_id=room_id)
            if not context.get('truncated') or context.get('oldest_timestamp') is None:
                break
            cursor = datetime.fromtimestamp(context['oldest_timestamp'] / 1000, timezone.utc).isoformat()
            if cursor == before:
                break
            before = cursor
        raise ValueError('message not found in the bounded room history; no identity assumed')

    def health(self):
        return self.request('/health', authenticated=False)


def _human(message):
    if message.get('sender_kind') != 'user' or not message.get('sender'):
        raise ValueError('message must have server-resolved sender_kind=user; agents and unknown identities cannot approve')


def intake(work, case_id, client, room_id, message_id, config_path=None):
    message = client.message(room_id, message_id)
    _human(message)
    origin = dict(server=client.base, room_id=room_id, message_id=message_id,
                  sender=message['sender'], timestamp=message.get('timestamp'))
    store = Store(work)
    try:
        state = store.get(case_id)
    except ValueError:
        state = None
    if state:
        if state.get('origin') == origin and state['report'] == message['body']:
            return case_path(work, case_id)
        raise ValueError('case already exists with a different report or origin')
    return initialize(work, case_id, message['body'], config_path=config_path, origin=origin)


def review(work, case_id, proposal_id, client, message_id):
    store = Store(work)
    state = store.get(case_id)
    origin = state.get('origin')
    if not origin or origin['server'] != client.base:
        raise ValueError('case must originate from authenticated Switch intake on this server')
    message = client.message(origin['room_id'], message_id)
    _human(message)
    if message['sender'] != origin['sender']:
        raise ValueError('only the original human reporter can review this case')
    body = message.get('body', '').strip()
    # Full-message matching rejects quoted approvals and embedded instructions.
    match = re.fullmatch(r'(accept|reject) ' + re.escape(case_id) + r' '
                         + re.escape(proposal_id) + r' ([a-f0-9]{64})', body)
    if not match:
        raise ValueError('expected exact message: accept|reject CASE PROPOSAL FULL_SOURCE_SHA256')
    event_id = client.base + ':' + origin['room_id'] + ':' + message_id
    with store.transaction() as db:
        state = store.get(case_id, db)
        existing = state.get('decision')
        if existing and existing['event_id'] == event_id:
            return existing
        if state['status'] != 'awaiting_human_review' or state['current_proposal'] != proposal_id:
            raise ValueError('review does not match the current proposal awaiting review')
        proposal = next(p for p in store.proposals(case_id, db) if p['id'] == proposal_id)
        if match.group(2) != proposal['source_sha256']:
            raise ValueError('review hash does not match the tested candidate')
        created = datetime.fromisoformat(proposal['created_at']).timestamp() * 1000
        if not isinstance(message.get('timestamp'), (int, float)) or message['timestamp'] < created:
            raise ValueError('review message predates the candidate or lacks a trustworthy timestamp')
        # Review artifacts are mirrors. If edited, refuse until exported again.
        folder = case_path(work, case_id) / 'proposals' / proposal_id / 'source'
        from .adapters import read_files, manifest
        if manifest(read_files(folder, list(proposal['sources']))) != proposal['source_sha256']:
            raise ValueError('exported candidate changed after testing; export the canonical proposal again')
        decision = dict(event_id=event_id, message_id=message_id, sender=message['sender'],
                        room_id=origin['room_id'], server=client.base, decision=match.group(1),
                        proposal_id=proposal_id, source_sha256=proposal['source_sha256'], recorded_at=now())
        store.transition(db, state, 'accepted' if match.group(1) == 'accept' else 'rejected',
                         'authenticated human review')
        state['decision'] = decision
        store.event(db, case_id, 'human_review', decision)
        store.put(db, state)
    export(work, case_id)
    return decision
