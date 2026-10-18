#!/usr/bin/env python3
"""Evaluate Python-source benchmarks without executing fixture programs."""
from __future__ import annotations

import argparse
import ast
import csv
import html
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict, deque
from datetime import UTC, datetime
from pathlib import Path

from benchmark.evaluation.oracles_current import evaluate_semantics

HERE = Path(__file__).resolve().parents[1]
CASES = HERE / 'cases.json'
FIXTURES = HERE / 'fixtures'


def check_sources(case: dict, fixtures_root: Path = FIXTURES) -> tuple[Path, list[dict]]:
    root = fixtures_root.resolve()
    source = (root / case['source']).resolve()
    if not source.is_relative_to(root) or not source.exists():
        raise ValueError('Missing or unsafe fixture source: ' + case['source'])
    files = [source] if source.is_file() else sorted(source.rglob('*.py'))
    marks: list[dict] = []
    for path in files:
        text = path.read_text(encoding='utf-8-sig')
        ast.parse(text, filename=str(path))  # DO NOT import/execute fixture source.
        for line_no, line in enumerate(text.splitlines(), 1):
            if '# BENCH:critical' in line:
                marks.append({'file': path.name if source.is_file() else path.relative_to(source).as_posix(),
                              'line': line_no, 'source': line.split('# BENCH:critical')[0].strip()})
    return source, marks


