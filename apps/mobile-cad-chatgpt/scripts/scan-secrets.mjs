import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { relative, resolve } from "node:path";

const repoRoot = execFileSync("git", ["rev-parse", "--show-toplevel"], { encoding: "utf8" }).trim();
const appRoot = fileURLToPath(new URL("../", import.meta.url));
const appScope = relative(repoRoot, appRoot).replaceAll("\\", "/");
const output = execFileSync(
  "git",
  [
    "ls-files", "--cached", "--others", "--exclude-standard", "--",
    appScope, ".github/workflows/mobile-cad-chatgpt.yml",
  ],
  { cwd: repoRoot, encoding: "utf8", maxBuffer: 16 * 1024 * 1024 },
);
const files = output.split(/\r?\n/).filter(Boolean);
const rules = [
  ["private-key", /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/],
  ["openai-key", /sk-(?:proj-)?[A-Za-z0-9_-]{20,}/],
  ["github-token", /(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})/],
  ["cloudflare-token", /CLOUDFLARE_API_TOKEN\s*[:=]\s*["']?[A-Za-z0-9_-]{20,}/i],
  ["aws-key", /AKIA[0-9A-Z]{16}/],
  ["local-user-path", /(?:[A-Za-z]:\\Users\\|\/(?:Users|home)\/)[^\s"']+/i],
];
const findings = [];

for (const file of files) {
  const path = resolve(repoRoot, file);
  let text;
  try { text = readFileSync(path, "utf8"); } catch { continue; }
  if (text.includes("\0")) continue;
  const lines = text.split(/\r?\n/);
  for (let index = 0; index < lines.length; index += 1) {
    for (const [name, pattern] of rules) {
      if (pattern.test(lines[index])) findings.push(`${file}:${index + 1} (${name})`);
      pattern.lastIndex = 0;
    }
  }
}

if (findings.length) throw new Error(`Potential secret or local path found (values redacted):\n${findings.join("\n")}`);
console.log(`Secret scan passed: ${files.length} tracked/unignored files checked; values were never printed.`);
