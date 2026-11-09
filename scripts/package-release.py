#!/usr/bin/env python3
"""Package the exact frozen binary; never compiles or modifies the executable."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--out', type=Path, default=Path('release-assets'))
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root/'release-manifest.json').read_text())
    if digest(a.binary) != manifest['binary_sha256']:
        raise SystemExit('Binary SHA differs from frozen release manifest')
    a.out.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(a.out).free < 10 * 1024**3 + 256 * 1024**2:
        raise SystemExit('Packaging would violate the 10 GiB disk reserve')
    asset = a.out/'qdrant-veortex-v45-1.20.0-linux-x86_64.tar.gz'
    if asset.exists():
        raise SystemExit('Refusing to overwrite an existing release archive')
    # Package only reviewed, committed public files. Local secrets, data, compiled
    # helper outputs, and ignored configs cannot enter through a recursive walk.
    tracked = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z']).decode().split('\0')
    files = [name for name in tracked if name]
    if not all(name in files for name in ['LICENSE', 'NOTICE', 'DEPLOYMENT.md', 'release-manifest.json']):
        raise SystemExit('Commit the reviewed public release files before packaging')
    with tarfile.open(asset, 'w:gz', compresslevel=6) as archive:
        archive.add(a.binary, arcname='bin/qdrant')
        for name in files:
            path = root/name
            if not path.is_file() or path.is_symlink():
                raise SystemExit('Only tracked regular files may enter the release archive')
            archive.add(path, arcname=name, recursive=False)
    with tarfile.open(asset, 'r:gz') as archive:
        stream = archive.extractfile('bin/qdrant')
        value = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
        if value.hexdigest() != manifest['binary_sha256']:
            raise SystemExit('Packaged binary verification failed')
    shutil.copyfile(root/'release-manifest.json', a.out/'release-manifest.json')
    assets = [asset, a.out/'release-manifest.json']
    (a.out/'SHA256SUMS').write_text(''.join(f'{digest(path)}  {path.name}\n' for path in assets))
    print(json.dumps({'assets': [str(path) for path in assets], 'unchanged_binary_sha256': manifest['binary_sha256']}))


if __name__ == '__main__':
    main()
