import { useCallback, useEffect, useState } from "react";

import type {
  AdminApiClient,
  AdminPaymentDetail,
  AdminPaymentRow,
} from "./admin-client";


export type AdminPaymentsApi = Pick<
  AdminApiClient,
  "payments" | "payment" | "receipt" | "decide"
>;

type Props = {
  api: AdminPaymentsApi;
  onChanged?: () => void;
};

const STATUS_TEXT: Record<string, string> = {
  pending: "Kutilayotgan",
  approved: "Tasdiqlangan",
  rejected: "Rad etilgan",
  cancelled: "Bekor qilingan",
};

const SERVICE_TEXT: Record<string, string> = {
  subscription: "Obuna",
  advertisement: "Reklama",
  listing: "E’lon",
};


function money(value: number) {
  return Number(value || 0).toLocaleString("uz-UZ");
}

function stamp(seconds: number) {
  if (!seconds) return "—";
  const at = new Date(seconds * 1000);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${pad(at.getDate())}.${pad(at.getMonth() + 1)}.${at.getFullYear()}`
    + ` ${pad(at.getHours())}:${pad(at.getMinutes())}`;
}

function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}


export function AdminPayments({ api, onChanged }: Props) {
  const [status, setStatus] = useState("pending");
  const [serviceType, setServiceType] = useState("");
  const [rows, setRows] = useState<AdminPaymentRow[]>([]);
  const [selected, setSelected] = useState<AdminPaymentDetail | null>(null);
  const [receiptUrl, setReceiptUrl] = useState("");
  const [reason, setReason] = useState("");
  const [internalNote, setInternalNote] = useState("");
  const [loading, setLoading] = useState(true);
  // Faqat ochilayotgan qator kutish holatida bo'ladi.
  const [opening, setOpening] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await api.payments(status, serviceType));
      setFailed(false);
    } catch (error) {
      setFailed(true);
      setNote(message(error));
    } finally {
      setLoading(false);
    }
  }, [api, status, serviceType]);

  useEffect(() => {
    void load();
  }, [load]);

  async function open(paymentId: number) {
    setOpening(paymentId);
    setReceiptUrl("");
    setReason("");
    setInternalNote("");
    try {
      setSelected(await api.payment(paymentId));
      setFailed(false);
      setNote("");
    } catch (error) {
      setFailed(true);
      setNote(message(error));
    } finally {
      setOpening(null);
    }
  }

  async function showReceipt(paymentId: number) {
    setBusy(true);
    try {
      const link = await api.receipt(paymentId);
      setReceiptUrl(link.url);
      setFailed(false);
    } catch (error) {
      setFailed(true);
      setNote(message(error));
    } finally {
      setBusy(false);
    }
  }

  async function decide(decision: "approve" | "reject" | "cancel") {
    if (!selected) return;
    if (decision !== "approve" && !reason.trim()) {
      setFailed(true);
      setNote("Sabab kiritilishi shart.");
      return;
    }
    setBusy(true);
    try {
      await api.decide(selected.id, decision, {
        reason: reason.trim(),
        internal_note: internalNote.trim(),
      });
      setFailed(false);
      setNote({
        approve: "To‘lov tasdiqlandi ✅",
        reject: "To‘lov rad etildi",
        cancel: "To‘lov bekor qilindi",
      }[decision]);
      setSelected(null);
      setReceiptUrl("");
      await load();
      onChanged?.();
    } catch (error) {
      setFailed(true);
      setNote(message(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page active">
      <div className="page-head">
        <div>
          <div className="eyebrow">MANUAL TEKSHIRUV</div>
          <h1>To‘lovlar</h1>
        </div>
      </div>

      <div className="filterbar">
        <label className="sr-only" htmlFor="paymentStatus">Holat</label>
        <select
          id="paymentStatus"
          value={status}
          onChange={(event) => setStatus(event.target.value)}
        >
          <option value="pending">Kutilayotgan</option>
          <option value="">Barchasi</option>
          <option value="approved">Tasdiqlangan</option>
          <option value="rejected">Rad etilgan</option>
          <option value="cancelled">Bekor qilingan</option>
        </select>
        <label className="sr-only" htmlFor="paymentService">Xizmat</label>
        <select
          id="paymentService"
          value={serviceType}
          onChange={(event) => setServiceType(event.target.value)}
        >
          <option value="">Barcha xizmatlar</option>
          <option value="subscription">Obuna</option>
          <option value="advertisement">Reklama</option>
          <option value="listing">E’lon</option>
        </select>
        <button type="button" onClick={() => void load()} disabled={loading}>
          Ko‘rsatish
        </button>
      </div>

      {note ? (
        <div className={`message${failed ? " error" : ""}`} role="status">
          {note}
        </div>
      ) : null}

      <div className="panel table-wrap">
        <table>
          <thead>
            <tr>
              <th>Kod</th>
              <th>Xizmat</th>
              <th>Summa</th>
              <th>Holat</th>
              <th>Sana</th>
              <th>Amal</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6}>Yuklanmoqda…</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={6}>To‘lov yo‘q.</td></tr>
            ) : rows.map((row) => (
              <tr key={row.id}>
                <td>{row.request_code}</td>
                <td>{SERVICE_TEXT[row.service_type] ?? row.service_type}</td>
                <td>{`${money(row.amount)} so‘m`}</td>
                <td>{STATUS_TEXT[row.status] ?? row.status}</td>
                <td>{stamp(row.created_at)}</td>
                <td>
                  <button
                    type="button"
                    className="secondary compact"
                    disabled={opening === row.id}
                    onClick={() => void open(row.id)}
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
            <h2>{selected.request_code}</h2>
            <button
              type="button"
              className="secondary compact"
              onClick={() => { setSelected(null); setReceiptUrl(""); }}
            >
              Yopish
            </button>
          </div>

          <dl className="detail-grid">
            <div><dt>Egasi</dt><dd>{selected.account_login}</dd></div>
            <div>
              <dt>Xizmat</dt>
              <dd>
                {SERVICE_TEXT[selected.service_type] ?? selected.service_type}
                {selected.plan_code
                  ? ` · ${selected.plan_code} · ${selected.duration_months} oy`
                  : ""}
              </dd>
            </div>
            <div><dt>Summa</dt><dd>{`${money(selected.amount)} so‘m`}</dd></div>
            <div><dt>Usul</dt><dd>{selected.payment_method_name}</dd></div>
            <div>
              <dt>Holat</dt>
              <dd>{STATUS_TEXT[selected.status] ?? selected.status}</dd>
            </div>
            <div><dt>Yuborilgan</dt><dd>{stamp(selected.created_at)}</dd></div>
          </dl>

          <div className="attempts">
            {selected.attempts.map((attempt) => (
              <div className="attempt" key={attempt.attempt_no}>
                <span>{`#${attempt.attempt_no}`}</span>
                <span>{STATUS_TEXT[attempt.review_status] ?? attempt.review_status}</span>
                <span>{stamp(attempt.submitted_at)}</span>
                {attempt.review_reason ? (
                  <span className="reason">{attempt.review_reason}</span>
                ) : null}
              </div>
            ))}
          </div>

          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={() => void showReceipt(selected.id)}
          >
            🧾 Kvitansiyani ko‘rish
          </button>
          {receiptUrl ? (
            <img className="receipt" src={receiptUrl} alt="To‘lov kvitansiyasi" />
          ) : null}

          {selected.status === "pending" ? (
            <>
              <label htmlFor="decisionReason">Sabab (mijozga ko‘rinadi)</label>
              <input
                id="decisionReason"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
              <label htmlFor="internalNote">Ichki izoh</label>
              <input
                id="internalNote"
                value={internalNote}
                onChange={(event) => setInternalNote(event.target.value)}
              />
              <div className="decision-row">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void decide("approve")}
                >
                  Tasdiqlash
                </button>
                <button
                  type="button"
                  className="secondary danger"
                  disabled={busy}
                  onClick={() => void decide("reject")}
                >
                  Rad etish
                </button>
                <button
                  type="button"
                  className="secondary"
                  disabled={busy}
                  onClick={() => void decide("cancel")}
                >
                  Bekor qilish
                </button>
              </div>
            </>
          ) : (
            <div className="message" role="status">
              {`Qaror qabul qilingan: ${
                STATUS_TEXT[selected.status] ?? selected.status
              }`}
            </div>
          )}
        </div>
      ) : null}
    </section>
  );
}
