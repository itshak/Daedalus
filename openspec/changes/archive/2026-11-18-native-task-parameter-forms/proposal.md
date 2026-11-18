# Generate native task parameter forms from the public engine registry

## Why
Daedalus can launch all discovered background operations using JSON, but operators must guess parameter names/types. The native Tasks page should present a useful field editor without inventing new game logic or bypassing engine validation.

## What changes
- Extend offline AST-based engine introspection to report bounded safe parameter name, required-state, primitive type and literal default metadata for built-in IkaBot background tasks only.
- Render a dynamic native form for the selected task with booleans, numbers, text and JSON fields, keeping an advanced JSON editor for nested configurations.
- Build explicit JSON from fields for operator review; do not launch until existing checkbox, confirmation dialog, authenticated API and engine schema checks succeed.
- Add tests for all known public tasks, required fields, unsafe JSON and task selection/reset behavior.

## Modified capabilities
- `engine-integration`: offline parameter metadata discovery
- `desktop-client`: forms for every registered task with advanced JSON fallback

## Non-goals
No default engine operations, no guesswork about runtime game state, no automatic task dispatch, and no claim that every complex upstream parameter can be represented as a simple scalar.
