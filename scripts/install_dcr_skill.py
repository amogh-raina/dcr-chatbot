#!/usr/bin/env python3
"""Copy the bundled DCR skill to an agent's skill directory without overwriting an installation."""
import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '.agents/skills/dcr-xml-builder'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--agent', choices=('codex', 'claude'))
    choice.add_argument('--dest', type=Path, help='exact destination skill folder for another agent')
    parser.add_argument('--scope', choices=('user', 'repo'), default='user')
    args = parser.parse_args(argv)
    if not (SOURCE / 'SKILL.md').is_file():
        parser.error('bundled skill is missing; use a complete repository checkout')
    if args.dest:
        target = args.dest.expanduser().resolve()
    else:
        base = Path.home() if args.scope == 'user' else ROOT
        target = base / ('.agents' if args.agent == 'codex' else '.claude') / 'skills/dcr-xml-builder'
    if target.resolve() == SOURCE.resolve():
        print(f'Already available in this repository: {SOURCE}')
        return 0
    if target.exists():
        parser.error(f'destination already exists; left unchanged: {target}')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    print(f'Installed dcr-xml-builder: {target}')
    print('Use it in a new agent chat; for agents without discovery, read its SKILL.md explicitly.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
