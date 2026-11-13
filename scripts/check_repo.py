#!/usr/bin/env python3
"""Offline release checks: candidate files, links, secrets, build inputs and frontend assets.

Checks both tracked and nonignored untracked files, without modifying the index or reading .env.
Historical handoffs and source documents are excluded from link validation.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
REQUIRED = (
    'AGENTS.md', '.env.example', 'faq_search/answer_edits.json',
    'xml graphs/SU_handicaptillaeg_FAQ_Application_Structured.xml',
    'xml graphs/SU_handicaptillaeg_FAQ_Application_Demo.xml',
    '.agents/skills/dcr-xml-builder/scripts/validate_dcr_xml.py',
    'docs/sources/Question_upmapping_chatbot.docx',
    'tools/clean_graph/build_clean_graph.py', 'tools/clean_graph/split_steps.py',
    'tools/clean_graph/dmn_table.py', 'tools/clean_graph/field_help.json',
    'tools/clean_graph/determinations.json',
    'xml graphs/SU_handicaptillaeg_FAQ_Retrieval_Clean_NoEffect.xml',
)
SECRET = re.compile(
    r'(?<![A-Za-z0-9])(?:sk-(?:proj-)?[A-Za-z0-9_-]{32,}|gh[pousr]_[A-Za-z0-9]{30,}|'
    r'github_pat_[A-Za-z0-9_]{40,}|AKIA[A-Z0-9]{16})(?![A-Za-z0-9])'
    r'|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'
)
LINK = re.compile(r'(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)')


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args]).decode()


def main():
    names = set(git('ls-files', '-z', '--cached', '--others', '--exclude-standard').split('\0')) - {''}
    files = sorted(name for name in names if (ROOT / name).is_file())
    problems = []
    for name in files:
        path = Path(name)
        if (set(path.parts) & {'node_modules', '__pycache__', '.pytest_cache', '.ruff_cache', '.jj', '.claude'}
                or (path.parts[0] == 'traces' and name != 'traces/README.md')
                or (path.name.startswith('.env') and name != '.env.example')):
            problems.append(f'private/generated file is a commit candidate: {name}')
            continue
        # Text scan only. Do not inspect local secrets, binaries or ignored material.
        try:
            text = (ROOT / name).read_text(encoding='utf-8')
        except (UnicodeError, OSError):
            continue
        if SECRET.search(text):
            problems.append(f'possible credential in {name} (value withheld)')
        if path.suffix == '.md' and not any(part in path.parts for part in ('handoffs', 'sources')):
            for match in LINK.finditer(text):
                target = match.group(1).split(' "', 1)[0].strip('<>')
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                local = ((ROOT / path).parent / unquote(parsed.path)).resolve()
                if not local.exists():
                    problems.append(f'broken documentation link in {name}: {target}')
    for name in REQUIRED:
        if name not in files:
            problems.append(f'required reproducible input is missing or ignored: {name}')

    # Traverse asset references from the entry point, so old hashed bundles cannot accumulate.
    build = ROOT / 'static/demo'
    index = build / 'index.html'
    if not index.exists():
        problems.append('static/demo/index.html is missing; run npm run build in demo-ui')
    else:
        reachable, pending = set(), [index]
        asset_pattern = re.compile(r'(?:/static/demo/|[./]*)(assets/[A-Za-z0-9_.-]+)')
        while pending:
            current = pending.pop()
            try:
                text = current.read_text(encoding='utf-8')
            except UnicodeError:
                continue
            for match in asset_pattern.finditer(text):
                name = match.group(1)
                if name in reachable:
                    continue
                reachable.add(name)
                asset = build / name
                if not asset.exists():
                    problems.append(f'missing frontend asset: {name}')
                else:
                    pending.append(asset)
        for asset in (build / 'assets').glob('index-*'):
            if asset.relative_to(build).as_posix() not in reachable:
                problems.append(f'obsolete frontend bundle: {asset.relative_to(ROOT)}')

    data = json.loads((ROOT / 'faq_search/data/faq_qa_records.json').read_text())
    meta = json.loads((ROOT / 'faq_search/data/faq_embeddings_meta.json').read_text())
    ids = {row['id'] for row in data['records']}
    if {row['id'] for row in meta['rows']} != ids:
        problems.append('FAQ records and embedding metadata cover different IDs')
    from faq_search.build_faq_data import build
    normalize = lambda rows: [{k: v for k, v in row.items() if k != 'updated_at'} for row in rows]
    if normalize(build()['records']) != normalize(data['records']):
        problems.append('FAQ catalogue does not reproduce from the source documents and answer edits')
    for problem in problems:
        print('FAIL: ' + problem)
    print(f'Checked {len(files)} candidate files; {len(problems)} problems.')
    return bool(problems)


if __name__ == '__main__':
    raise SystemExit(main())
