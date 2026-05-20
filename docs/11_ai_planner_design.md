# AI Planner Design

The AI Planner must never produce executable Python, AutoLISP, shell, or arbitrary CAD script code. It may only output JSON commands accepted by the Pydantic command validator.

## Flow

```text
Natural language -> prompt template -> JSON command or command_batch -> validation -> safety guard -> dry-run -> execution
```

## Rules

- Output JSON only.
- Unknown requests return `unsupported_command` or `ask_clarification`.
- Dangerous commands require backup and preview.
- XiCAD aliases must exist in the safe alias catalog.
- Interactive XiCAD commands must warn users.

See `src/ai/prompts.py` for the canonical prompt fragments.
