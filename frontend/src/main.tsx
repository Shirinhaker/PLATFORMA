import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { ApiClient } from "./api/client";
import {
  ApiConfigurationError,
  loadApiBaseUrl,
} from "./api/runtime-base-url";
import { App } from "./app/App";
import { resolveAdminEntryRedirect } from "./app/entry-routing";
import { resolveAuthContext } from "./auth/adapter";
import "./profiles/BusinessOnlineEditingViews.css";
// Biznes kabinet lazy route bo'lsa ham uning asosiy CSS tartibi buildga
// bog'lanmasin. Eski, ishlatilmaydigan V2 stylesheet bilan selectorlar
// to'qnashuvi kabinet dizaynini productionda buzgan edi.
import "./profiles/Cabinet.css";
import "./profiles/BusinessCabinetDashboardParity.css";
import "./profiles/BusinessFollowCounts.css";


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


const adminEntryRedirect = resolveAdminEntryRedirect(window.location);
if (adminEntryRedirect) {
  window.location.replace(adminEntryRedirect);
} else {
  void bootstrap();
}
