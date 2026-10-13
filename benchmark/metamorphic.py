"""Run domain-neutral metamorphic checks against the installed CLI."""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tokenize
from pathlib import Path

from portable_tempdirs import temporary_directory

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"


def rename_identifiers(source: Path, destination: Path, mapping: dict[str, str]) -> None:
    text = source.read_text(encoding="utf-8-sig")
    tokens = tokenize.generate_tokens(io.StringIO(text).readline)
    changed = (token._replace(string=mapping[token.string])
               if token.type == tokenize.NAME and token.string in mapping else token
               for token in tokens)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(tokenize.untokenize(changed), encoding="utf-8", newline="")


def graph_signature(path: Path, ignored_pure_calls: tuple[str, ...] = ()) -> dict:
    graph = json.loads(path.read_text(encoding="utf-8"))
    nodes = {node["id"]: node for node in graph["nodes"]}
    removed = {node_id for node_id, node in nodes.items()
               if node.get("label_metadata", {}).get("significant_call")
               and node.get("label_metadata", {}).get("call_expression") in ignored_pure_calls}
    edges = list(graph["edges"])
    for node_id in removed:
        incoming_edges = [edge for edge in edges if edge["target"] == node_id]
        outgoing_edges = [edge for edge in edges if edge["source"] == node_id]
        # This metamorphic case proves `len` is the builtin and its argument is
        # a list-comprehension result. Its possible TypeError edge is therefore
        # outside the equivalence claim and may be removed with its propagation
        # marker. Other calls and exception routes are never normalized away.
        exceptional = [edge for edge in outgoing_edges
                       if edge.get("label") in {"May raise", "Puede lanzar"}
                       and nodes[edge["target"]].get("label_metadata", {}).get("exception_route")
                       == "propagated"]
        if exceptional:
            if len(exceptional) != 1 or len(outgoing_edges) != 2:
                raise ValueError(f"Cannot normalize exceptional pure call node {node_id}")
            propagated = exceptional[0]["target"]
            propagated_edges = [edge for edge in edges if edge["source"] == propagated]
            if (len(propagated_edges) != 1
                    or nodes[propagated].get("label_metadata", {}).get("control_transfer") != "raise"):
                raise ValueError(f"Cannot normalize nonterminal exception route {propagated}")
            edges = [edge for edge in edges
                     if edge is not exceptional[0] and edge not in propagated_edges]
            nodes.pop(propagated)
            outgoing_edges = [edge for edge in outgoing_edges if edge is not exceptional[0]]
        if len(incoming_edges) != 1 or len(outgoing_edges) != 1:
            raise ValueError(f"Cannot normalize non-linear pure call node {node_id}")
        incoming_edge, outgoing_edge = incoming_edges[0], outgoing_edges[0]
        if incoming_edge.get("label") and outgoing_edge.get("label"):
            raise ValueError(f"Cannot preserve two edge labels around pure call node {node_id}")
        edges = [edge for edge in edges if edge is not incoming_edge and edge is not outgoing_edge]
        if incoming_edge["source"] not in removed and outgoing_edge["target"] not in removed:
            edges.append({"source": incoming_edge["source"], "target": outgoing_edge["target"],
                          "label": incoming_edge.get("label") or outgoing_edge.get("label", "")})
    nodes = {node_id: node for node_id, node in nodes.items() if node_id not in removed}
    edges = [edge for edge in edges
             if edge["source"] in nodes and edge["target"] in nodes]
    outgoing = {node_id: [] for node_id in nodes}
    incoming = {node_id: [] for node_id in nodes}
    edge_pairs = []
    branch_counts = {"yes": 0, "no": 0, "other": 0}
    for edge in edges:
        source, target = edge["source"], edge["target"]
        label = edge.get("label", "").strip().casefold()
        label = "yes" if label in {"sí", "si", "yes", "true"} else "no" if label in {"no", "false"} else "other"
        outgoing[source].append((label, target))
        incoming[target].append((label, source))
        edge_pairs.append((nodes[source].get("kind"), label, nodes[target].get("kind")))
        branch_counts[label] += 1
    colors = {node_id: json.dumps([node.get("kind")], separators=(",", ":"))
              for node_id, node in nodes.items()}
    for _ in range(max(1, len(nodes))):
        colors = {
            node_id: hashlib.sha256(json.dumps([
                nodes[node_id].get("kind"),
                sorted((label, colors[target]) for label, target in outgoing[node_id]),
                sorted((label, colors[source]) for label, source in incoming[node_id]),
            ], separators=(",", ":")).encode()).hexdigest()
            for node_id in nodes
        }
    return {
        "nodes": len(nodes), "edges": len(edges),
        "node_kinds": sorted(node.get("kind") for node in nodes.values()),
        "decision_count": sum(node.get("kind") == "decision" for node in nodes.values()),
        "edge_kind_polarities": sorted(edge_pairs),
        "branch_counts": branch_counts,
        "degree_profile": sorted((len(incoming[node_id]), len(outgoing[node_id])) for node_id in nodes),
        "topology_colors": sorted(colors.values()),
    }


