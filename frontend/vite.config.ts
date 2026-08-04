import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";


type PreviewEnvironment = Record<string, string | undefined>;


export function resolvePreviewApiTarget(
  environment: PreviewEnvironment,
): string {
  const rawValue = (
    environment.KOPRIK_API_BASE_URL
    || environment.VITE_API_BASE_URL
    || environment.API_BASE_URL
    || ""
  ).trim();
  if (!rawValue) return "";

  const target = new URL(rawValue);
  if (target.protocol !== "https:") {
    throw new Error("preview_api_proxy_target_must_use_https");
  }
  if (target.pathname !== "/" || target.search || target.hash) {
    throw new Error("preview_api_proxy_target_must_be_an_origin");
  }
  return target.origin;
}


export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, ".", [
    "KOPRIK_API_BASE_URL",
    "VITE_API_BASE_URL",
    "API_BASE_URL",
  ]);
  const apiTarget = resolvePreviewApiTarget(environment);

  return {
    plugins: [react()],
    ...(apiTarget ? {
      preview: {
        proxy: {
          "/api": {
            target: apiTarget,
            changeOrigin: true,
            secure: true,
          },
        },
      },
    } : {}),
    test: {
      environment: "jsdom",
      setupFiles: "./src/test/setup.ts",
      // v1656 paritet testlari bitta testda o'nlab ekranni to'liq
      // render qiladi. 5 soniyalik standart chegara to'plam parallel
      // ishlaganda yetmay qoladi va test tasodifiy yiqiladi.
      testTimeout: 20000,
    },
  };
});
