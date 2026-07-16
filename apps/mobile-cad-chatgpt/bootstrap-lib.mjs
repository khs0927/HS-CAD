import { createHash } from "node:crypto";
import { isAbsolute, relative, resolve, sep } from "node:path";
import { gunzipSync } from "node:zlib";

const PAYLOAD_PART_PATTERN = /^part-\d+(?:-\d+)*\.txt$/;
const WINDOWS_ABSOLUTE_PATTERN = /^(?:[A-Za-z]:[\\/]|\\\\)/;

export function selectPayloadParts(names) {
  if (!Array.isArray(names)) {
    throw new TypeError("payload part names must be an array");
  }

  const selected = names
    .filter((name) => typeof name === "string" && name.endsWith(".txt"))
    .sort();

  if (selected.length === 0) {
    throw new Error("no payload parts found");
  }

  for (const name of selected) {
    if (!PAYLOAD_PART_PATTERN.test(name)) {
      throw new Error(`unexpected payload part name: ${name}`);
    }
  }

  if (new Set(selected).size !== selected.length) {
    throw new Error("duplicate payload part name detected");
  }

  return selected;
}

export function decodePayload(payload) {
  if (typeof payload !== "string" || payload.trim() === "") {
    throw new Error("payload is empty");
  }

  const normalized = payload.replace(/\s+/g, "");
  if (!/^[A-Za-z0-9+/]*={0,2}$/.test(normalized) || normalized.length % 4 === 1) {
    throw new Error("payload is not valid base64");
  }

  let decoded;
  try {
    decoded = gunzipSync(Buffer.from(normalized, "base64")).toString("utf8");
  } catch (error) {
    throw new Error(`payload decompression failed: ${error.message}`);
  }

  let files;
  try {
    files = JSON.parse(decoded);
  } catch (error) {
    throw new Error(`payload JSON is invalid: ${error.message}`);
  }

  if (files === null || Array.isArray(files) || typeof files !== "object") {
    throw new Error("payload root must be an object of file paths and contents");
  }

  const entries = Object.entries(files);
  if (entries.length === 0) {
    throw new Error("payload does not contain source files");
  }
  for (const [path, content] of entries) {
    if (typeof path !== "string" || path.trim() === "") {
      throw new Error("payload contains an empty file path");
    }
    if (typeof content !== "string") {
      throw new Error(`payload content must be UTF-8 text: ${path}`);
    }
  }

  return {
    files,
    digest: createHash("sha256").update(normalized).digest("hex"),
  };
}

export function resolveOutputPath(appRoot, candidate) {
  if (typeof appRoot !== "string" || appRoot.trim() === "") {
    throw new Error("app root is required");
  }
  if (typeof candidate !== "string" || candidate.trim() === "") {
    throw new Error("payload file path is required");
  }

  const normalizedCandidate = candidate.replaceAll("\\", "/");
  if (
    isAbsolute(normalizedCandidate) ||
    WINDOWS_ABSOLUTE_PATTERN.test(candidate) ||
    normalizedCandidate.includes("\0")
  ) {
    throw new Error(`absolute payload path is forbidden: ${candidate}`);
  }

  const root = resolve(appRoot);
  const target = resolve(root, normalizedCandidate);
  const relativePath = relative(root, target);
  if (
    relativePath === "" ||
    relativePath === ".." ||
    relativePath.startsWith(`..${sep}`) ||
    isAbsolute(relativePath)
  ) {
    throw new Error(`payload path escapes app root: ${candidate}`);
  }

  return target;
}
