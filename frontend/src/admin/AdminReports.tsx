import { useCallback, useEffect, useState } from "react";

import type { AdminApiClient, ReportRow } from "./admin-client";


export type AdminReportsApi = Pick<
  AdminApiClient,
  "reports" | "assignReport" | "decideReport" | "setContentStatus"
>;

type Props = { api: AdminReportsApi };

const STATUS_TEXT: Record<string, string> = {
  open: "Ochiq",
  reviewing: "Ko‘rib chiqilmoqda",
  resolved: "Hal qilingan",
  dismissed: "Rad etilgan",
};

const REASON_TEXT: Record<string, string> = {
  fraud: "Firibgarlik",
  spam: "Spam",
  illegal: "Noqonuniy",
  abuse: "Haqorat",
  other: "Boshqa",
};

function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

function stamp(seconds: number) {
  if (!seconds) return "—";
  const at = new Date(seconds * 1000);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${pad(at.getDate())}.${pad(at.getMonth() + 1)} ${pad(at.getHours())}:${pad(at.getMinutes())}`;
}


export function AdminReports({ api }: Props) {
  const [status, setStatus] = useState("open");
  const [rows, setRows] = useState<ReportRow[]>([]);
  const [selected, setSelected] = useState<ReportRow | null>(null);
  const [resolution, setResolution] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await api.reports(status));
      setFailed(false);
    } catch (error) {
      setFailed(true);
      setText(message(error));
    } finally {
      setLoading(false);
    }
  }, [api, status]);

  useEffect(() => {
    void load();
  }, [load]);

  async function assign(report: ReportRow) {
    setBusy(true);
    try {
      setSelected(await api.assignReport(report.id));
      setFailed(false);
      setText("Shikoyat sizga biriktirildi");
      await load();
    } catch (error) {
      setFailed(true);
      setText(message(error));
    } finally {
      setBusy(false);
    }
  }

  async function decide(decision: "resolve" | "dismiss") {
    if (!selected) return;
    if (!resolution.trim()) {
      setFailed(true);
      setText("Sabab kiritilishi shart.");
      return;
    }
    setBusy(true);
    try {
      await api.decideReport(selected.id, decision, resolution.trim());
      setFailed(false);
      setText(
        decision === "resolve"
          ? "Shikoyat hal qilindi ✅"
          : "Shikoyat rad etildi",
      );
      setSelected(null);
      setResolution("");
      await load();
    } catch (error) {
      setFailed(true);
      setText(message(error));
    } finally {
      setBusy(false);
    }
  }

  async function hideContent() {
    if (!selected) return;
    if (!resolution.trim()) {
      setFailed(true);
      setText("Sabab kiritilishi shart.");
      return;
    }
    setBusy(true);
    try {
      await api.setContentStatus(
        selected.content_kind, selected.content_id, "hide", resolution.trim(),
      );
      setFailed(false);
      setText("Kontent publicdan yashirildi");
    } catch (error) {
      setFailed(true);
      setText(message(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page active">
      <div className="page-head">
        <div>
          <div className="eyebrow">MODERATSIYA</div>
          <h1>Shikoyatlar</h1>
        </div>
      </div>

      <div className="filterbar">
        <label className="sr-only" htmlFor="reportStatus">Holat</label>
        <select
          id="reportStatus"
          value={status}
          onChange={(event) => setStatus(event.target.value)}
        >
          <option value="open">Ochiq</option>
          <option value="reviewing">Ko‘rib chiqilmoqda</option>
          <option value="">Barchasi</option>
          <option value="resolved">Hal qilingan</option>
          <option value="dismissed">Rad etilgan</option>
        </select>
        <button type="button" disabled={loading} onClick={() => void load()}>
          Ko‘rsatish
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
              <th>Kontent</th>
              <th>Sabab</th>
              <th>Holat</th>
              <th>Sana</th>
              <th>Amal</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5}>Yuklanmoqda…</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={5}>Shikoyat yo‘q.</td></tr>
            ) : rows.map((row) => (
              <tr key={row.id}>
                <td>{`${row.content_kind} #${row.content_id}`}</td>
                <td>{REASON_TEXT[row.reason_code] ?? row.reason_code}</td>
                <td>{STATUS_TEXT[row.status] ?? row.status}</td>
                <td>{stamp(row.created_at)}</td>
                <td>
                  <button
                    type="button"
                    className="secondary compact"
                    onClick={() => setSelected(row)}
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
            <h2>{`${selected.content_kind} #${selected.content_id}`}</h2>
            <button
              type="button"
              className="secondary compact"
              onClick={() => { setSelected(null); setResolution(""); }}
            >
              Yopish
            </button>
          </div>

          <dl className="detail-grid">
            <div>
              <dt>Sabab</dt>
              <dd>{REASON_TEXT[selected.reason_code] ?? selected.reason_code}</dd>
            </div>
            <div>
              <dt>Holat</dt>
              <dd>{STATUS_TEXT[selected.status] ?? selected.status}</dd>
            </div>
            <div>
              <dt>Biriktirilgan</dt>
              <dd>{selected.assigned_admin_tg_id ?? "—"}</dd>
            </div>
            <div><dt>Kelgan</dt><dd>{stamp(selected.created_at)}</dd></div>
          </dl>

          {selected.comment ? (
            <div className="muted">{selected.comment}</div>
          ) : null}

          {selected.status === "open" || selected.status === "reviewing" ? (
            <>
              {selected.status === "open" ? (
                <div className="decision-row">
                  <button
                    type="button"
                    className="secondary"
                    disabled={busy}
                    onClick={() => void assign(selected)}
                  >
                    O‘zimga biriktirish
                  </button>
                </div>
              ) : null}

              <label htmlFor="reportResolution">Qaror sababi</label>
              <input
                id="reportResolution"
                value={resolution}
                onChange={(event) => setResolution(event.target.value)}
              />
              <div className="decision-row">
                <button
                  type="button"
                  className="secondary danger"
                  disabled={busy}
                  onClick={() => void hideContent()}
                >
                  Kontentni yashirish
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void decide("resolve")}
                >
                  Hal qilindi
                </button>
                <button
                  type="button"
                  className="secondary"
                  disabled={busy}
                  onClick={() => void decide("dismiss")}
                >
                  Rad etish
                </button>
              </div>
            </>
          ) : (
            <div className="message" role="status">
              {`Qaror: ${STATUS_TEXT[selected.status]} · ${selected.resolution}`}
            </div>
          )}
        </div>
      ) : null}
    </section>
  );
}
