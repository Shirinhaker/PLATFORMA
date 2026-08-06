import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { loadApiBaseUrl } from "../api/runtime-base-url";
import { AdminApiClient } from "./admin-client";
import { AdminApp } from "./AdminApp";


const container = document.getElementById("admin-root");

async function start() {
  if (!container) return;
  const root = createRoot(container);
  try {
    const baseUrl = await loadApiBaseUrl();
    root.render(
      <StrictMode>
        <AdminApp api={new AdminApiClient(baseUrl)} />
      </StrictMode>,
    );
  } catch (error) {
    container.textContent = error instanceof Error
      ? error.message
      : "API manzili sozlanmagan.";
  }
}

void start();
