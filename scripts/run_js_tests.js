#!/usr/bin/env node
// Runs the tests for the rules the pages count with. The files are found here so the command
// does not depend on a shell expanding a pattern.
import { readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const root = fileURLToPath(new URL("../tests", import.meta.url));

function testsIn(dir) {
  const found = [];
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) {
      found.push(...testsIn(path));
    } else if (entry.endsWith(".test.mjs")) {
      found.push(path);
    }
  }
  return found;
}

const files = testsIn(root);
if (!files.length) {
  console.error("no tests found under tests/");
  process.exit(1);
}

const result = spawnSync(process.execPath, ["--test", ...files], { stdio: "inherit" });
process.exit(result.status ?? 1);
