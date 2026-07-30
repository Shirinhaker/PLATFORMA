import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";


const outputPath = fileURLToPath(
  new URL("../public/runtime-config.json", import.meta.url),
);
const rawValue = (
  process.env.KOPRIK_API_BASE_URL
  || process.env.VITE_API_BASE_URL
  || process.env.API_BASE_URL
  || ""
).trim();


function normalizeHttpsOrigin(value) {
  if (!value) return "";
  const parsed = new URL(value);
  if (parsed.protocol !== "https:") {
    throw new Error("runtime_api_origin_must_use_https");
  }
  if (parsed.pathname !== "/" || parsed.search || parsed.hash) {
    throw new Error("runtime_api_origin_must_be_an_origin");
  }
  return parsed.origin;
}


const apiBaseUrl = normalizeHttpsOrigin(rawValue);
await mkdir(path.dirname(outputPath), { recursive: true });
await writeFile(
  outputPath,
  `${JSON.stringify({ apiBaseUrl }, null, 2)}\n`,
  "utf8",
);

console.log(
  apiBaseUrl
    ? `runtime-config.json generated for ${apiBaseUrl}`
    : "runtime-config.json generated without API origin",
);
