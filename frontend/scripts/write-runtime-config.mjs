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
const railwayBuild = Boolean(
  process.env.RAILWAY_SERVICE_NAME
  || process.env.RAILWAY_ENVIRONMENT_NAME
  || process.env.RAILWAY_PROJECT_ID,
);


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
if (railwayBuild && !apiBaseUrl) {
  throw new Error(
    "KOPRIK_API_BASE_URL is required for Railway frontend deployment",
  );
}

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
