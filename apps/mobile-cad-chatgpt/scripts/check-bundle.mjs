import { readFile, readdir, stat } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { join, relative } from "node:path";

const root = fileURLToPath(new URL("../dist/", import.meta.url));
const maxHtmlBytes = 1_000_000;
const maxTotalBytes = 2_000_000;
const forbidden = [
  { name: "source map", test: (name) => name.endsWith(".map") },
  { name: "local Windows path", pattern: /[A-Za-z]:\\Users\\/i },
  { name: "local Unix path", pattern: /\/(?:Users|home)\/[^/\s]+\//i },
  { name: "private key", pattern: /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/ },
  { name: "OpenAI key", pattern: /sk-(?:proj-)?[A-Za-z0-9_-]{20,}/ },
  { name: "GitHub token", pattern: /(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})/ },
];

async function filesIn(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await filesIn(path));
    else files.push(path);
  }
  return files;
}

const files = await filesIn(root);
if (!files.length) throw new Error("dist is empty; run npm run build first");

let totalBytes = 0;
for (const file of files) {
  const info = await stat(file);
  const name = relative(root, file).replaceAll("\\", "/");
  totalBytes += info.size;
  for (const rule of forbidden) {
    if (rule.test?.(name)) throw new Error(`${rule.name} found: ${name}`);
  }
  if (/\.(?:html|js|css|json|webmanifest|svg)$/i.test(name)) {
    const text = await readFile(file, "utf8");
    for (const rule of forbidden) {
      if (rule.pattern?.test(text)) throw new Error(`${rule.name} found in ${name}`);
    }
  }
  if (name.endsWith(".html") && info.size > maxHtmlBytes) {
    throw new Error(`${name} is ${info.size} bytes; limit is ${maxHtmlBytes}`);
  }
}

if (totalBytes > maxTotalBytes) {
  throw new Error(`dist is ${totalBytes} bytes; limit is ${maxTotalBytes}`);
}

const index = await readFile(new URL("../dist/index.html", import.meta.url), "utf8");
if (/<script\b[^>]*\bsrc=/i.test(index) || /<link\b[^>]*\brel=["']stylesheet["']/i.test(index)) {
  throw new Error("index.html is not self-contained");
}

console.log(`Bundle check passed: ${files.length} files, ${totalBytes} bytes total, index.html ${Buffer.byteLength(index)} bytes.`);
