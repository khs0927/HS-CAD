import assert from "node:assert/strict";
import { gzipSync } from "node:zlib";
import test from "node:test";

import {
  decodePayload,
  resolveOutputPath,
  selectPayloadParts,
} from "./bootstrap-lib.mjs";

test("payload parts are validated and sorted deterministically", () => {
  assert.deepEqual(
    selectPayloadParts(["part-010.txt", "notes.md", "part-002-001.txt", "part-001.txt"]),
    ["part-001.txt", "part-002-001.txt", "part-010.txt"],
  );
  assert.throws(
    () => selectPayloadParts(["source.txt"]),
    /unexpected payload part name/,
  );
});

test("payload decoding validates gzip JSON and returns a stable digest", () => {
  const encoded = gzipSync(
    Buffer.from(JSON.stringify({ "src/index.ts": "export const ready = true;\n" }), "utf8"),
  ).toString("base64");

  const first = decodePayload(encoded);
  const second = decodePayload(encoded);

  assert.equal(first.files["src/index.ts"], "export const ready = true;\n");
  assert.match(first.digest, /^[a-f0-9]{64}$/);
  assert.equal(first.digest, second.digest);
  assert.throws(() => decodePayload("not base64!"), /valid base64/);
});

test("output paths remain inside the mobile app root", () => {
  const root = "/workspace/apps/mobile-cad-chatgpt";

  assert.equal(
    resolveOutputPath(root, "src/index.ts"),
    "/workspace/apps/mobile-cad-chatgpt/src/index.ts",
  );
  assert.throws(() => resolveOutputPath(root, "../outside.txt"), /escapes app root/);
  assert.throws(() => resolveOutputPath(root, "/tmp/outside.txt"), /absolute payload path/);
  assert.throws(() => resolveOutputPath(root, "C:\\temp\\outside.txt"), /absolute payload path/);
  assert.throws(() => resolveOutputPath(root, "\\\\server\\share\\outside.txt"), /absolute payload path/);
});
