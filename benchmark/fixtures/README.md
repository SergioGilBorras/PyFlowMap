# Cross-domain benchmark programs

The 15 baseline Python fixtures cover commerce, ETL, CLI, network, IoT,
resources, predicates, scheduling, recursion, security, workflow,
multi-module import resolution, plugins, analytics and inheritance.

The canonical runner discovers these programs using
`../cases.json`. Source programs must not be imported or executed by the
benchmark. Only the analyzers' AST traversal and artifact generation run.

```bash
python -m benchmark.runners.run --output pyflowmap-output/baseline --render
```

Keep fixtures source-stable; derived diagrams belong under ignored
`pyflowmap-output/` and are excluded from packages.