def run_analysis(python: str, source: Path, entry: str, output: Path, cwd: Path) -> Path:
    command = [python, "-m", "pyflowmap", "analyze", str(source), "--entry", entry,
               "--diagram-type", "activity", "--semantic-provider", "disabled", "--language", "es",
               "--max-nodes", "30", "--max-depth", "3", "--format", "mmd",
               "--renderer", "graphviz", "--output", str(output)]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(command, check=False, cwd=cwd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=180, env=env)
    if result.returncode:
        raise RuntimeError(f"Analyzer failed for {source}: {result.stderr[-1000:]}")
    payload = json.loads(result.stdout)
    return Path(payload["files"]["json"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Metamorphic checks; fixture programs are parsed, never executed.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    cases = []
    with temporary_directory("pyflowmap-metamorphic", parent=output) as temp_root:
        work = Path(temp_root)
        cases.extend(_rename_case(work, "variable-function-renaming", FIXTURES / "logic/predicates.py",
                                  "predicates:authorize", "predicates:evaluate_access",
                                  {"authorize": "evaluate_access", "audit_access": "check_gate",
                                   "check_token": "verify_credential", "count_attempt": "record_attempt",
                                   "allowed": "accepted", "fallback": "alternate_count",
                                   "user": "principal", "token": "credential"}))
        cases.extend(_rename_case(work, "class-method-renaming", FIXTURES / "library/resolution.py",
                                  "resolution:Derived.process", "resolution:Concrete.apply",
                                  {"Base": "Entity", "Derived": "Concrete",
                                   "convert": "coerce", "process": "apply"}))
        cases.extend(_module_rename_case(work))
        cases.extend(_equivalent_expression_case(work))
        cases.extend(_relocation_case(work))
    report = {"schema_version": 2, "oracle": "Exact directed topology for identifier/module/path renames; expression equivalence uses only a preconditioned control-flow normalization that removes proven pure operations, while raw graph signatures remain recorded.",
              "cases": cases,
              "totals": {"pass": sum(row["status"] == "PASS" for row in cases),
                         "fail": sum(row["status"] == "FAIL" for row in cases)}}
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    for row in cases:
        print(row["status"], row["id"], row["baseline"]["nodes"], "->", row["variant"]["nodes"],
              "nodes;", row["baseline"]["edges"], "->", row["variant"]["edges"], "edges")
    print(report_path)
    return 1 if report["totals"]["fail"] else 0


def _compare(work: Path, name: str, source_a: Path, entry_a: str,
             source_b: Path, entry_b: str, invariant: str,
             ignored_pure_calls: tuple[str, ...] = ()) -> dict:
    python = sys.executable
    graph_a = run_analysis(python, source_a, entry_a, work / name / "baseline-output", HERE.parent)
    graph_b = run_analysis(python, source_b, entry_b, work / name / "variant-output", HERE.parent)
    sig_a, sig_b = graph_signature(graph_a), graph_signature(graph_b)
    normalized_a = graph_signature(graph_a, ignored_pure_calls)
    normalized_b = graph_signature(graph_b, ignored_pure_calls)
    return {"id": name, "invariant": invariant, "baseline": sig_a, "variant": sig_b,
            "normalization": {"ignored_proven_pure_calls": list(ignored_pure_calls),
                              "baseline": normalized_a, "variant": normalized_b},
            "status": "PASS" if normalized_a == normalized_b else "FAIL"}


def _rename_case(work: Path, name: str, source: Path, entry_a: str, entry_b: str,
                 mapping: dict[str, str]) -> list[dict]:
    a, b = work / name / "baseline" / source.name, work / name / "variant" / source.name
    a.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, a)
    rename_identifiers(source, b, mapping)
    return [_compare(work, name, a, entry_a, b, entry_b, "Identifier names change, Python execution structure remains equivalent.")]


def _module_rename_case(work: Path) -> list[dict]:
    source = FIXTURES / "multimodule/pipeline"
    base = work / "module-renaming" / "baseline"
    base_package = base / "pipeline"
    variant = work / "module-renaming" / "variant"
    variant_package = variant / "streamline"
    shutil.copytree(source, base_package)
    variant_package.mkdir(parents=True)
    (variant_package / "__init__.py").write_text((source / "__init__.py").read_text(encoding="utf-8"), encoding="utf-8")
    rename_identifiers(source / "main.py", variant_package / "main.py", {})
    for old, new in (("parse.py", "decode_input.py"), ("validate.py", "check_input.py")):
        rename_identifiers(source / old, variant_package / new, {})
    main_path = variant_package / "main.py"
    text = main_path.read_text(encoding="utf-8").replace(".parse", ".decode_input").replace(".validate", ".check_input")
    main_path.write_text(text, encoding="utf-8", newline="")
    return [_compare(work, "module-renaming", base, "pipeline.main:start",
                     variant, "streamline.main:start",
                     "Package/module names and equivalent relative imports change together.")]


def _equivalent_expression_case(work: Path) -> list[dict]:
    source = FIXTURES / "analytics/metrics.py"
    a = work / "equivalent-expression" / "baseline" / source.name
    b = work / "equivalent-expression" / "variant" / source.name
    a.parent.mkdir(parents=True, exist_ok=True)
    b.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, a)
    text = source.read_text(encoding="utf-8").replace("if not cleaned:", "if len(cleaned) == 0:")
    original = source.read_text(encoding="utf-8")
    if text == original:
        raise AssertionError("Expected truthiness expression was not found in the fixture.")
    valid, variable, reason = empty_list_len_equivalence_preconditions(original, text)
    if not valid:
        return [{"id": "equivalent-expression", "status": "UNSUPPORTED",
                 "invariant": reason, "preconditions": {"valid": False}}]
    b.write_text(text, encoding="utf-8", newline="")
    return [_compare(work, "equivalent-expression", a, "metrics:summarize", b,
                     "metrics:summarize",
                     f"Equivalent empty-list predicate for statically known list {variable}; "
                     "ignore only the proven pure builtin len activity.",
                     ignored_pure_calls=("len",))]


