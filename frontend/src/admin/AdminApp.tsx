import { useEffect, useState } from "react";

import type { AdminApiClient } from "./admin-client";
import { AdminAccounts } from "./AdminAccounts";
import { AdminAudit } from "./AdminAudit";
import { AdminLogin } from "./AdminLogin";
import { AdminPayments } from "./AdminPayments";
import { AdminPricing } from "./AdminPricing";
import { AdminReports } from "./AdminReports";
import "./admin.css";


type Page = "payments" | "pricing" | "accounts" | "reports" | "audit";

type Props = { api: AdminApiClient };

// Faqat tayyor bo'limlar ko'rsatiladi — ishlamaydigan menyu qoldirilmaydi.
const PAGES: ReadonlyArray<{ key: Page; icon: string; label: string }> = [
  { key: "payments", icon: "₿", label: "To‘lovlar" },
  { key: "pricing", icon: "₸", label: "Narxlar va usullar" },
  { key: "accounts", icon: "♙", label: "Profil va bizneslar" },
  { key: "reports", icon: "⚑", label: "Shikoyatlar" },
  { key: "audit", icon: "≡", label: "Audit tarixi" },
];


export function AdminApp({ api }: Props) {
  const [adminId, setAdminId] = useState<number | null>(null);
  const [checking, setChecking] = useState(true);
  const [page, setPage] = useState<Page>("payments");

  useEffect(() => {
    let active = true;
    api.me()
      .then((identity) => {
        if (active) setAdminId(identity.telegram_user_id);
      })
      .catch(() => {
        if (active) setAdminId(null);
      })
      .finally(() => {
        if (active) setChecking(false);
      });
    return () => { active = false; };
  }, [api]);

  if (checking) {
    return <div className="admin-boot">Yuklanmoqda…</div>;
  }

  if (adminId === null) {
    return <AdminLogin api={api} onSignedIn={setAdminId} />;
  }

  return (
    <div className="admin-app">
      <header className="topbar">
        <div className="topbar-brand">
          <span className="brand-mark">K</span>
          <strong>Ko‘prik</strong>
          <small>ADMIN</small>
        </div>
        <div className="topbar-actions">
          <span className="admin-id">{adminId}</span>
          <button
            type="button"
            className="secondary compact"
            onClick={() => {
              void api.logout().finally(() => setAdminId(null));
            }}
          >
            Chiqish
          </button>
        </div>
      </header>

      <div className="app-grid">
        <aside className="sidebar" aria-label="Admin bo‘limlari">
          <nav>
            {PAGES.map((entry) => (
              <button
                key={entry.key}
                type="button"
                className={`nav-item${page === entry.key ? " active" : ""}`}
                aria-current={page === entry.key ? "page" : undefined}
                onClick={() => setPage(entry.key)}
              >
                <span>{entry.icon}</span>
                {entry.label}
              </button>
            ))}
          </nav>
          <div className="sidebar-note">
            Barcha o‘zgarishlar audit tarixiga yoziladi.
          </div>
        </aside>

        <main className="workspace">
          {page === "payments" ? <AdminPayments api={api} /> : null}
          {page === "pricing" ? <AdminPricing api={api} /> : null}
          {page === "accounts" ? <AdminAccounts api={api} /> : null}
          {page === "reports" ? <AdminReports api={api} /> : null}
          {page === "audit" ? <AdminAudit api={api} /> : null}
        </main>
      </div>
    </div>
  );
}
