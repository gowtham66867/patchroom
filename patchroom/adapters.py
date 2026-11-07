"""Explicit source/test allowlists for the fixture and a local unittest repository."""
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'fixtures' / 'checkout'
DEFAULTS = dict(test_pattern='test*.py', min_tests=1, timeout_seconds=15, output_limit=131072)


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def manifest(files):
    return digest(json.dumps(files, sort_keys=True, separators=(',', ':')))


def safe_name(name):
    path = PurePosixPath(name)
    if (not isinstance(name, str) or not name or path.is_absolute() or '..' in path.parts
            or '\\' in name or str(path) != name or not name.endswith('.py')):
        raise ValueError('file paths must be relative .py paths without traversal: ' + str(name))
    return name


def read_files(root, names):
    root = Path(root).resolve()
    result = {}
    if not names or len(names) > 100:
        raise ValueError('configure between 1 and 100 files per file group')
    for name in names:
        safe_name(name)
        path = root / name
        if path.is_symlink() or root not in path.resolve().parents:
            raise ValueError('symlinks and paths outside the repository are not allowed')
        if path.stat().st_size > 1_000_000:
            raise ValueError('source file exceeds 1 MB: ' + name)
        result[name] = path.read_text()
    return result


def snapshot(config_path=None):
    if config_path is None:
        config = dict(DEFAULTS, name='checkout', root=str(FIXTURE), source_files=['checkout.py'],
                      test_files=['test_checkout.py'], min_tests=6,
                      reproduction_test='test_checkout.ShippingContract.test_exact_threshold')
    else:
        path = Path(config_path).resolve()
        raw = json.loads(path.read_text())
        allowed = set(DEFAULTS) | {'name', 'root', 'source_files', 'test_files', 'reproduction_test'}
        if set(raw) - allowed:
            raise ValueError('unknown adapter fields: ' + ', '.join(sorted(set(raw) - allowed)))
        config = dict(DEFAULTS, **raw)
        config['root'] = str((path.parent / config.get('root', '.')).resolve())
    for key in ['source_files', 'test_files', 'reproduction_test']:
        if not config.get(key):
            raise ValueError('adapter requires ' + key)
    if not 1 <= config['min_tests'] <= 10000 or not 0.1 <= config['timeout_seconds'] <= 120:
        raise ValueError('invalid minimum test count or timeout')
    if not 1024 <= config['output_limit'] <= 1_000_000:
        raise ValueError('output limit must be 1024–1000000 bytes')
    if set(config['source_files']) & set(config['test_files']):
        raise ValueError('source and protected test files must not overlap')
    sources = read_files(config['root'], config['source_files'])
    tests = read_files(config['root'], config['test_files'])
    if any(Path(name).match(config['test_pattern']) for name in sources):
        raise ValueError('source files must not match the protected test discovery pattern')
    revision = None
    dirty = None
    try:
        revision = subprocess.check_output(['git', '-C', config['root'], 'rev-parse', 'HEAD'],
                                           text=True, stderr=subprocess.DEVNULL, timeout=10).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass
    try:
        dirty = subprocess.check_output(['git', '-C', config['root'], 'status', '--porcelain'],
                                        text=True, stderr=subprocess.DEVNULL, timeout=10).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return dict(config=config, sources=sources, tests=tests,
                source_sha256=manifest(sources), contract_sha256=manifest(tests),
                git_revision=revision, initial_git_status=dirty,
                dependency_policy='stdlib unittest; no automatic dependency installation')


def candidate_files(state, source_path=None, candidate_dir=None):
    names = state['adapter']['config']['source_files']
    if source_path is not None:
        if len(names) != 1:
            raise ValueError('--source requires an adapter with one source file; use --candidate-dir')
        path = Path(source_path)
        return read_files(path.parent, [path.name]) if path.name == names[0] else {names[0]: read_files(path.parent, [path.name])[path.name]}
    if candidate_dir is None:
        raise ValueError('supply --source or --candidate-dir')
    return read_files(candidate_dir, names)
