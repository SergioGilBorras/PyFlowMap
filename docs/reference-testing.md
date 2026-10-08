# Immutable reference cases (read-only source projects)

The project under test is **not modified**. GitHub references are fixed to a
full commit SHA. Every reference snapshot is vendored as plain Python source
under `tests/fixtures/references/`, so regression tests work offline, even
when the GitHub source repository is private or its `main` branch advances.

## P4-Planning-Agent V1

- Original repository: `SergioGilBorras/P4-Planning-Agent`
- Commit: `8e68c720bef75e24acd6b3ed8a237b41fa3a838d`
- Fixture: `tests/fixtures/references/p4-planning-agent-v1/`
- Scope: application Python files only, no secrets, tests, or `.env` files
- Entry: `planning.coordinator:PlanningCoordinator.plan`
- Core regression: two branch labels with correct predicate polarity, one
  shared return, activity initial/final, no invented continuation from a return.

Run locally after installing `pip install -e '.[dev]'`:

```bash
pytest -q
pyflowmap analyze tests/fixtures/references/p4-planning-agent-v1 \
  --entry planning.coordinator:PlanningCoordinator.plan \
  --language es --diagram-type activity --format all --renderer graphviz \
  --output examples/results/p4-planning-agent-v1-1/
```

## Future P4-Planning-Agent V2

When the P4 pipeline changes, record its **new full commit SHA**, place a new
snapshot under `tests/fixtures/references/p4-planning-agent-v2/`, and **leave
V1 untouched**. Run the same tests and compare the generated diagrams for both
versions. A local Git clone can also check out either commit into a disposable
folder; never checkout or write into the user's working P4 project.

The fixture manifest records Git blob hashes so alterations to pinned snapshots
are caught by tests. These hashes are calculated from the raw file contents
using the standard Git blob algorithm.
