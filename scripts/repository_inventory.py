#!/usr/bin/env python3
"""Inventory tracked/new authored files and static references; never delete files.

Python imports and assembly INCLUDEs are dependency evidence. Filename mentions
also retain generated-source staging, command-line probes and documentation, but
are not proof that a path is executed. Dynamic source transforms need review.
"""
import argparse
import ast
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path('docs/repository-inventory.json')
TEXT_SUFFIXES = {'.py', '.inc', '.asm', '.mk', '.md', '.sh', '.mjs', '.json', '.yml', '.yaml'}


def role(path):
    parts = path.parts
    if path.name == 'AGENTS.md':
        return 'repository-guidance'
    if parts[0] == 'references':
        return 'protected-input-placeholder'
    if parts[0] in ('docs', 'outputs', 'cfg', 'assets', 'MSXDevToolExtension'):
        return 'historical-evidence' if parts[0] in ('docs', 'outputs') else 'contributor-resource'
    if parts[0] == 'tests' or (path.suffix == '.py' and
            (path.name.startswith('test_') or 'verify' in path.stem or 'probe' in path.stem)):
        return 'maintained-regression'
    if parts[:2] == ('src','toolchain'):
        return 'host-toolchain'
    if parts[0] == 'scripts':
        return 'public-cli'
    if path.suffix == '.md':
        return 'historical-evidence'
    if path.suffix in ('.asm', '.inc'):
        return 'active-runtime-source'
    return 'required-build-dependency'


def static_references(paths, texts):
    """Return evidence, retaining ambiguous basenames instead of picking one."""
    known = {p.as_posix() for p in paths}
    basenames = defaultdict(list)
    for path in paths:
        basenames[path.name].append(path.as_posix())
    incoming = defaultdict(set)
    for source, text in texts.items():
        if source.endswith('.py'):
            tree = ast.parse(text, filename=source)
            for node in ast.walk(tree):
                modules = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                           else [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
                for module in modules:
                    module_path = module.replace('.', '/')
                    for prefix in ('', str(Path(source).parent) + '/'):
                        for suffix in ('.py', '/__init__.py'):
                            candidate = prefix + module_path + suffix
                            if candidate in known and candidate != source:
                                incoming[candidate].add((source, 'python-import'))
        for target in re.findall(r'(?im)^\s*INCLUDE\s+["\']([^"\']+)["\']', text):
            for candidate in basenames.get(Path(target).name, []):
                if candidate != source:
                    incoming[candidate].add((source, 'assembly-include-candidate'))
        # Also capture names in copy lists, generated templates and prose. This
        # intentionally over-approximates callers; it cannot authorize deletion.
        tokens = set(re.findall(r'[\w.-]+\.(?:py|inc|asm|mk|sh|mjs|json|bin|rom|tsv|csv|xlsx)', text))
        for token in tokens:
            for candidate in basenames.get(token, []):
                if candidate != source:
                    incoming[candidate].add((source, 'filename-mention'))
    return incoming


def inventory(root, output):
    raw = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=root)
    excluded = {output.as_posix(), 'docs/retired-artifacts.json'}
    paths = sorted({Path(p) for p in raw.decode().split('\0') if p and p not in excluded})
    texts = {}
    provenance = {'docs/scripts-audit.json', 'docs/screen4-migration.json', 'docs/screen5-migration.json'}
    for path in paths:
        if ((path.suffix in TEXT_SUFFIXES or path.name == 'Makefile') and
                path.parts[0] not in ('outputs', 'references') and path.as_posix() not in provenance and
                (root/path).is_file()):
            texts[path.as_posix()] = (root/path).read_text()
    incoming = static_references(paths, texts)
    files = []
    for path in paths:
        refs = incoming[path.as_posix()]
        files.append(dict(path=path.as_posix(), role=role(path), present_in_worktree=(root/path).is_file(),
                          references=[dict(path=p, kind=k) for p, k in sorted(refs)]))
    return dict(schema_version=1,
                baseline_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                method='Tracked and visible new file snapshot; Python AST imports, assembly INCLUDE candidates and conservative filename mentions. Includes conditional and historical paths. No runtime reachability or dead-code proof.',
                exclusions=sorted(excluded),
                counts=dict(sorted(Counter(f['role'] for f in files).items())),
                files=files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output
    if output.is_absolute() or '..' in output.parts:
        parser.error('--output must be a repository-relative path')
    result = inventory(ROOT, output)
    (ROOT/output).parent.mkdir(parents=True, exist_ok=True)
    (ROOT/output).write_text(json.dumps(result, indent=2) + '\n')
    print(f'{len(result["files"])} files inventoried: {output}')


if __name__ == '__main__':
    main()
