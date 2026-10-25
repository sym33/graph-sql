"""Verify and reproduce the compact experiment release."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent


def verified_files():
    manifest = json.loads((ROOT / 'MANIFEST.json').read_text())
    for item in manifest['files']:
        content = (ROOT / item['path']).read_bytes()
        if hashlib.sha256(content).hexdigest() != item['sha256']:
            raise ValueError('Package integrity failure: ' + item['path'])
    index = json.loads((ROOT / 'data/index.json').read_text())
    with zipfile.ZipFile(ROOT / 'data/frozen.zip') as packed:
        for item in index['files']:
            relative = Path(item['path'])
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Unsafe indexed path')
            storage = item['storage']
            content = (packed.read(storage.split(':', 1)[1]) if storage.startswith('data:')
                       else (ROOT / storage).read_bytes())
            if hashlib.sha256(content).hexdigest() != item['sha256']:
                raise ValueError('Input integrity failure: ' + item['path'])
            yield relative, content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['verify', 'example', 'examples', 'cycle-test', 'transfer', 'breadth', 'analysis', 'robustness', 'costs', 'tests', 'all'], nargs='?', default='example')
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    arguments = args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments
    try:
        if args.mode == 'verify':
            if arguments: raise ValueError('verify takes no additional arguments')
            count = sum(1 for _ in verified_files())
            print(f'Verified package and {count} indexed experiment files.')
            return
        work = ROOT / '.runs/work'
        work.mkdir(parents=True, exist_ok=True)
        for relative, content in verified_files():
            target = work / relative
            if not target.resolve().is_relative_to(work.resolve()):
                raise ValueError('Unsafe replay path')
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != hashlib.sha256(content).hexdigest():
                temporary = target.with_name(target.name + '.unpacking')
                temporary.write_bytes(content)
                temporary.replace(target)
        scripts = {'example': 'example.py', 'examples': 'examples/compare.py', 'cycle-test': 'Cycle_Review/replay.py', 'transfer': 'Transfer_Peers/replay.py', 'breadth': 'Transfer_Breadth/replay.py', 'analysis': 'practical_analysis.py',
                   'robustness': 'Robustness/evaluate.py', 'costs': 'deployment_costs.py', 'all': 'run.py'}
        command = ([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'] if args.mode == 'tests'
                   else [sys.executable, scripts[args.mode]])
        status = subprocess.call(command + arguments, cwd=work)
        if status == 0 and args.mode == 'all':
            status = subprocess.call([sys.executable, 'Transfer_Peers/replay.py'], cwd=work)
        if status == 0 and args.mode == 'all':
            status = subprocess.call([sys.executable, 'Transfer_Breadth/replay.py'], cwd=work)
        raise SystemExit(status)
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__': main()