def reachable(seed: str, adjacency: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    pending = deque([seed])
    while pending:
        node = pending.popleft()
        if node in seen:
            continue
        seen.add(node)
        pending.extend(adjacency.get(node, set()) - seen)
    return seen


def inspect_graph(graph: dict, markers: list[dict], min_decisions: int) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    nodes = graph.get('nodes')
    edges = graph.get('edges')
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return {'errors': ['JSON must include nodes/edges arrays'], 'warnings': [],
                'node_count': 0, 'edge_count': 0, 'critical_direct': 0, 'critical_metadata': 0,
                'critical_missing': len(markers), 'critical_total': len(markers)}
    by_id = {n.get('id'): n for n in nodes if isinstance(n, dict) and isinstance(n.get('id'), str)}
    if len(by_id) != len(nodes):
        errors.append('Duplicate or invalid node IDs')
    initial = [n['id'] for n in nodes if isinstance(n, dict) and n.get('kind') == 'initial']
    finals = [n['id'] for n in nodes if isinstance(n, dict) and n.get('kind') == 'final']
    if len(initial) != 1:
        errors.append(f'Expected exactly one initial node, found {len(initial)}')
    if not finals:
        errors.append('Missing final node')
    forwards: dict[str, set[str]] = defaultdict(set)
    backwards: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        if not isinstance(edge, dict) or edge.get('source') not in by_id or edge.get('target') not in by_id:
            errors.append(f'Unknown edge endpoint: {edge}')
            continue
        forwards[edge['source']].add(edge['target'])
        backwards[edge['target']].add(edge['source'])
    if len(initial) == 1:
        orphans = set(by_id) - reachable(initial[0], forwards)
        if orphans:
            errors.append(f'{len(orphans)} nodes unreachable from initial')
    if finals:
        terminable = set().union(*(reachable(n, backwards) for n in finals))
        stranded = set(by_id) - terminable
        if stranded:
            errors.append(f'{len(stranded)} nodes lack a path to final')
    decisions = [n for n in nodes if isinstance(n, dict) and n.get('kind') == 'decision']
    if len(decisions) < min_decisions:
        warnings.append(f'Only {len(decisions)} decision nodes (manual oracle expects >= {min_decisions}); check representation')
    critical_direct = critical_metadata = critical_missing = 0
    misses = []
    for mark in markers:
        full_re = re.compile(r'(?<![A-Za-z0-9_])' + re.escape(mark['file'].replace('\\', '/')) + r':' + str(mark['line']) + r'(?!\d)')
        # Some versions store absolute path; match its ending with a boundary.
        file_tail = mark['file'].replace('\\', '/').split('/')[-1]
        loose_re = re.compile(r'(?<![A-Za-z0-9_])' + re.escape(file_tail) + r':' + str(mark['line']) + r'(?!\d)')
        def matches(value: str, full_re=full_re, loose_re=loose_re) -> bool:
            norm = value.replace('\\', '/')
            return bool(full_re.search(norm) or loose_re.search(norm))
        try:
            marker_ast = ast.parse(mark['source'])
            marker_calls = [ast.unparse(n) for n in ast.walk(marker_ast) if isinstance(n, ast.Call)]
            marker_callables = [ast.unparse(n.func) for n in ast.walk(marker_ast) if isinstance(n, ast.Call)]
        except SyntaxError:
            marker_calls, marker_callables = [], []

        visible_expressions = []
        metadata_expressions = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_locations = node.get('locations') or []
            node_matches = any(matches(str(loc)) for loc in node_locations)
            metadata = node.get('label_metadata', {})
            expression = str(metadata.get('call_expression', ''))
            if node_matches and metadata.get('significant_call'):
                visible_expressions.append(expression)
            metadata_expressions.extend((expression, loc or (str(node_locations[0]) if node_locations else ""))
                                        for expression, loc in _metadata_call_sites(metadata))
        if marker_calls:
            visible = all(any(expr and (expr == actual or expr in actual or actual in expr)
                              for actual in visible_expressions)
                          for expr in marker_calls)
            hidden = any(expr and (expr == actual or expr in actual or actual in expr)
                         and (not loc or matches(loc))
                         for expr in marker_callables for actual, loc in metadata_expressions)
            if visible:
                critical_direct += 1
            elif hidden:
                critical_metadata += 1
            else:
                critical_missing += 1
                misses.append(f"{mark['file']}:{mark['line']} — {mark['source']}")
        elif any(any(matches(str(loc)) for loc in (node.get('locations') or []))
                 for node in nodes if isinstance(node, dict)):
            # Non-call markers are retained as a source-location check.
            critical_direct += 1
        elif any(matches(json.dumps(node.get('label_metadata', {}), ensure_ascii=False))
                 for node in nodes if isinstance(node, dict)):
            critical_metadata += 1
        else:
            critical_missing += 1
            misses.append(f"{mark['file']}:{mark['line']} — {mark['source']}")
    if misses:
        warnings.append('Critical call sites not found directly or in metadata: ' + '; '.join(misses))
    return {
        'node_count': len(nodes), 'edge_count': len(edges), 'decision_count': len(decisions),
        'kinds': dict(Counter(str(n.get('kind')) for n in nodes if isinstance(n, dict))),
        'errors': errors, 'warnings': warnings,
        'critical_total': len(markers), 'critical_direct': critical_direct,
        'critical_metadata': critical_metadata, 'critical_missing': critical_missing,
        'analyzer_warnings': len(graph.get('warnings', [])),
    }


def _metadata_call_expressions(metadata: dict) -> list[str]:
    expressions: list[str] = []
    if isinstance(metadata, dict):
        for key, value in metadata.items():
            if key == 'contained_call_expressions' and isinstance(value, list):
                expressions.extend(map(str, value))
            elif key == 'subprocess_calls' and isinstance(value, list):
                expressions.extend(str(item.get('expression', '')) for item in value if isinstance(item, dict))
            elif isinstance(value, (dict, list)):
                expressions.extend(_metadata_call_expressions(value))
    elif isinstance(metadata, list):
        for item in metadata:
            expressions.extend(_metadata_call_expressions(item))
    return [value for value in expressions if value]


def _metadata_call_sites(metadata) -> list[tuple[str, str]]:
    sites: list[tuple[str, str]] = []
    if isinstance(metadata, dict):
        for key, value in metadata.items():
            if key == 'subprocess_calls' and isinstance(value, list):
                sites.extend((str(item.get('expression', '')), str(item.get('location', '')))
                             for item in value if isinstance(item, dict))
            elif key == 'contained_call_expressions' and isinstance(value, list):
                sites.extend((str(item), '') for item in value)
            elif isinstance(value, (dict, list)):
                sites.extend(_metadata_call_sites(value))
    elif isinstance(metadata, list):
        for item in metadata:
            sites.extend(_metadata_call_sites(item))
    return [(expr, loc) for expr, loc in sites if expr]


def run_case(case: dict, out: Path, render: bool, timeout: int, max_depth: int,
             max_nodes: int, fixtures_root: Path = FIXTURES, language: str = 'en') -> dict:
    source, markers = check_sources(case, fixtures_root)
    output = out / 'cases' / case['id']
    output.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, '-m', 'pyflowmap', 'analyze', str(source),
               '--entry', case['entry'], '--diagram-type', 'activity',
               '--semantic-provider', 'disabled', '--language', language,
               '--max-nodes', str(max_nodes), '--max-depth', str(max_depth),
               '--format', 'images' if render else 'mmd', '--renderer', 'graphviz',
               '--output', str(output)]
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    row = {**case, 'source': str(source), 'marks': markers, 'command': command,
           'status': 'error', 'files': {}, 'errors': [], 'warnings': []}
    try:
        process = subprocess.run(command, check=False, cwd=out.parent, capture_output=True, text=True,
                                 encoding='utf-8', errors='replace', timeout=timeout, env=env)
        if process.returncode:
            row['errors'].append(f'Exit code {process.returncode}: {process.stderr[-900:]}')
            return row
        result = json.loads(process.stdout)
        row['files'] = result.get('files', {})
        graph_path = Path(row['files']['json'])
        graph = json.loads(graph_path.read_text(encoding='utf-8'))
        stats = inspect_graph(graph, markers, case.get('min_decisions', 0))
        row.update(stats)
        row['structural_status'] = 'FAIL' if stats['errors'] else 'PASS'
        row['structural_warnings'] = stats['warnings']
        row['semantic'] = evaluate_semantics(case, source, graph)
        row['semantic_status'] = row['semantic']['status']
        if stats['errors'] or row['semantic_status'] == 'FAIL':
            row['status'] = 'FAIL'
        elif row['semantic_status'] == 'UNSUPPORTED':
            row['status'] = 'UNSUPPORTED'
        elif row['semantic_status'] == 'REVIEW':
            row['status'] = 'REVIEW'
        else:
            row['status'] = 'PASS'
        if render:
            svg = Path(row['files']['svg'])
            png = Path(row['files']['png'])
            if '<svg' not in svg.read_text(encoding='utf-8'):
                row['errors'].append('SVG invalid or not encoded as UTF-8')
            if png.read_bytes()[:8] != b'\x89PNG\r\n\x1a\n':
                row['errors'].append('PNG signature invalid')
            if row['errors']:
                row['status'] = 'FAIL'
                row['structural_status'] = 'FAIL'
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        row['errors'].append(f'{type(exc).__name__}: {exc}')
    return row


