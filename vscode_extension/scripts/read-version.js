import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..", "..");

const version = readFileSync(join(root, "VERSION"), "utf8").trim();
const pkgPath = join(__dirname, "..", "package.json");

let pkg;
try {
  pkg = JSON.parse(readFileSync(pkgPath, "utf8"));
} catch {
  console.error(`Failed to parse ${pkgPath}`);
  process.exit(1);
}

if (pkg.version !== version) {
  pkg.version = version;
  writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + "\n");
  console.log(`Updated package.json version to ${version}`);
} else {
  console.log(`package.json version already ${version}`);
}
