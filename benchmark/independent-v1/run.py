"""Blind validation runner for PyFlowMap. Does not execute fixture modules or judge semantics."""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from zipfile import ZipFile, ZIP_DEFLATED
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
CASES = json.loads((ROOT / 'cases.json').read_text(encoding='utf-8'))['cases']


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): sha256(p)
            for p in sorted(root.rglob('*.py')) if '__pycache__' not in p.parts}


def verify_fixture(case: dict) -> int:
    folder = ROOT / case['source']
    sources = list(folder.rglob('*.py'))
    if not sources:
        raise ValueError(f"No Python modules for {case['id']}")
    for file in sources:
        ast.parse(file.read_text(encoding='utf-8'), filename=str(file))
    return len(sources)


def gather_graphs(folder: Path) -> tuple[list[dict], list[str]]:
    findings = []
    errors = []
    for path in sorted(folder.rglob('*.json')):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (ValueError, UnicodeError) as exc:
            errors.append(f"Bad JSON: {path.name}: {exc}")
            continue
        if isinstance(data, dict) and isinstance(data.get('nodes'), list) and isinstance(data.get('edges'), list):
            nodes = data['nodes']
            edges = data['edges']
            ids = {n.get('id') for n in nodes if isinstance(n, dict)}
            missing = sorted({str(e.get(side)) for e in edges if isinstance(e, dict)
                              for side in ('source', 'target') if e.get(side) not in ids})
            findings.append({'json': path.relative_to(folder).as_posix(),
                             'nodes': len(nodes), 'edges': len(edges),
                             'decisions': sum(n.get('kind') == 'decision' for n in nodes if isinstance(n, dict)),
                             'warnings': len(data.get('warnings', [])), 'dangling_references': missing})
    return findings, errors


def validate_render(folder: Path) -> dict:
    svg_files = list(folder.rglob('*.svg'))
    png_files = list(folder.rglob('*.png'))
    mmd_files = list(folder.rglob('*.mmd'))
    errors = []
    for path in svg_files:
        try:
            ET.parse(path)
        except ET.ParseError as exc:
            errors.append(f"Bad SVG {path.name}: {exc}")
    for path in png_files:
        with path.open('rb') as fp:
            if fp.read(8) != b'\x89PNG\r\n\x1a\n':
                errors.append(f"Bad PNG signature: {path.name}")
    return {'svg': len(svg_files), 'png': len(png_files), 'mermaid': len(mmd_files), 'render_errors': errors}


def render_gallery(folder: Path, entries: list[dict]) -> None:
    blocks = []
    for record in entries:
        case_id = record['id']
        case_dir = folder / 'cases' / case_id
        svgs = sorted(case_dir.rglob('*.svg'))
        if svgs:
            rel = svgs[0].relative_to(folder).as_posix()
            image = f'<a href="{html.escape(rel, quote=True)}"><img loading="lazy" src="{html.escape(rel,quote=True)}" alt="Grafo {case_id}"></a>'
        else:
            image = '<p>No se encontró SVG.</p>'
        blocks.append(f'<article><h2>{html.escape(case_id)} — {html.escape(record["domain"])}</h2>'
                      f'<p>{html.escape(record["entry"])} · {html.escape(record["generation_status"])}</p>{image}</article>')
    content = ('<!doctype html><html lang="es"><head><meta charset="utf-8"><title>PyFlowMap · Banco independiente</title>'
               '<style>body{font-family:system-ui;background:#fafafa;color:#222;margin:2rem}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(400px,1fr));gap:20px}article{border:1px solid #ddd;border-radius:12px;padding:12px;background:white}img{width:100%;height:360px;object-fit:contain;background:white}h2{font-size:1.1rem}</style>'
               '</head><body><h1>PyFlowMap · Primera ejecución independiente</h1><p>Los resultados de generación no implican conformidad semántica. No cambiar el analizador antes de auditar esta primera pasada.</p><main>'
               + '\n'.join(blocks) + '</main></body></html>')
    (folder / 'gallery.html').write_text(content, encoding='utf-8')


def make_zip(out: Path, target: Path) -> None:
    with ZipFile(target, 'w', compression=ZIP_DEFLATED, compresslevel=6) as z:
        # Include the original, previously unseen code, manifest, and exact runner.
        for name in ('README.md', 'run.py', 'cases.json', 'source-hashes.json'):
            z.write(ROOT / name, f'PyFlowMap-Validation/{name}')
        for p in sorted((ROOT / 'fixtures').rglob('*.py')):
            z.write(p, 'PyFlowMap-Validation/' + p.relative_to(ROOT).as_posix())
        for p in sorted(out.rglob('*')):
            if p.is_file():
                z.write(p, 'PyFlowMap-Validation/results/' + p.relative_to(out).as_posix())
    with ZipFile(target) as z:
        bad = z.testzip()
        if bad:
            raise RuntimeError('Corrupted ZIP member: ' + bad)


def git_info(project: Path | None) -> dict:
    if project is None:
        return {}
    info = {}
    for key, args in [('head', ['rev-parse','HEAD']), ('changes_summary', ['status','--porcelain'])]:
        try:
            p = subprocess.run(['git', *args], cwd=project, capture_output=True, text=True, timeout=10)
            if p.returncode == 0:
                info[key] = p.stdout.strip() if key == 'head' else {'modified':sum(bool(s) for s in p.stdout.splitlines())}
        except (OSError, subprocess.TimeoutExpired):
            pass
    src = project / 'src' / 'pyflowmap'
    if src.is_dir():
        info['production_sha256'] = {str(p.relative_to(src)).replace('\\','/'):sha256(p)
                                     for p in sorted(src.rglob('*.py'))}
    return info


