import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";


type PreviewEnvironment = Record<string, string | undefined>;


export const KOPRIK_PREVIEW_ALLOWED_HOSTS = Object.freeze([
  ".railway.app",
  ".koprik.uz",
]);


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
    build: {
      rollupOptions: {
        // Admin paneli alohida sayt: foydalanuvchi ilovasi bilan
        // bitta JS to'plamda bo'lmaydi.
        input: {
          main: "index.html",
          admin: "admin.html",
        },
        output: {
          manualChunks(id) {
            if (id.includes("node_modules/leaflet")) return "vendor-map";
            if (id.includes("node_modules/react")) return "vendor-react";
            return undefined;
          },
        },
      },
    },
    ...(apiTarget ? {
      preview: {
        allowedHosts: [...KOPRIK_PREVIEW_ALLOWED_HOSTS],
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
      // Keng paritet testlari bitta testda o'nlab ekranni to'liq
      // render qiladi. 5 soniyalik standart chegara to'plam parallel
      // ishlaganda yetmay qoladi va test tasodifiy yiqiladi.
      testTimeout: 20000,
    },
  };
});
