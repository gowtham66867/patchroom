"""Stage only PatchRoom source for a local Switch runtime outside Downloads.

No credentials, upstream checkout, Git metadata, or existing case state is copied.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ['README.md']
DIRECTORIES = ['patchroom', 'fixtures', 'examples', 'docs']


def stage(destination):
    destination = Path(destination).expanduser().resolve()
    if destination == ROOT or ROOT in destination.parents:
        raise ValueError('runtime destination must be outside the source project')
    if destination.exists() and not (destination / 'patchroom-runtime.json').exists():
        raise ValueError('refusing to overwrite an unrelated existing directory')
    destination.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name in DIRECTORIES:
        for path in (ROOT / name).rglob('*'):
            if path.is_file() and not path.is_symlink() and '__pycache__' not in path.parts:
                relative = path.relative_to(ROOT)
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
                hashes[str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in FILES:
        shutil.copyfile(ROOT / name, destination / name)
        hashes[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    (destination / 'patchroom-runtime.json').write_text(json.dumps(
        dict(source=str(ROOT), files=hashes, note='Runtime snapshot; local cases are stored here independently.'), indent=2) + '\n')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=Path.home() / '.switch/patchroom-project')
    args = parser.parse_args()
    print(stage(args.destination))
