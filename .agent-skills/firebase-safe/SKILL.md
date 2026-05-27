# Firebase Safe Skill

Use this skill for Firebase work.

Rules:
- Inspect firebase.json, firestore.rules, storage.rules, functions package first.
- Do not deploy unless explicitly requested.
- Do not expose service account JSON.
- Do not print .env values.
- Use emulators when possible.
- Treat rules, auth, billing, and production config as protected.
- Use read-only inspection first.

Verification:
- functions lint/build/test if available
- emulator notes if available
- rules risk notes
