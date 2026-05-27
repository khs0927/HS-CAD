# Dependency Policy

Do not add new dependencies casually.

Before installing or adding a package:
1. Explain why it is needed.
2. Check whether an existing dependency can solve the problem.
3. Check current docs using Context7 if relevant.
4. Consider maintenance and security risk.
5. Consider bundle size or runtime cost.
6. Ask for approval if it affects production, security, billing, auth, or deployment.

Never:
- add large frameworks for small tasks
- add abandoned packages
- add packages that require secrets without documenting env vars
- run unknown install scripts without review
