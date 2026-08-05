import { useCallback, useEffect, useMemo, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  PaymentCatalog,
  PaymentRequestRecord,
  PaymentReceiptRef,
} from "../api/types";
import "./SubscriptionsV1656.css";


export type SubscriptionsApi = Pick<
  ApiClient,
  | "getPaymentCatalog"
  | "getMyPayments"
  | "createPaymentRequest"
  | "createUploadGrant"
  | "uploadGrantedFile"
>;

type PlanCode = "free" | "plus" | "pro";

const DURATIONS = [1, 3, 12] as const;
const PLAN_NAMES: Record<PlanCode, string> = {
  free: "Bepul",
  plus: "Plus",
  pro: "Pro",
};
const PLAN_CAPTIONS: Record<PlanCode, string> = {
  free: "Asosiy biznes profil uchun",
  plus: "Yaqin mijozlarga ko‘rinish",
  pro: "Eng keng imkoniyatlar",
};
const PLAN_ICONS: Record<PlanCode, string> = {
  free: "🌱",
  plus: "✨",
  pro: "💎",
};
const PLAN_BENEFITS: Record<PlanCode, string[]> = {
  free: [
    "Biznes profilidan foydalanish",
    "Mahsulot va xizmatlarni cheksiz joylash",
  ],
  plus: [
    "Bepul tarifdagi barcha imkoniyatlar",
    "Mahsulot yoki xizmatlarni “Sizga yaqin” bo‘limiga chiqarish huquqi",
  ],
  pro: [
    "Plus tarifdagi barcha imkoniyatlar",
    "Biznesni bosh xaritada ko‘rsatish",
  ],
};
const MAX_RECEIPT_BYTES = 5 * 1024 * 1024;


function money(value: number) {
  return Number(value || 0).toLocaleString("uz-UZ");
}

function message(error: unknown) {
  return error instanceof Error ? error.message : "Kutilmagan xato.";
}

async function fileDigest(file: File) {
  const buffer = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}