def main() -> int:
    ap = argparse.ArgumentParser(description='PyFlowMap: validación exploratoria ciega sin ejecución de fixtures')
    ap.add_argument('--list', action='store_true', help='Listar casos sin generar diagramas')
    ap.add_argument('--validate-only', action='store_true', help='Comprobar sintaxis sin ejecutar PyFlowMap')
    ap.add_argument('--python', default=sys.executable, help='Python del entorno con PyFlowMap instalado')
    ap.add_argument('--project-root', type=Path, help='Raíz PyFlowMap para registrar huellas de producción')
    ap.add_argument('--output', type=Path, default=ROOT.parent/'PyFlowMap-Validation-Results')
    ap.add_argument('--timeout', type=int, default=180)
    ap.add_argument('--package', action='store_true', help='Crear ZIP reproducible de fuentes y resultados')
    args = ap.parse_args()
    for case in CASES:
        module_count = verify_fixture(case)
        if args.list:
            print(f"{case['id']}  {case['domain']:<24} {case['entry']:<30} {module_count} módulos")
    if args.list or args.validate_only:
        if args.validate_only:
            print(f"Sintaxis correcta: {len(CASES)} casos")
        return 0
    out = args.output.expanduser().resolve()
    if out.exists() and any(out.iterdir()):
        ap.error(f'La salida ya existe y no está vacía: {out}. Usa un directorio nuevo para preservar el primer resultado.')
    out.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    project = args.project_root.expanduser().resolve() if args.project_root else None
    rows=[]
    for case in CASES:
        d=out/'cases'/case['id']
        d.mkdir(parents=True)
        source=ROOT/case['source']
        cmd=[args.python, '-m','pyflowmap.cli','analyze',str(source),'--entry',case['entry'],
             '--max-nodes','30','--max-depth','3','--language','es',
             '--renderer','graphviz','--format','all','--semantic-provider','disabled','--output',str(d)]
        print(f"[{case['id']}/{len(CASES)}] {case['entry']}",flush=True)
        start=time.monotonic()
        try:
            process=subprocess.run(cmd, cwd=project or Path.cwd(), env=env,
                                   capture_output=True,text=True, encoding='utf-8',errors='replace',timeout=args.timeout)
            code=process.returncode
            stdout=process.stdout
            stderr=process.stderr
            status='GENERATED' if code == 0 else 'RUN_ERROR'
        except subprocess.TimeoutExpired as exc:
            code=-1; status='TIMEOUT'
            stdout=exc.stdout.decode('utf-8','replace') if isinstance(exc.stdout,bytes) else (exc.stdout or '')
            stderr=exc.stderr.decode('utf-8','replace') if isinstance(exc.stderr,bytes) else (exc.stderr or '')
        duration=round(time.monotonic()-start,3)
        (d/'stdout.txt').write_text(stdout,encoding='utf-8')
        (d/'stderr.txt').write_text(stderr,encoding='utf-8')
        graphs, json_errors=gather_graphs(d)
        render=validate_render(d)
        row={'id':case['id'],'domain':case['domain'],'entry':case['entry'],
             'generation_status':status,'return_code':code,'seconds':duration,
             'graph_candidates':graphs,'json_errors':json_errors,**render,
             'semantic_status':'NOT_EVALUATED'}
        if code == 0 and not graphs:
            row['generation_status']='MISSING_GRAPH_JSON'
        rows.append(row)
    results={'schema_version':1,'benchmark':'PyFlowMap-Banco-Independiente-V1',
             'executed_at':datetime.now(timezone.utc).isoformat(),'parameters':{
             'max_nodes':30,'max_depth':3,'language':'es','renderer':'graphviz',
             'format':'all','semantic_provider':'disabled','timeout_seconds':args.timeout},
             'python':sys.version,'project_git':git_info(project),
             'fixture_hashes':fingerprint(ROOT/'fixtures'), 'cases':rows}
    (out/'run-report.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (out/'run-report.csv').open('w',encoding='utf-8',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=['id','domain','entry','generation_status','semantic_status','nodes','edges','decisions','warnings','svg','png','mermaid','seconds'])
        w.writeheader()
        for r in rows:
            candidate=max(r['graph_candidates'],key=lambda g:g['nodes'], default={})
            w.writerow({**{k:r.get(k) for k in ['id','domain','entry','generation_status','semantic_status','svg','png','mermaid','seconds']},
                        **{k:candidate.get(k) for k in ('nodes','edges','decisions','warnings')}})
    render_gallery(out,rows)
    count=sum(r['generation_status']=='GENERATED' for r in rows)
    lines=['# Primera ejecución ciega — PyFlowMap','',
           '**Este informe NO certifica fidelidad semántica.** Los casos se analizan estáticamente y no se ejecutan.',
           '',f'Casos con generación correcta: {count}/{len(rows)}','',
           '| Caso | Generación | Nodos | Aristas | Decisiones | Advertencias |','|---|---|---:|---:|---:|---:|']
    for r in rows:
        g=max(r['graph_candidates'],key=lambda x:x['nodes'], default={})
        lines.append('| '+ ' | '.join([r['id'],r['generation_status'],str(g.get('nodes','-')),str(g.get('edges','-')),
                                  str(g.get('decisions','-')),str(g.get('warnings','-'))])+' |')
    lines+=['','**No modificar el analizador hasta compartir los primeros resultados para una auditoría independiente.**','']
    (out/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    if args.package:
        dest=out.with_suffix('.zip')
        make_zip(out,dest)
        print(f"ZIP para auditoría: {dest} ({dest.stat().st_size} bytes)")
    print(f'Generados {count}/{len(rows)}. Informe: {out / "REPORT.md"}. Estado semántico: NO EVALUADO.')
    return 0 if count==len(CASES) else 1

if __name__=='__main__':
    raise SystemExit(main())
