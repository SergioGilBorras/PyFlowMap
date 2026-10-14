# Oracle regression fixtures

Small Python AST programs that verify an evaluator rejects impossible
control-flow edges while permitting valid graph paths.

- `match-guards/`: pattern checks, capture binding and guards.
- `match-dispatch/`: independent match statements, guards and module-name
  disambiguation.
- `python-semantics/`: returns, exceptions, context managers and branching.

These are **current regression inputs**. The source is parsed, not executed.
The files were reorganized by semantic topic to remove obsolete phase
directories. Results go to ignored output folders; changes to fixture
source need an explicit new semantic criterion.
