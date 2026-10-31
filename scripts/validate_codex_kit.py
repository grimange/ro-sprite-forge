#!/usr/bin/env python3
"""Portable structural checks for the Codex kit; no network or third-party packages."""
from pathlib import Path
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = [
    'AGENTS.md', '.codex/config.toml',
    '.codex/agents/forge_qa_reviewer.toml',
    '.codex/agents/forge_format_explorer.toml',
    'README_CODEX_SETUP.md',
    'docs/workflows/KANEO_PMP.md',
    'docs/workflows/M0_KICKOFF.md',
    'docs/templates/KANEO_TASK.md',
    'docs/templates/VERIFICATION_REPORT.md',
    'docs/architecture/RO_SPRITE_FORGE_COMPREHENSIVE_IMPLEMENTATION_PLAN_v1.1.md',
]
SKILLS = ('forge-kaneo','forge-requirements','forge-codec','forge-verification','forge-qa')
errors = []
for name in REQUIRED:
    if not (ROOT / name).is_file():
        errors.append(f'Missing: {name}')
for name in SKILLS:
    p = ROOT / '.agents/skills' / name / 'SKILL.md'
    if not p.is_file():
        errors.append(f'Missing skill: {p.relative_to(ROOT)}')
        continue
    s = p.read_text(encoding='utf-8')
    if not re.search(r'\A---\nname:\s*'+re.escape(name)+r'\n', s):
        errors.append(f'Invalid skill front matter: {name}')
    if not re.search(r'\ndescription:\s*.+\n---\n', s):
        errors.append(f'Skill description missing: {name}')
config = ROOT / '.codex/config.toml'
if config.exists():
    try:
        parsed = tomllib.loads(config.read_text(encoding='utf-8'))
        url = parsed.get('mcp_servers', {}).get('kaneo-local', {}).get('url')
        if url != 'https://pmp.kaneo.local.test/api/mcp':
            errors.append('Wrong Kaneo MCP URL in config')
    except Exception as e:
        errors.append(f'Config TOML invalid: {e}')
for f in sorted((ROOT / '.codex/agents').glob('*.toml')):
    try:
        a = tomllib.loads(f.read_text(encoding='utf-8'))
        for field in ('name','description','developer_instructions'):
            if not a.get(field):
                errors.append(f'{f.name}: missing {field}')
    except Exception as e:
        errors.append(f'{f.name}: invalid TOML: {e}')
if errors:
    print('FAIL:')
    for x in errors:
        print(' -', x)
    sys.exit(1)
print('PASS: kit structure, skill metadata, TOML, and expected Kaneo URL')
print('NOTE: no Codex execution, MCP authentication, code tests or tracker updates verified')
