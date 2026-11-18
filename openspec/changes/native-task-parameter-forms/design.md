# Native task parameter form design

Introspect the publicly vendored IkaBot Python AST without importing task modules. For each @task-decorated function collect a bounded list of keyword arguments and whether a safe literal default exists. Infer primitive form types only from simple built-in defaults/annotations. Unknown or nested parameters use a JSON field and are still checked by the actual engine.

The GUI rebuilds a form on task selection. Editing a form field marks the draft dirty; the operator must explicitly press Build JSON from fields, then review the resulting editor before the pre-existing two-step task confirmation. Advanced JSON remains available for existing IkaBot config exports and complex modules.

Backend task start still checks registered task names, validated configuration, explicit confirmation, account identity, idempotency and IPC engine-side parameter validation. No source code execution occurs during introspection.
