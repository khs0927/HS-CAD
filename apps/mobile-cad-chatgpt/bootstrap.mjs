import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

import {
  decodePayload,
  resolveOutputPath,
  selectPayloadParts,
} from "./bootstrap-lib.mjs";

const appRoot = dirname(fileURLToPath(import.meta.url));
const payloadDirectory = new URL("./payload/", import.meta.url);
const partNames = selectPayloadParts(await readdir(payloadDirectory));
const payload = (
  await Promise.all(
    partNames.map((name) => readFile(new URL(`./payload/${name}`, import.meta.url), "utf8")),
  )
).join("");
const { files, digest } = decodePayload(payload);

for (const [path, content] of Object.entries(files).sort(([left], [right]) => left.localeCompare(right))) {
  // Keep repository-level ignore rules managed by Git. Older payloads may
  // contain a stale .gitignore and must not overwrite deployment safeguards.
  if (path === ".gitignore") {
    continue;
  }
  const target = resolveOutputPath(appRoot, path);
  await mkdir(dirname(target), { recursive: true });
  await writeFile(target, content, "utf8");
}

console.log(
  `HS-CAD mobile v0.2 source prepared (${Object.keys(files).length} files, payload sha256 ${digest.slice(0, 12)}).`,
);
