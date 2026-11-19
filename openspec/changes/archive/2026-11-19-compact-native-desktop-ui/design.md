# Design: table-first, progressive disclosure

- Qt/Fluent remains the rendering stack. Keep semantic Qt controls and a single shared compact table factory.
- Mac visual hierarchy: 16–20px page inset, 8–10px vertical rhythm, 34px data rows, concise page titles, restrained system blue and neutral backgrounds for both themes.
- Accounts: one table expands to fill available space. Always-available Add, refresh, report inclusion and all-account sign-in; selection-sensitive editing, one-account sign-in, assistance and expert recovery are compact or in More.
- Warehouses: all-account report first, selected subset and one-account actions alongside print/export. Preserve unknown/zero distinction and account-specific partial failures.
- Automations: simple form and task selector first; opt-in gallery, JSON and separate history/running screens. Preserve readiness and explicit review.
- Overview: short action rows instead of oversized explanatory cards; runtime state remains truthful.
- Tooltips and accessible descriptions retain explanations hidden from the default visual path. No icon-only destructive actions, no new game effects.
