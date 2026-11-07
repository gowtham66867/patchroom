import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from patchroom.adapters import ROOT
from patchroom.store import Store
from patchroom.switch_client import SwitchClient


class Handler(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *args):
        pass

    def response(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.calls.append((self.path, self.headers.get('Authorization')))
        if self.path == '/health':
            self.response({'status': 'ok'})
        else:
            self.response({'operations': {'read_context': {'input_schema': {'properties': {
                'room_id': {}, 'limit': {}, 'before': {}}}}}})

    def do_POST(self):
        self.calls.append((self.path, self.headers.get('Authorization')))
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.response({'result': {'threads': [{'root': dict(id='message-1', kind='message',
            body='human report', sender='human-1', sender_kind='user', timestamp=1),
            'replies': []}], 'truncated': False}})


class SwitchHTTP(unittest.TestCase):
    def test_authenticated_discovery_and_room_history(self):
        Handler.calls = []
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        client = SwitchClient('http://127.0.0.1:' + str(server.server_port), 'agent-1', 'test-token')
        self.assertEqual(client.health(), {'status': 'ok'})
        message = client.message('room-1', 'message-1')
        self.assertEqual(message['sender_kind'], 'user')
        self.assertEqual(message['room_id'], 'room-1')
        self.assertEqual(Handler.calls, [('/health', None),
            ('/agents/agent-1/ops', 'Bearer test-token'),
            ('/agents/agent-1/ops/read_context', 'Bearer test-token')])
        with self.assertRaisesRegex(ValueError, 'incompatible argument'):
            client.operation('read_context', {'invented_argument': 1})

    def test_state_survives_separate_cli_processes(self):
        with tempfile.TemporaryDirectory() as temp:
            base = [sys.executable, '-m', 'patchroom', '--work', temp]
            first = subprocess.run(base + ['init', 'restart', '--report', 'Shipping at $100 fails'],
                                   cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            second = subprocess.run(base + ['reproduce', 'restart', '--event-id', 'repro-1'],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(second.returncode, 0, second.stderr)
            result = subprocess.run(base + ['status', 'restart'], cwd=ROOT,
                                    capture_output=True, text=True)
            self.assertEqual(json.loads(result.stdout)['status'], 'reproduced')
            self.assertGreater(len(Store(Path(temp)).timeline('restart')), 1)


if __name__ == '__main__':
    unittest.main()
