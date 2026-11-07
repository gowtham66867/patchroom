"""Bounded process execution; isolation of working copies is not a security sandbox."""
import json
import os
import selectors
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RUNNER = Path(__file__).with_name('test_runner.py')


def execute(files, config):
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='patchroom-run-') as temp:
        root = Path(temp)
        checkout = root / 'checkout'
        checkout.mkdir()
        for name, content in files.items():
            target = checkout / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        result_file = root / 'result.json'
        command = [sys.executable, '-I', str(RUNNER), str(checkout),
                   config.get('test_pattern', 'test*.py'), str(result_file)]
        metadata = {'command': command, 'working_directory': str(checkout),
                    'timeout_seconds': config['timeout_seconds'], 'output_limit': config['output_limit']}
        output = bytearray()
        reason = None
        process = subprocess.Popen(command, cwd=checkout, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                if time.monotonic() - started >= config['timeout_seconds']:
                    reason = 'timeout'
                    break
                for key, _ in selector.select(0.05):
                    chunk = os.read(key.fileobj.fileno(), 8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    room = config['output_limit'] - len(output)
                    output.extend(chunk[:max(0, room)])
                    if len(chunk) > room:
                        reason = 'output_limit'
                        break
                if reason:
                    break
        if reason is None:
            try:
                process.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                reason = 'lingering_process'
        if reason:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                if process.poll() is None:
                    process.kill()
            process.wait()
        process.stdout.close()
        summary = None
        if result_file.exists() and result_file.stat().st_size <= 1_000_000:
            try:
                summary = json.loads(result_file.read_text())
            except (ValueError, OSError):
                pass
        text = output.decode('utf-8', errors='replace')
        completed = (reason is None and isinstance(summary, dict)
                     and summary.get('ran', 0) >= config['min_tests'])
        if not completed:
            classification = 'insufficient_evidence' if reason is None else 'environment_error'
        elif summary['errors'] or process.returncode not in (0, 1):
            classification = 'environment_error'
        elif summary['skipped'] or summary['expected_failures'] or summary['unexpected_successes']:
            classification = 'insufficient_evidence'
        elif summary['failures']:
            classification = 'failed'
        elif process.returncode == 0:
            classification = 'verified'
        else:
            classification = 'environment_error'
        return dict(metadata, passed=classification == 'verified', completed=completed,
                    classification=classification, exit_code=process.returncode,
                    reason=reason, summary=summary, output=text,
                    duration_seconds=round(time.monotonic() - started, 4))
