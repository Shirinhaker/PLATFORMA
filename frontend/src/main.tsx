import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { ApiClient } from "./api/client";
import {
  ApiConfigurationError,
  loadApiBaseUrl,
} from "./api/runtime-base-url";
import { App } from "./app/App";
import { resolveAuthContext } from "./auth/adapter";
import "./profiles/BusinessProfileV2.css";


const rootElement = document.getElementById("root");
if (rootElement === null) {
  throw new Error("Frontend root elementi topilmadi.");
}
const root = rootElement;


function renderConfigurationError(error: unknown) {
  const code = error instanceof ApiConfigurationError
    ? error.code
    : "api_bootstrap_failed";
  createRoot(root).render(
    <StrictMode>
      <main className="session-panel session-panel--message" role="alert">
        <p>API konfiguratsiyasi topilmadi.</p>
        <small>Xato kodi: {code}</small>
      </main>
    </StrictMode>,
  );
}


async function bootstrap() {
  try {
    const apiBaseUrl = await loadApiBaseUrl();
    const api = new ApiClient(
      apiBaseUrl,
      window.fetch.bind(window),
      resolveAuthContext(),
    );
    createRoot(root).render(
      <StrictMode>
        <App api={api} />
      </StrictMode>,
    );
  } catch (error) {
    renderConfigurationError(error);
  }
}


void bootstrap();
