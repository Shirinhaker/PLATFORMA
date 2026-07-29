import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { ApiClient } from "./api/client";
import { resolveApiBaseUrl } from "./api/runtime-base-url";
import { App } from "./app/App";
import { resolveAuthContext } from "./auth/adapter";


const api = new ApiClient(
  resolveApiBaseUrl(import.meta.env.VITE_API_BASE_URL),
  window.fetch.bind(window),
  resolveAuthContext(),
);
const root = document.getElementById("root");
if (root === null) {
  throw new Error("Frontend root elementi topilmadi.");
}
createRoot(root).render(
  <StrictMode>
    <App api={api} />
  </StrictMode>,
);
