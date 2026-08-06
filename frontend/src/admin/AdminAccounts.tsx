import { useState } from "react";

import type {
  AdminAccountDetail,
  AdminAccountRow,
  AdminApiClient,
} from "./admin-client";


export type AdminAccountsApi = Pick<
  AdminApiClient,
  "accounts" | "account" | "restrict" | "unrestrict" | "addNote"
>;

type Props = { api: AdminAccountsApi };

const RESTRICTION_TEXT: Record<string, string> = {
  content_hidden: "Publicdan yashirilgan",
  account_blocked: "Bloklangan",
};

function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

function stamp(seconds: number) {
  if (!seconds) return "—";
  const at = new Date(seconds * 1000);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${pad(at.getDate())}.${pad(at.getMonth() + 1)}.${at.getFullYear()}`;
}


export function AdminAccounts({ api }: Props) {
  const [actorType, setActorType] = useState<"user" | "business">("business");
  const [query, setQuery] = useState("");
  const [restriction, setRestriction] = useState("");
  const [rows, setRows] = useState<AdminAccountRow[]>([]);
  const [selected, setSelected] = useState<AdminAccountDetail | null>(null);
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [searched, setSearched] = useState(false);
  const [text, setText] = useState("");
  const [failed, setFailed] = useState(false);

  async function search() {
    setBusy(true);
    try {
      setRows(await api.accounts(actorType, query.trim(), restriction));
      setSearched(true);
      setFailed(false);
      setText("");
    } catch (error) {
      setFailed(true);
      setText(message(error));
    } finally {
      setBusy(false);
    }
  }

  async function open(row: AdminAccountRow) {
    setBusy(true);
    setReason("");
    setNote("");
    try {
      setSelected(await api.account(row.actor_type, row.account_id));
      setFailed(false);
    } catch (error) {
      setFailed(true);
      setText(message(error));
    } finally {
      setBusy(false);
    }
  }

  async function toggle(kind: string, active: boolean) {
    if (!selected) return;
    if (!reason.trim()) {
      setFailed(true);
      setText("Sabab kiritilishi shart.");
      return;
    }
    setBusy(true);
    try {
      const call = active ? api.unrestrict : api.restrict;
      await call.call(api, selected.actor_type, selected.account_id, {
        restriction: kind,
        reason: reason.trim(),
      });
      setSelected(await api.account(selected.actor_type, selected.account_id));
      setReason("");
      setFailed(false);
      setText(active ? "Cheklov olib tashlandi" : "Cheklov qo‘yildi");
      await search();
    } catch (error) {
      setFailed(true);
      setText(message(error));
    } finally {
      setBusy(false);
    }
  }

  async function saveNote() {
    if (!selected) return;
    if (!note.trim()) {
      setFailed(true);
      setText("Izoh bo‘sh bo‘lmasin.");
      return;
    }
    setBusy(true);
    try {
      await api.addNote(selected.actor_type, selected.account_id, note.trim());
      setSelected(await api.account(selected.actor_type, selected.account_id));
      setNote("");
      setFailed(false);
      setText("Izoh saqlandi ✅");
    } catch (error) {
      setFailed(true);
      setText(message(error));
    } finally {
      setBusy(false);
    }
  }

  const active = new Set(
    (selected?.restrictions ?? [])
      .filter((row) => row.status === "active")
      .map((row) => row.restriction),
  );

  return (
    <section className="page active">
      <div className="page-head">
        <div>
          <div className="eyebrow">PROFILLAR</div>
          <h1>Foydalanuvchilar va bizneslar</h1>
        </div>
      </div>

      <div className="filterbar">
        <label className="sr-only" htmlFor="accountType">Akkaunt turi</label>
        <select
          id="accountType"
          value={actorType}
          onChange={(event) => {
            setActorType(event.target.value as "user" | "business");
            setSelected(null);
          }}
        >
          <option value="business">Bizneslar</option>
          <option value="user">Foydalanuvchilar</option>
        </select>
        <label className="sr-only" htmlFor="accountSearch">Qidiruv</label>
        <input
          id="accountSearch"
          placeholder="Ism, login yoki Telegram ID"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <label className="sr-only" htmlFor="accountStatus">Holat</label>
        <select
          id="accountStatus"
          value={restriction}
          onChange={(event) => setRestriction(event.target.value)}
        >
          <option value="">Barcha holatlar</option>
          <option value="content_hidden">Publicdan yashirilgan</option>
          <option value="account_blocked">Bloklangan</option>
        </select>
        <button type="button" disabled={busy} onClick={() => void search()}>
          Qidirish
        </button>
      </div>

      {text ? (
        <div className={`message${failed ? " error" : ""}`} role="status">
          {text}
        </div>
      ) : null}

      <div className="panel table-wrap">
        <table>
          <thead>
            <tr>
              <th>Login</th>
              <th>Nomi</th>
              <th>Telefon</th>
              <th>Cheklovlar</th>
              <th>Amal</th>
            </tr>
          </thead>
          <tbody>
            {!searched ? (
              <tr><td colSpan={5}>Qidiruvni boshlang.</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={5}>Hech narsa topilmadi.</td></tr>
            ) : rows.map((row) => (
              <tr key={`${row.actor_type}-${row.account_id}`}>
                <td>{row.login}</td>
                <td>{row.name || "—"}</td>
                <td>{row.phone || "—"}</td>
                <td>
                  {row.restrictions.length
                    ? row.restrictions
                      .map((kind) => RESTRICTION_TEXT[kind] ?? kind)
                      .join(", ")
                    : "—"}
                </td>
                <td>
                  <button
                    type="button"
                    className="secondary compact"
                    onClick={() => void open(row)}
                  >
                    Ko‘rish
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selected ? (
        <div className="panel detail-panel">
          <div className="panel-head">
            <h2>{selected.login}</h2>
            <button
              type="button"
              className="secondary compact"
              onClick={() => setSelected(null)}
            >
              Yopish
            </button>
          </div>

          <dl className="detail-grid">
            <div><dt>Nomi</dt><dd>{selected.name || "—"}</dd></div>
            <div><dt>Telefon</dt><dd>{selected.phone || "—"}</dd></div>
            <div>
              <dt>Telegram</dt>
              <dd>{selected.telegram_user_id ?? "—"}</dd>
            </div>
            <div>
              <dt>Ro‘yxatdan o‘tgan</dt>
              <dd>{stamp(selected.created_at)}</dd>
            </div>
          </dl>

          <label htmlFor="restrictReason">Sabab</label>
          <input
            id="restrictReason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
          <div className="decision-row">
            {(["content_hidden", "account_blocked"] as const).map((kind) => (
              <button
                key={kind}
                type="button"
                className={active.has(kind) ? "secondary" : "secondary danger"}
                disabled={busy}
                onClick={() => void toggle(kind, active.has(kind))}
              >
                {active.has(kind)
                  ? `${RESTRICTION_TEXT[kind]} — olib tashlash`
                  : RESTRICTION_TEXT[kind]}
              </button>
            ))}
          </div>

          <div className="panel-head">
            <h2>Cheklov tarixi</h2>
          </div>
          {selected.restrictions.length === 0 ? (
            <div className="muted">Cheklov bo‘lmagan.</div>
          ) : (
            <div className="attempts">
              {selected.restrictions.map((row) => (
                <div className="attempt" key={row.id}>
                  <span>{RESTRICTION_TEXT[row.restriction] ?? row.restriction}</span>
                  <span>{row.status === "active" ? "Faol" : "Bekor qilingan"}</span>
                  <span>{stamp(row.created_at)}</span>
                  <span className="reason">{row.reason}</span>
                </div>
              ))}
            </div>
          )}

          <label htmlFor="accountNote">Ichki izoh</label>
          <input
            id="accountNote"
            value={note}
            onChange={(event) => setNote(event.target.value)}
          />
          <div className="decision-row">
            <button type="button" disabled={busy} onClick={() => void saveNote()}>
              Izoh qo‘shish
            </button>
          </div>
          <div className="attempts">
            {selected.notes.map((row) => (
              <div className="attempt" key={row.id}>
                <span>{stamp(row.created_at)}</span>
                <span>{row.note}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