export function SubscriptionsV1656({
  api,
  onBack,
}: {
  api: SubscriptionsApi;
  onBack(): void;
}) {
  const [catalog, setCatalog] = useState<PaymentCatalog | null>(null);
  const [payments, setPayments] = useState<PaymentRequestRecord[]>([]);
  const [duration, setDuration] = useState<number>(1);
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState(false);
  const [openPlan, setOpenPlan] = useState<"plus" | "pro" | null>(null);
  const [methodId, setMethodId] = useState<number>(0);
  const [receipt, setReceipt] = useState<File | null>(null);
  const [formMessage, setFormMessage] = useState("");
  const [formError, setFormError] = useState(false);

  const load = useCallback(async () => {
    try {
      const [loaded, mine] = await Promise.all([
        api.getPaymentCatalog(),
        api.getMyPayments(),
      ]);
      setCatalog(loaded);
      setPayments(mine);
      setMethodId(loaded.methods[0]?.id ?? 0);
      setLoadError("");
    } catch (error) {
      setLoadError(message(error));
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  const priceOf = useCallback(
    (plan: "plus" | "pro") => catalog?.prices.find(
      (price) => price.service_type === "subscription"
        && price.plan_code === plan
        && price.duration_months === duration,
    ) ?? null,
    [catalog, duration],
  );

  const pending = useMemo(
    () => payments.filter((row) => row.status === "pending"),
    [payments],
  );

  function chooseReceipt(file: File | null) {
    if (!file) {
      setReceipt(null);
      return;
    }
    if (file.size > MAX_RECEIPT_BYTES) {
      setFormError(true);
      setFormMessage("Kvitansiya 5 MB dan oshmasin.");
      return;
    }
    setFormError(false);
    setFormMessage("");
    setReceipt(file);
  }

  async function submit() {
    if (!openPlan) return;
    const price = priceOf(openPlan);
    if (!price) {
      setFormError(true);
      setFormMessage("Tanlangan tarif hozir faol emas.");
      return;
    }
    if (!receipt) {
      setFormError(true);
      setFormMessage("To‘lov kvitansiyasini tanlang.");
      return;
    }
    setBusy(true);
    setFormError(false);
    setFormMessage("Kvitansiya xavfsiz yuklanmoqda...");
    try {
      const grant = await api.createUploadGrant({
        purpose: "payment_receipt",
        filename: receipt.name,
        content_type: receipt.type,
        size_bytes: receipt.size,
      });
      await api.uploadGrantedFile(grant, receipt);
      const reference: PaymentReceiptRef = {
        object_key: grant.object_key,
        filename: receipt.name,
        mime: receipt.type,
        sha256: await fileDigest(receipt),
      };
      await api.createPaymentRequest({
        service_type: "subscription",
        price_code: price.price_code,
        payment_method_id: methodId,
        receipt: reference,
        plan_code: openPlan,
        duration_months: duration,
      });
      setOpenPlan(null);
      setReceipt(null);
      setFormMessage("");
      await load();
    } catch (error) {
      setFormError(true);
      setFormMessage(message(error));
    } finally {
      setBusy(false);
    }
  }

  if (loadError) {
    return (
      <section className="subscriptions-v1656">
        <button className="subscriptions-back" type="button" onClick={onBack}>
          ← Ortga
        </button>
        <div className="subscription-state error" role="alert">
          <h3>Tariflarni yuklab bo‘lmadi</h3>
          <p>{loadError}</p>
          <button type="button" onClick={() => void load()}>Qayta urinish</button>
        </div>
      </section>
    );
  }

  if (!catalog) {
    return (
      <section className="subscriptions-v1656">
        <button className="subscriptions-back" type="button" onClick={onBack}>
          ← Ortga
        </button>
        <div className="subscription-state" aria-live="polite">
          <h3>Tariflar yuklanmoqda</h3>
          <p>Joriy obunangiz serverdan olinmoqda.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="subscriptions-v1656">
      <button className="subscriptions-back" type="button" onClick={onBack}>
        ← Ortga
      </button>

      <div className="subscription-demo-note">
        <span>🧾</span>
        <div>
          <b>To‘lov tartibi</b>
          <br />
          Plus yoki Pro tarifini tanlang, kvitansiyani yuboring. Tarif
          administrator tasdiqlagandan keyin faollashadi.
        </div>
      </div>

      {pending.length ? (
        <div className="subscription-current">
          Tekshiruvdagi to‘lov: {pending.length} ta
        </div>
      ) : null}

      <div className="subscription-section-title">
        <h3>Muddatni tanlang</h3>
        <p>Plus va Pro uchun</p>
      </div>
      <div className="subscription-duration" role="group" aria-label="Obuna muddati">
        {DURATIONS.map((value) => (
          <button
            key={value}
            type="button"
            className={value === duration ? "on" : ""}
            aria-pressed={value === duration}
            onClick={() => setDuration(value)}
          >
            {value} oy
          </button>
        ))}
      </div>

      <div className="subscription-section-title">
        <h3>Tariflar</h3>
        <p>Mahsulot va xizmatlarni joylash cheksiz</p>
      </div>
      <div className="subscription-plan-grid">
        {(["free", "plus", "pro"] as PlanCode[]).map((plan) => {
          const price = plan === "free" ? null : priceOf(plan);
          return (
            <article
              className="subscription-plan-card"
              data-plan={plan}
              key={plan}
            >
              <div className="subscription-plan-top">
                <div className="subscription-plan-icon">{PLAN_ICONS[plan]}</div>
                <div>
                  <div className="subscription-plan-name">{PLAN_NAMES[plan]}</div>
                  <div className="subscription-plan-caption">
                    {PLAN_CAPTIONS[plan]}
                  </div>
                </div>
              </div>
              <ul className="subscription-benefits">
                {PLAN_BENEFITS[plan].map((benefit) => (
                  <li key={benefit}>{benefit}</li>
                ))}
              </ul>
              {price ? (
                <div className="subscription-plan-price">
                  {money(price.amount_uzs)} so‘m
                </div>
              ) : null}
              <button
                type="button"
                className="subscription-action"
                disabled={plan !== "free" && !price}
                onClick={() => {
                  if (plan === "free") return;
                  setFormMessage("");
                  setFormError(false);
                  setReceipt(null);
                  setOpenPlan(plan);
                }}
              >
                {plan === "free"
                  ? "Joriy bepul tarif"
                  : `${PLAN_NAMES[plan]} uchun to‘lov qilish`}
              </button>
            </article>
          );
        })}
      </div>

      {payments.length ? (
        <>
          <div className="subscription-section-title">
            <h3>To‘lovlarim</h3>
            <p>Oxirgi so‘rovlar</p>
          </div>
          <div className="subscription-payments">
            {payments.map((row) => (
              <div className="subscription-payment-row" key={row.id}>
                <div>
                  <b>{row.request_code}</b>
                  <div className="idesc">
                    {money(row.amount)} so‘m · {row.plan_code || row.service_type}
                  </div>
                  {row.public_reason ? (
                    <div className="idesc">{row.public_reason}</div>
                  ) : null}
                </div>
                <span className={`subscription-status ${row.status}`}>
                  {row.status === "pending" ? "Tekshiruvda"
                    : row.status === "approved" ? "Tasdiqlangan"
                      : row.status === "rejected" ? "Rad etilgan"
                        : "Bekor qilingan"}
                </span>
              </div>
            ))}
          </div>
        </>
      ) : null}

      {openPlan ? (
        <div className="payment-modal on" role="dialog" aria-modal="true">
          <div className="payment-modal-back" onClick={() => setOpenPlan(null)} />
          <div className="payment-modal-card">
            <div className="payment-modal-head">
              <div>
                <h2>To‘lov so‘rovini yuborish</h2>
                <div className="idesc">
                  {PLAN_NAMES[openPlan]} obuna · {duration} oy
                </div>
              </div>
              <button
                type="button"
                className="payment-modal-close"
                aria-label="Yopish"
                onClick={() => setOpenPlan(null)}
              >
                ×
              </button>
            </div>

            <div className="payment-summary">
              <span>{PLAN_NAMES[openPlan]} obuna</span>
              <strong>{money(priceOf(openPlan)?.amount_uzs ?? 0)} so‘m</strong>
              <div className="idesc">Narx server tomonidan hisoblanadi.</div>
            </div>

            <div className="field">
              <label htmlFor="payment-method">To‘lov usuli</label>
              <select
                className="select"
                id="payment-method"
                value={methodId}
                onChange={(event) => setMethodId(Number(event.target.value))}
              >
                {catalog.methods.map((method) => (
                  <option key={method.id} value={method.id}>
                    {method.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <label htmlFor="payment-receipt">To‘lov kvitansiyasi</label>
              <input
                id="payment-receipt"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={(event) => chooseReceipt(
                  event.target.files?.[0] ?? null,
                )}
              />
              <div className="idesc">
                Maksimum 5 MB. Kvitansiya ochiq fayllar orasida saqlanmaydi.
              </div>
            </div>

            {formMessage ? (
              <div
                className={`subscription-action-message on${formError ? " error" : ""}`}
                role="status"
              >
                {formMessage}
              </div>
            ) : null}

            <button
              type="button"
              className="btn btn-primary btn-block"
              disabled={busy}
              onClick={() => void submit()}
            >
              {busy ? "Yuborilmoqda..." : "To‘lov so‘rovini yuborish"}
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
