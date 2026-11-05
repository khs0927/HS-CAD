import { readFile, readdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const nodeModules = fileURLToPath(new URL("../node_modules/", import.meta.url));
const allowedTokens = new Set([
  "0BSD", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "CC0-1.0",
  "CC-BY-4.0", "ISC", "LGPL-3.0-or-later", "MIT", "MPL-2.0",
  "Python-2.0", "Unlicense", "Unicode-3.0",
  "BlueOak-1.0.0",
]);
const forbidden = /(?:^|\W)(?:AGPL|GPL|SSPL|BUSL|Commons-Clause|UNLICENSED)(?:$|\W)/i;

async function packageFiles(directory) {
  const files = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    if (entry.name === ".bin") continue;
    const path = join(directory, entry.name);
    if (!entry.isDirectory()) continue;
    if (entry.name.startsWith("@")) {
      files.push(...await packageFiles(path));
      continue;
    }
    const manifest = join(path, "package.json");
    try {
      const parsed = JSON.parse(await readFile(manifest, "utf8"));
      if (parsed.name && parsed.version) files.push({ manifest, parsed });
    } catch {
      // Not a package root; nested package managers may still place children here.
    }
    const nested = join(path, "node_modules");
    try { files.push(...await packageFiles(nested)); } catch { /* no nested node_modules */ }
  }
  return files;
}

const packages = await packageFiles(nodeModules);
const unique = new Map(packages.map(({ parsed }) => [`${parsed.name}@${parsed.version}`, parsed]));
const errors = [];
const summary = new Map();

for (const [id, manifest] of [...unique].sort(([a], [b]) => a.localeCompare(b))) {
  const raw = Array.isArray(manifest.licenses)
    ? manifest.licenses.map((item) => typeof item === "string" ? item : item?.type).filter(Boolean).join(" OR ")
    : (typeof manifest.license === "string" ? manifest.license : manifest.license?.type);
  const license = raw?.trim();
  if (!license) {
    errors.push(`${id}: missing license metadata`);
    continue;
  }
  summary.set(license, (summary.get(license) ?? 0) + 1);
  if (forbidden.test(license)) {
    errors.push(`${id}: disallowed license ${license}`);
    continue;
  }
  const tokens = license.match(/[A-Za-z0-9.-]+/g) ?? [];
  const meaningful = tokens.filter((token) => !["AND", "OR", "WITH"].includes(token));
  if (meaningful.length && !meaningful.some((token) => allowedTokens.has(token))) {
    errors.push(`${id}: unreviewed license ${license}`);
  }
}

console.log(`Reviewed ${unique.size} installed packages.`);
for (const [license, count] of [...summary].sort(([a], [b]) => a.localeCompare(b))) {
  console.log(`${license}: ${count}`);
}
if (errors.length) throw new Error(`License review failed:\n${errors.join("\n")}`);
