import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const deployScriptUrl = new URL("./scripts/deploy_and_verify.ps1", import.meta.url);
const gitignoreUrl = new URL("./.gitignore", import.meta.url);
const handoffUrl = new URL("./CODEX_HANDOFF_CLOUDFLARE_CHATGPT_APP.md", import.meta.url);

test("deployment script preserves the required validation and health gates", async () => {
  const script = await readFile(deployScriptUrl, "utf8");
  for (const required of [
    "npm run validate:ci",
    "wrangler whoami",
    "wrangler deploy",
    "/health",
    "ok -ne $true",
    "CODEX_DEPLOYMENT_RESULT.md",
  ]) {
    assert.ok(script.includes(required), `missing deployment gate: ${required}`);
  }
});

test("local account and deployment artifacts are ignored", async () => {
  const gitignore = await readFile(gitignoreUrl, "utf8");
  assert.match(gitignore, /^deployment-logs\/$/m);
  assert.match(gitignore, /^CODEX_DEPLOYMENT_RESULT\.md$/m);
  assert.match(gitignore, /^\.dev\.vars$/m);
});

test("Codex handoff prohibits unsafe publish actions", async () => {
  const handoff = await readFile(handoffUrl, "utf8");
  for (const required of [
    "Do not merge PR #127",
    "Do not submit the app publicly",
    "Do not expose account credentials or tokens",
    "Keep it private/internal",
  ]) {
    assert.ok(handoff.includes(required), `missing handoff guardrail: ${required}`);
  }
});
