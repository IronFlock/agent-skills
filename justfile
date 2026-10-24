# Default recipe: show available commands when `just` is run with no args.
default:
    @just --list

# Lint as CI runs it (non-mutating): ruff.
lint:
    uvx ruff@0.14.0 check .

# The validator's regression tests and the starter app (PyYAML and jsonschema,
# the validator's two dependencies, pinned in a throwaway environment).
test:
    uv run --no-project --python 3.13 --with pyyaml==6.0.3 --with jsonschema==4.25.1 -- python -I tests/run.py

# Reload the ironflock plugin in the local Claude Code from GitHub (pushed commits
# only). Running sessions pick it up after /reload-plugins or a restart.
refresh-plugin:
    claude plugin marketplace update ironflock
    claude plugin update ironflock@ironflock --scope user
