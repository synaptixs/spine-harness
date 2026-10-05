"""Validated scenario catalogs, shared by both implementations and intake.

Catalog paths and held-out files are operator-controlled local inputs. Tests are
Python code executed during grading, never included in model ticket text.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess


class CatalogError(ValueError):
    pass


def relative_path(value: str) -> str:
    if not isinstance(value, str) or not value or '\\' in value:
        raise CatalogError(f'Expected a relative POSIX path: {value!r}')
    p = PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or str(p) != value:
        raise CatalogError(f'Unsafe or noncanonical path: {value!r}')
    return value


def load_catalog(path: Path) -> tuple[list[dict], dict]:
    path = path.resolve()
    data = json.loads(path.read_text())
    if not {'schema_version','scenarios'} <= set(data) or set(data)-{'schema_version','scenarios','evaluation_mode'} or data['schema_version'] != 1:
        raise CatalogError('Catalog requires schema_version: 1 and scenarios, with no other top-level keys')
    if not isinstance(data['scenarios'], list) or not data['scenarios']:
        raise CatalogError('scenarios must be a nonempty list')
    mode=data.get('evaluation_mode','graded')
    if mode not in ('graded','tokens-only'):raise CatalogError('Unknown evaluation_mode')
    seen, rows, hashes = set(), [], {path.name: hashlib.sha256(path.read_bytes()).hexdigest()}
    for row in data['scenarios']:
        required = {'key','kind','spec','held_out_tests'}
        if not isinstance(row,dict) or not required <= row.keys() or set(row)-required-{'must_edit'}:
            raise CatalogError('Each scenario needs key, kind, spec, held_out_tests; optional must_edit')
        key = row['key']
        if not isinstance(key,str) or not re.fullmatch(r'[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+',key) or key in seen:
            raise CatalogError(f'Invalid or duplicate scenario ID: {key!r}')
        seen.add(key)
        if row['kind'] not in (('create','edit','change') if mode=='tokens-only' else ('create','edit')):
            raise CatalogError(f'{key}: kind must be create or edit')
        spec = row['spec']
        if not isinstance(spec,dict) or set(spec) != {'title','summary','technical_notes','acceptance_criteria'}:
            raise CatalogError(f'{key}: spec requires title, summary, technical_notes, acceptance_criteria')
        if any(not isinstance(spec[k],str) or not spec[k].strip() for k in ('title','summary','technical_notes')):
            raise CatalogError(f'{key}: spec text must be nonempty strings')
        ac = spec['acceptance_criteria']
        if not isinstance(ac,list) or (not ac and mode!='tokens-only') or any(not isinstance(x,str) or not x.strip() for x in ac):
            raise CatalogError(f'{key}: acceptance_criteria must contain nonempty strings')
        must = row.get('must_edit',[])
        if not isinstance(must,list) or any(not isinstance(p,str) for p in must) or len(set(must)) != len(must):
            raise CatalogError(f'{key}: must_edit must be a list of unique paths')
        must = [relative_path(p) for p in must]
        if (row['kind']=='edit') != bool(must):
            raise CatalogError(f'{key}: edit requires must_edit; create requires it empty')
        tests = row['held_out_tests']
        if not isinstance(tests,list) or (not tests and mode!='tokens-only'):
            raise CatalogError(f'{key}: held_out_tests must list at least one test file')
        bodies = {}
        for rel in tests:
            rel = relative_path(rel)
            file = (path.parent/rel).resolve()
            if not file.is_relative_to(path.parent) or not file.is_file():
                raise CatalogError(f'{key}: missing test or path escapes catalog directory: {rel}')
            if not re.fullmatch(r'test_[A-Za-z0-9_]+\.py',file.name) or file.name in bodies:
                raise CatalogError(f'{key}: held-out basenames must be unique test_*.py names')
            body = file.read_text()
            compile(body,str(file),'exec')
            if not body.strip():
                raise CatalogError(f'{key}: empty held-out test: {rel}')
            bodies[file.name] = body
            hashes[rel] = hashlib.sha256(file.read_bytes()).hexdigest()
        rows.append({'key':key,'kind':row['kind'],'spec':spec,'must_edit':must,'held_out_tests':bodies})
    digest = hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
    metadata={'schema_version':1,'catalog_sha256':digest,'file_sha256':hashes}
    if mode=='tokens-only':metadata['evaluation_mode']=mode
    return rows, metadata


def configure(cb, selected: list[str], catalog: Path | None = None, target: Path | None = None):
    """Install one selected catalog on the imported benchmark; do not patch source files."""
    all_tickets = {t.key:t for t in cb.TICKETS}
    metadata = None
    if catalog:
        rows, metadata = load_catalog(catalog)
        for row in rows:
            if row['key'] in all_tickets:
                raise CatalogError(f'Custom ID shadows a built-in ticket: {row["key"]}')
            all_tickets[row['key']] = cb.Ticket(**row)
    if not selected or len(selected) != len(set(selected)) or any(not x for x in selected):
        raise CatalogError('TICKETS must be a nonempty list of unique IDs')
    unknown = set(selected)-all_tickets.keys()
    if unknown:
        raise CatalogError(f'Unknown TICKETS: {sorted(unknown)}. List IDs with scenarios.py list.')
    tickets = [all_tickets[key] for key in selected]
    for t in tickets:
        if not t.held_out_tests and not (metadata and metadata.get('evaluation_mode')=='tokens-only'):
            raise CatalogError(f'{t.key}: no independent held-out tests')
        if target:
            for rel in t.must_edit:
                relative_path(rel)
                if not (target/rel).is_file() or not (target/rel).resolve().is_relative_to(target.resolve()):
                    raise CatalogError(f'{t.key}: must_edit target missing or outside repository: {rel}')
    cb.TICKETS[:] = tickets
    return metadata


def fingerprint(tickets) -> str:
    """Includes the judge without exposing its contents to a model prompt."""
    values = [{'key':t.key,'kind':t.kind,'spec':t.spec,'must_edit':t.must_edit,
               'held_out_tests':t.held_out_tests} for t in tickets]
    return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()


def changed_python_files(root: Path) -> list[str]:
    """Include staged/unstaged tracked edits as well as untracked Python files."""
    def git(*args):
        return subprocess.run(['git',*args],cwd=root,check=True,capture_output=True).stdout.decode().split('\0')
    paths = set(git('diff','--name-only','--diff-filter=ACMRT','-z','HEAD'))
    paths.update(git('ls-files','--others','--exclude-standard','-z'))
    skip = ('.specify/','.agents/','.claude/','specs/','.venv/')
    return [str(root/p) for p in sorted(paths) if p.endswith('.py') and not p.startswith(skip) and (root/p).is_file()]


def split_python_files(root: Path, paths: list[str]):
    def is_test(p):
        rel=Path(p).relative_to(root)
        return rel.parts[0]=='tests' or rel.name.startswith('test_')
    return [p for p in paths if not is_test(p)], [p for p in paths if is_test(p)]
