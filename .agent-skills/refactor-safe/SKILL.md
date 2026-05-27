# Safe Refactor Skill

Use this skill for refactoring.

Rules:
- Do not change behavior unless requested.
- Use Serena for symbol references.
- Use ast-grep for structural transformations.
- Avoid broad formatting changes.
- Keep refactor small and reversible.
- Run tests before and after if possible.
- Inspect git diff carefully.

Required output:
- what behavior should remain unchanged
- files touched
- verification result
- rollback plan
