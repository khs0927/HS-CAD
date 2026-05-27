# Verification Policy

Every code change needs verification.

Choose verification based on project type and changed files.

## General

Before final response:
- run available tests if practical
- run typecheck if available
- run lint if available
- run build if relevant
- inspect git diff
- report exact commands and results

If verification cannot be run:
- explain why
- provide the command the user should run
- do not claim full success

## Failure loop

If verification fails:
1. Read the error.
2. Identify the root cause.
3. Make a minimal fix.
4. Rerun the failed command.
5. Report remaining failures if unresolved.

## Do not hide failures

Never say “done” when:
- tests failed
- build failed
- lint failed
- typecheck failed
- UI could not load
- git diff was not inspected
