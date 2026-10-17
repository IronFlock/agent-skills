# Default recipe: show available commands when `just` is run with no args.
default:
    @just --list

# Reload the ironflock plugin in the local Claude Code from GitHub (pushed commits
# only). Running sessions pick it up after /reload-plugins or a restart.
refresh-plugin:
    claude plugin marketplace update ironflock
    claude plugin update ironflock@ironflock --scope user