def reports(out: Path, rows: list[dict], render: bool) -> None:
    out.mkdir(parents=True, exist_ok=True)
    summary = {'generated_at_utc': datetime.now(UTC).isoformat(),
               'render': render, 'model': 'PyFlowMap static AST, provider=disabled',
               'cases': rows,
               'totals': dict(Counter(row['status'] for row in rows))}
    (out / 'report.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    with (out / 'report.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['id', 'domain', 'patterns', 'status', 'structural_status',
                                                     'semantic_status', 'node_count',
                                                     'edge_count', 'decision_count', 'critical_direct',
                                                     'critical_metadata', 'critical_missing', 'analyzer_warnings'])
        writer.writeheader()
        writer.writerows([{k: r.get(k) for k in writer.fieldnames} for r in rows])
    lines = ['# PyFlowMap cross-domain benchmark', '',
             'Fixture programs were parsed but never executed. No AI provider was used; semantic and structural checks are reported separately.', '',
             '| Case | Domain | Semantics | Structure | Nodes | Edges | Decisions | Calls visible / metadata / missing |',
             '|---|---|---|---|---:|---:|---:|---:|']
    gallery: list[str] = []
    for row in rows:
        esc = html.escape
        direct = row.get('critical_direct', 0)
        total = row.get('critical_total', len(row['marks']))
        lines.append(f"| {row['id']} | {row['domain']} | {row.get('semantic_status', 'REVIEW')} | "
                     f"{row.get('structural_status', 'REVIEW')} | {row.get('node_count', '-')} | "
                     f"{row.get('edge_count', '-')} | {row.get('decision_count', '-')} | "
                     f"{direct}/{row.get('critical_metadata', 0)}/{row.get('critical_missing', total)} |")
        lines.extend(['', f"### {row['id']}", ''])
        for e in row.get('errors', []):
            lines.append('- ERROR: ' + str(e))
        for w in row.get('warnings', []):
            lines.append('- REVIEW: ' + str(w))
        for feature in row.get('semantic', {}).get('features', []):
            lines.append(f"- SEMANTIC {feature['status']} — {feature['feature']}: {feature['message']}")
        if row.get('status') == 'PASS':
            lines.append('- All checked semantic and structural obligations passed.')
        if row.get('files'):
            lines.append('- Graph: `' + str(row['files'].get('json', '')) + '`')
        if render and row.get('files', {}).get('svg'):
            svg = Path(row['files']['svg'])
            rel = os.path.relpath(svg, out).replace('\\', '/')
            gallery.append(f'<section><h2>{esc(row["id"])} — {esc(row["domain"])}</h2>'
                           f'<p>{esc(row["patterns"])} · semantics: {esc(row.get("semantic_status", "REVIEW"))}; '
                           f'structure: {esc(row.get("structural_status", "REVIEW"))}</p>'
                           f'<object data="{esc(rel)}" type="image/svg+xml" width="100%" height="550"></object>'
                           f'<p><a href="{esc(rel)}">Open full-size SVG</a></p></section>')
    (out / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    if render:
        page = '<!doctype html><html lang="en"><meta charset="utf-8"><title>PyFlowMap: cross-domain benchmark</title>'
        page += '<style>body{font:16px system-ui;max-width:1200px;margin:auto;padding:2em}section{border-top:1px solid #ddd;margin-top:2em}object{border:1px solid #ddd}</style>'
        page += '<h1>PyFlowMap: cross-domain activity diagrams</h1>'
        page += '<p>Visual inspection supplements, but does not replace, semantic and structural checks.</p>'
        page += '\n'.join(gallery) + '</html>'
        (out / 'gallery.html').write_text(page, encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description='Evaluate Python sources without running fixture code.')
    parser.add_argument('--output', type=Path, default=Path.cwd() / 'pyflowmap-output' / 'benchmark')
    parser.add_argument('--cases-file', type=Path, default=CASES,
                        help='Case manifest; defaults to the 15-case cross-domain bank')
    parser.add_argument('--fixtures-root', type=Path, default=FIXTURES,
                        help='Directory containing paths referenced by the case manifest')
    parser.add_argument('--render', action='store_true', help='Render SVG and PNG (requires Graphviz dot)')
    parser.add_argument('--strict', action='store_true', help='Treat REVIEW or missing expected evidence as failure')
    parser.add_argument('--only', nargs='*', help='Case IDs to evaluate')
    parser.add_argument('--list', action='store_true', help='List cases without running PyFlowMap')
    parser.add_argument('--language', choices=['en', 'es'], default='en',
                        help='Diagram label language (English by default)')
    parser.add_argument('--max-depth', type=int, default=3)
    parser.add_argument('--max-nodes', type=int, default=30)
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    cases_path = args.cases_file.resolve()
    fixtures_root = args.fixtures_root.resolve()
    if not cases_path.is_file() or not fixtures_root.is_dir():
        parser.error('--cases-file must be a file and --fixtures-root must be a directory')
    cases = json.loads(cases_path.read_text(encoding='utf-8'))['cases']
    if args.only:
        unknown = set(args.only) - {c['id'] for c in cases}
        if unknown:
            parser.error('Unknown case IDs: ' + ', '.join(sorted(unknown)))
        cases = [c for c in cases if c['id'] in args.only]
    if args.list:
        for case in cases:
            _source, markers = check_sources(case, fixtures_root)
            print(f"{case['id']:<14} {case['patterns']:<55} ({len(markers)} marked call sites)")
        return 0
    if args.render and not shutil.which("dot"):
        parser.error("Graphviz dot is unavailable; install Graphviz or omit --render")
    out = args.output.resolve()
    # Never allow benchmark reports to be generated within fixtures (would pollute inputs).
    if out.is_relative_to(fixtures_root):
        parser.error('--output must be outside the fixture source directory')
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in cases:
        row = run_case(case, out, args.render, args.timeout, args.max_depth, args.max_nodes,
                       fixtures_root, args.language)
        rows.append(row)
        print(f"{case['id']:<14} {row['status']:<7} "
              f"{row.get('node_count', '-')} nodes, {row.get('edge_count', '-')} edges "
              f"critical={row.get('critical_direct', 0)}/{len(row['marks'])}")
    reports(out, rows, args.render)
    print(f'\nReports: {out / "REPORT.md"}, {out / "report.csv"}, {out / "report.json"}')
    if args.render:
        print(f'Gallery: {out / "gallery.html"}')
    failed = [r for r in rows if r['errors'] or r.get('semantic_status') == 'FAIL']
    if args.strict:
        failed.extend(r for r in rows if r.get('status') != 'PASS')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
