import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const portalRoot = resolve(__dirname, "..");
const srcJson = resolve(portalRoot, "..", "data", "portal_snapshot.json");
const dstJson = resolve(portalRoot, "src", "data", "portal_snapshot.json");

if (existsSync(srcJson)) {
  mkdirSync(dirname(dstJson), { recursive: true });
  copyFileSync(srcJson, dstJson);
  console.log("[sync-data] Copied ../data/portal_snapshot.json -> src/data/portal_snapshot.json");
} else if (existsSync(dstJson)) {
  console.log("[sync-data] Using committed src/data/portal_snapshot.json");
} else {
  console.error("[sync-data] ERROR: portal_snapshot.json not found");
  process.exit(1);
}
