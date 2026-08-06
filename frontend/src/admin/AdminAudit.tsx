import { useCallback, useEffect, useState } from "react";

import type { AdminApiClient, AuditDetail, AuditRow } from "./admin-client";


export type AdminAuditApi = Pick<
  AdminApiClient,
  "audit" | "auditDetail" | "auditExportUrl"
>;

type Props = { api: AdminAuditApi };

function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

function stamp(seconds: number) {
  if (!seconds) return "—";
  const at = new Date(seconds * 1000);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${pad(at.getDate())}.${pad(at.getMonth() + 1)}.${at.getFullYear()}`
    + ` ${pad(at.getHours())}:${pad(at.getMinutes())}`;
}


export function AdminAudit({ api }: Props) {
  const [action, setAction] = useState("");
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [selected, setSelected] = useState<AuditDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [text, setText] = useState("");
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await api.audit(action));
      setFailed(false);
      setText("");
    } catch (error) {
      setFailed(true);
      setText(message(error));
    } finally {
      setLoading(false);
    }
  }, [api, action]);

  useEffect(() => {
    void load();
  }, [load]);

  async function open(auditId: number) {
    try {
      setSelected(await api.auditDetail(auditId));
      setFailed(false);
    } catch (error) {
      setFailed(true);
      setText(message(error));
    }
  }

  return (
    <section className="page active">
      <div className="page-head">
        <div>
          <div className="eyebrow">TARIX</div>
          <h1>Audit tarixi</h1>
        </div>
      </div>

      <div className="filterbar">
        <label className="sr-only" htmlFor="auditAction">Amal</label>
        <input
          id="auditAction"
          placeholder="Amal — masalan payment.approve"
          value={action}
          onChange={(event) => setAction(event.target.value)}
        />
        <button type="button" disabled={loading} onClick={() => void load()}>
          Ko‘rsatish
        </button>
        <a
          className="secondary compact export-link"
          href={api.auditExportUrl(action)}
        >
          CSV yuklab olish
        </a>
      </div>

      <div className="muted">
        Bu jurnal o‘zgartirilmaydi va o‘chirilmaydi.
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
              <th>Sana</th>
              <th>Admin</th>
              <th>Amal</th>
              <th>Obyekt</th>
              <th>Sabab</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6}>Yuklanmoqda…</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={6}>Yozuv yo‘q.</td></tr>
            ) : rows.map((row) => (
              <tr key={row.id}>
                <td>{stamp(row.created_at)}</td>
                <td>{row.admin_tg_id}</td>
                <td>{row.action}</td>
                <td>{`${row.target_kind} ${row.target_id}`}</td>
                <td>{row.reason || "—"}</td>
                <td>
                  <button
                    type="button"
                    className="secondary compact"
                    onClick={() => void open(row.id)}
                  >
                    Batafsil
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
            <h2>{selected.action}</h2>
            <button
              type="button"
              className="secondary compact"
              onClick={() => setSelected(null)}
            >
              Yopish
            </button>
          </div>
          <dl className="detail-grid">
            <div><dt>Admin</dt><dd>{selected.admin_tg_id}</dd></div>
            <div><dt>Sana</dt><dd>{stamp(selected.created_at)}</dd></div>
            <div>
              <dt>Obyekt</dt>
              <dd>{`${selected.target_kind} ${selected.target_id}`}</dd>
            </div>
            <div><dt>Brauzer</dt><dd>{selected.user_agent || "—"}</dd></div>
          </dl>
          <div className="muted">Oldingi holat</div>
          <pre className="audit-json">
            {JSON.stringify(selected.before, null, 2)}
          </pre>
          <div className="muted">Yangi holat</div>
          <pre className="audit-json">
            {JSON.stringify(selected.after, null, 2)}
          </pre>
        </div>
      ) : null}
    </section>
  );
}
