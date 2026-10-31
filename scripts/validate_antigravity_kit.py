#!/usr/bin/env python3
"""Validate RO Sprite Forge Antigravity kit structure and metadata without networking."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    'GEMINI.md', '.agents/mcp_config.json',
    'docs/architecture/RO_SPRITE_FORGE_COMPREHENSIVE_IMPLEMENTATION_PLAN_v1.1.md',
    'docs/workflows/ANTIGRAVITY_KANEO_PMP.md',
    'docs/workflows/ANTIGRAVITY_M0_KICKOFF.md',
    'docs/templates/AGY_VERIFICATION_REPORT.md',
    'docs/ANTIGRAVITY_FEATURES.md',
]
TRIGGERS = {'model_decision', 'always_on', 'manual', 'glob'}
TOOLS = {'view_file', 'grep_search', 'run_command', 'replace_file_content', 'manage_task'}

def manifest(path: Path) -> tuple[dict[str, object], str]:
    raw=path.read_text(encoding='utf-8')
    if not raw.startswith('---\n'):
        raise ValueError(f'{path}: YAML frontmatter missing')
    try:
        import yaml
    except ImportError:
        # Parse limited one-line scalars (plus tools list) without external dependency.
        parts=raw.split('---\n',2)
        if len(parts)<3:
            raise ValueError(f'{path}: unclosed frontmatter')
        d={}; key=None
        for line in parts[1].splitlines():
            if line.startswith('  - '):
                if not key:
                    raise ValueError(f'{path}: unexpected list entry')
                d.setdefault(key,[]).append(line[4:].strip())
            elif ':' in line:
                key,val=line.split(':',1)
                key=key.strip();val=val.strip()
                if val:
                    d[key]={'true':True,'false':False}.get(val,val.strip('"\''))
                elif key in ('tools','skills'):
                    d[key]=[]
                else:
                    d[key]=''
        return d,parts[2]
    fm,body=raw.split('---\n',2)[1:]
    data=yaml.safe_load(fm)
    if not isinstance(data,dict):
        raise ValueError(f'{path}: invalid frontmatter mapping')
    return data,body

def main() -> int:
    errors=[]
    for p in REQUIRED:
        if not (ROOT/p).is_file():
            errors.append(f'missing {p}')
    try:
        m=json.loads((ROOT/'.agents/mcp_config.json').read_text())
        s=m['mcpServers']['kaneo-local']
        if s != {'serverUrl':'https://pmp.kaneo.local.test/api/mcp'}:
            errors.append('MCP endpoint schema or URL differs from reviewed template')
    except Exception as e:
        errors.append(f'MCP JSON invalid: {e}')
    rules=list((ROOT/'.agents/rules').glob('*.md'))
    skills=list((ROOT/'.agents/skills').glob('*/SKILL.md'))
    agents=list((ROOT/'.agents/agents').glob('*.md'))
    if len(rules)<5: errors.append(f'expected at least 5 rules, found {len(rules)}')
    if len(skills)<7: errors.append(f'expected at least 7 skills, found {len(skills)}')
    if len(agents)<2: errors.append(f'expected at least 2 agents, found {len(agents)}')
    for p in rules+skills+agents:
        try:
            d,body=manifest(p)
            if not body.strip(): errors.append(f'{p}: no instructions')
            if p in rules:
                if d.get('trigger') not in TRIGGERS: errors.append(f'{p}: bad trigger')
                if d.get('trigger')=='model_decision' and not d.get('description'):
                    errors.append(f'{p}: no selection description')
            elif p in skills:
                if p.parent.name.startswith('agy-forge-'):
                    if not d.get('description') or d.get('name') != p.parent.name:
                        errors.append(f'{p}: invalid Antigravity skill metadata')
                elif not d.get('description'):
                    errors.append(f'{p}: missing shared skill description')
            else:
                if not d.get('name') or not d.get('description'):
                    errors.append(f'{p}: missing agent name/description')
                if d.get('mainAgent') is not False or d.get('subagent') is not True:
                    errors.append(f'{p}: independent reviewer/investigator flags missing')
                if any(t not in TOOLS for t in d.get('tools', [])):
                    errors.append(f'{p}: unverified tool name')
                if d.get('commandExecutionPolicy')!='off':
                    errors.append(f'{p}: shell command auto execution not off')
        except Exception as e:
            errors.append(f'{p}: {e}')
    p=ROOT/REQUIRED[2]
    if p.exists():
        digest=hashlib.sha256(p.read_bytes()).hexdigest()
        print(f'Plan v1.1 SHA-256: {digest}')
    if (ROOT/'AGENTS.md').exists():
        print('Note: AGENTS.md is present and may belong to Codex; this kit does not replace it.')
    if errors:
        for e in errors: print('FAIL:',e,file=sys.stderr)
        return 1
    print(f'PASS: {len(rules)} rules, {len(skills)} skills, {len(agents)} agents; Kaneo MCP JSON; required files')
    print('Not verified: live Antigravity CLI, Kaneo login, network/TLS, actual project/task, native Korangar.')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
