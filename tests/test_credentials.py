import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from patchroom.switch_client import SwitchClient


class Credentials(unittest.TestCase):
    def test_existing_controller_schema_is_read_without_copying(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {}, clear=True):
            path = Path(temp) / 'credentials.json'
            path.write_text(json.dumps({'env': {'SWITCH_API_ENDPOINT': 'http://127.0.0.1:8000',
                'SWITCH_AGENT_ID': 'test-agent', 'SWITCH_API_TOKEN': 'test-secret'}}))
            client = SwitchClient(credentials_file=path)
            self.assertEqual(client.agent_id, 'test-agent')
            self.assertEqual(client.key, 'test-secret')
            self.assertEqual(list(Path(temp).iterdir()), [path])

    def test_bad_schema_does_not_echo_contents(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {}, clear=True):
            path = Path(temp) / 'credentials.json'
            path.write_text(json.dumps({'env': {'SWITCH_API_TOKEN': 'private-test-value'}}))
            with self.assertRaises(ValueError) as raised:
                SwitchClient(credentials_file=path)
            self.assertNotIn('private-test-value', str(raised.exception))


if __name__ == '__main__':
    unittest.main()
