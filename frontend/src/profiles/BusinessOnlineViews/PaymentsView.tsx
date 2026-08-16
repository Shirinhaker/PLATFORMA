// `BusinessOnlineViews.tsx` dan ajratildi.
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../../api/business-online-types";
import { money } from "../business-profile-config";
import { paymentDate, recordId, recordNumber, recordText, v1656Money } from "./shared";

export function PaymentsView({
  rows,
  loading,
  refresh,
  resubmit,
}: {
  rows: BusinessOnlineRecord[];
  loading: boolean;
  refresh: () => void;
  resubmit?: (id: number | string, file: File) => Promise<void>;
}) {
  const receiptInputs = useRef<Record<string, HTMLInputElement | null>>({});
  const [receipts, setReceipts] = useState<Record<string, File>>({});
  const [message, setMessage] = useState("");
  function serviceLabel(row: BusinessOnlineRecord) {
    const service = recordText(row, "service_type", "service");
    const plan = recordText(row, "plan_code", "plan");
    if (service === "subscription" || plan) {
      return `${plan === "pro" ? "Pro" : "Plus"} obuna`;
    }
    if (service === "advertisement") return "Reklama joylashtirish";
    if (service === "listing") return "E’lon joylashtirish";
    return "To‘lov";
  }
  function paymentStatus(value: unknown) {
    const status = String(value ?? "");
    return status === "approved"
      ? "Tasdiqlangan"
      : status === "rejected"
        ? "Rad etilgan"
        : status === "cancelled"
          ? "Bekor qilingan"
          : "Tekshirilmoqda";
  }
  return (
    <section className="form-wrap">
      {message && (
        <div className="app-toast on" role="status">
          {message}
        </div>
      )}
      <div className="lead">To‘lovlarim</div>
      <div className="lead-sub">
        Kvitansiya yuborilgan xizmatlar va administrator tekshiruvi holati.
      </div>
      <button
        type="button"
        className="btn btn-outline btn-block"
        onClick={refresh}
        disabled={loading}
      >
        Yangilash
      </button>
      <div className="payment-list">
        {rows.length ? (
          rows.map((row, index) => {
            const status = recordText(row, "status") || "pending";
            return (
              <article className="payment-card" key={String(recordId(row, index))}>
                <div className="payment-card-head">
                  <div>
                    <b>{serviceLabel(row)}</b>
                    <div className="payment-card-code">
                      {recordText(row, "request_code") || `#${recordId(row, index)}`}
                      {" · "}
                      {paymentDate(row.created_at)}
                    </div>
                  </div>
                  <span className={`payment-status ${status}`}>
                    {paymentStatus(status)}
                  </span>
                </div>
                <div className="payment-card-amount">
                  {v1656Money(recordNumber(row, "amount", "amount_snapshot", "total"))}
                </div>
                {recordText(row, "reason") && (
                  <div className="subscription-action-message error">
                    {recordText(row, "reason")}
                  </div>
                )}
                {status === "rejected" && (
                  <>
                    <input
                      ref={(node) => {
                        receiptInputs.current[String(recordId(row, index))] = node;
                      }}
                      type="file"
                      hidden
                      accept="image/jpeg,image/png,image/webp"
                      onChange={(event) => {
                        const file = event.currentTarget.files?.[0];
                        if (!file) return;
                        if (
                          !["image/jpeg", "image/png", "image/webp"].includes(
                            file.type,
                          ) ||
                          file.size > 5 * 1024 * 1024
                        ) {
                          event.currentTarget.value = "";
                          setMessage("JPG, PNG yoki WEBP; maksimum 5 MB.");
                          return;
                        }
                        setMessage("");
                        setReceipts((current) => ({
                          ...current,
                          [String(recordId(row, index))]: file,
                        }));
                      }}
                    />
                    <button
                      type="button"
                      className="btn btn-outline btn-block"
                      onClick={() =>
                        receiptInputs.current[String(recordId(row, index))]?.click()
                      }
                    >
                      {receipts[String(recordId(row, index))]
                        ? "Kvitansiya tanlandi ✅"
                        : "Yangi kvitansiya tanlash"}
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary btn-block"
                      disabled={loading}
                      onClick={async () => {
                        const id = recordId(row, index);
                        const file = receipts[String(id)];
                        if (!file) {
                          setMessage("Yangi kvitansiyani tanlang.");
                          return;
                        }
                        try {
                          await resubmit?.(id, file);
                          setReceipts((current) => {
                            const next = { ...current };
                            delete next[String(id)];
                            return next;
                          });
                          setMessage("Kvitansiya qayta yuborildi ✅");
                        } catch (error) {
                          setMessage(
                            error instanceof Error
                              ? error.message
                              : "So‘rov bajarilmadi.",
                          );
                        }
                      }}
                    >
                      Qayta yuborish
                    </button>
                  </>
                )}
              </article>
            );
          })
        ) : (
          <div className="subscription-state">
            <h3>To‘lovlar yo‘q</h3>
            <p>Yuborgan kvitansiyalaringiz shu yerda ko‘rinadi.</p>
          </div>
        )}
      </div>
    </section>
  );
}