def empty_list_len_equivalence_preconditions(source_a: str, source_b: str) -> tuple[bool, str, str]:
    """Prove the narrow preconditions for ``if not list_value`` == ``if len(list_value) == 0``.

    The value must be the immediate result of a list comprehension, the predicates
    must have the exact forms compared here, and ``len`` must not be rebound in
    the module. This bounds the metamorphic claim to Python's builtin list/len
    semantics; it does not generalize to arbitrary user objects.
    """
    try:
        tree_a, tree_b = ast.parse(source_a), ast.parse(source_b)
    except SyntaxError:
        return False, "Both variants must parse as Python", ""
    bound_len = any(
        (isinstance(node, ast.Name) and node.id == "len" and isinstance(node.ctx, ast.Store))
        or (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node.name == "len")
        or (isinstance(node, ast.arg) and node.arg == "len")
        or (isinstance(node, ast.alias) and (node.asname or node.name.split(".")[0]) == "len")
        for tree in (tree_a, tree_b) for node in ast.walk(tree)
    )
    if bound_len:
        return False, "The builtin name len is rebound", ""

    def predicate_nodes(tree):
        found = []
        for function in ast.walk(tree):
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for index, statement in enumerate(function.body[:-1]):
                if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
                    continue
                value = statement.value
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                if not isinstance(value, ast.ListComp) or len(targets) != 1 or not isinstance(targets[0], ast.Name):
                    continue
                following = function.body[index + 1]
                if isinstance(following, ast.If):
                    found.append((targets[0].id, following.test))
        return found

    left, right = predicate_nodes(tree_a), predicate_nodes(tree_b)
    for variable, test in left:
        if not (isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not)
                and isinstance(test.operand, ast.Name) and test.operand.id == variable):
            continue
        for other, candidate in right:
            if other != variable or not isinstance(candidate, ast.Compare):
                continue
            if (len(candidate.ops) == 1 and isinstance(candidate.ops[0], ast.Eq)
                    and len(candidate.comparators) == 1
                    and isinstance(candidate.left, ast.Call)
                    and isinstance(candidate.left.func, ast.Name)
                    and candidate.left.func.id == "len"
                    and len(candidate.left.args) == 1
                    and isinstance(candidate.left.args[0], ast.Name)
                    and candidate.left.args[0].id == variable
                    and isinstance(candidate.comparators[0], ast.Constant)
                    and candidate.comparators[0].value == 0):
                old_test = f"if not {variable}:"
                new_test = f"if len({variable}) == 0:"
                if source_a.replace(old_test, new_test, 1) != source_b:
                    return False, "Variants must differ only by the checked predicate rewrite", ""
                return True, "", variable
    return False, "Expected immediate list-comprehension binding followed by equivalent empty-list tests", ""


def _relocation_case(work: Path) -> list[dict]:
    source = FIXTURES / "workflow/approvals.py"
    a = work / "path-relocation" / "root-a" / "project" / source.name
    b = work / "path-relocation" / "root-b" / "moved" / source.name
    a.parent.mkdir(parents=True, exist_ok=True)
    b.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, a)
    shutil.copyfile(source, b)
    return [_compare(work, "path-relocation", a, "approvals:process_leave", b,
                     "approvals:process_leave", "Only the absolute source project path changes.")]


if __name__ == "__main__":
    raise SystemExit(main())
