import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { dirname } from "node:path";
import { gunzipSync } from "node:zlib";

const partNames = (await readdir(new URL("./payload/", import.meta.url))).filter((name) => name.endsWith(".txt")).sort();
const payload = (await Promise.all(partNames.map((name) => readFile(new URL(`./payload/${name}`, import.meta.url), "utf8")))).join("");
const files = JSON.parse(gunzipSync(Buffer.from(payload, "base64")).toString("utf8"));
for (const [path, content] of Object.entries(files)) {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, content, "utf8");
}
console.log(`HS-CAD mobile v0.2 source prepared (${Object.keys(files).length} files).`);
