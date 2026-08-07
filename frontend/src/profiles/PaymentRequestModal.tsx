import { useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  PaymentCatalog,
  PaymentMethod,
  PaymentReceiptRef,
} from "../api/types";
import "./PaymentRequestModal.css";


export type PaymentRequestApi = Pick<
  ApiClient,
  "getPaymentCatalog" | "createPaymentRequest" | "createUploadGrant"
  | "uploadGrantedFile"
>;

export type PaymentTarget = {
  /** v1656: `subscription_plus_3m` kabi tarif kodi. */
  priceCode: string;
  label: string;
  planCode?: string;
  durationMonths?: number;
};

const MAX_RECEIPT_BYTES = 5 * 1024 * 1024;


function money(value: number) {
  return Number(value || 0).toLocaleString("uz-UZ");
}

function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

/** v1656 `paymentMethodText` — qabul qiluvchi, rekvizitlar, ko'rsatma. */
export function paymentMethodText(method: PaymentMethod | undefined) {
  if (!method) return "To‘lov usulini tanlang.";
  const lines: string[] = [];
  if (method.recipient_name) {
    lines.push(`Qabul qiluvchi: ${method.recipient_name}`);
  }
  for (const value of Object.values(method.details ?? {})) {
    if (value !== null && value !== undefined && value !== "") {
      lines.push(String(value));
    }
  }
  if (method.instructions) lines.push(method.instructions);
  return lines.join("\n")
    || "Rekvizitlar administrator tomonidan kiritiladi.";
}


async function fileDigest(file: File) {
  const buffer = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}


export function PaymentRequestModal({
  api,
  catalog,
  target,
  onClose,
  onSubmitted,
}: {
  api: PaymentRequestApi;
  catalog: PaymentCatalog;
  target: PaymentTarget;
  onClose(): void;
  onSubmitted(): void;
}) {
  const price = catalog.prices.find(
    (row) => row.price_code === target.priceCode,
  );
  const [methodId, setMethodId] = useState(catalog.methods[0]?.id ?? 0);
  const [receipt, setReceipt] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [failed, setFailed] = useState(false);

  function chooseReceipt(file: File | null) {
    if (file && file.size > MAX_RECEIPT_BYTES) {
      setFailed(true);
      setNote("Kvitansiya 5 MB dan oshmasin.");
      return;
    }
    setFailed(false);
    setNote("");
    setReceipt(file);
  }

  async function submit() {
    if (!price) {
      setFailed(true);
      setNote("Tanlangan tarif hozir faol emas.");
      return;
    }
    if (!receipt) {
      setFailed(true);
      setNote("To‘lov kvitansiyasini tanlang.");
      return;
    }
    setBusy(true);
    setFailed(false);
    setNote("Kvitansiya xavfsiz yuklanmoqda...");
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
        plan_code: target.planCode ?? "",
        duration_months: target.durationMonths ?? 0,
      });
      onSubmitted();
      onClose();
    } catch (error) {
      setFailed(true);
      setNote(message(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="payment-request-modal on" role="dialog" aria-modal="true">
      <div className="payment-modal-back" onClick={onClose} />
      <div className="payment-modal-card">
        <div className="payment-modal-head">
          <div>
            <h2>To‘lov so‘rovini yuborish</h2>
            <div className="idesc">Xizmat ma’lumotlari</div>
          </div>
          <button
            type="button"
            className="payment-modal-close"
            aria-label="Yopish"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <div className="payment-summary">
          <span>{target.label}</span>
          <strong>{money(price?.amount_uzs ?? 0)} so‘m</strong>
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
              <option key={method.id} value={method.id}>{method.name}</option>
            ))}
          </select>
          <div className="payment-method-details">
            {paymentMethodText(
              catalog.methods.find((row) => row.id === methodId),
            )}
          </div>
        </div>

        <div className="field">
          <label htmlFor="payment-receipt">To‘lov kvitansiyasi</label>
          <input
            id="payment-receipt"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={(event) => chooseReceipt(event.target.files?.[0] ?? null)}
          />
          <div className="idesc">
            Maksimum 5 MB. Kvitansiya ochiq fayllar orasida saqlanmaydi.
          </div>
        </div>

        {note ? (
          <div
            className={`subscription-action-message on${failed ? " error" : ""}`}
            role="status"
          >
            {note}
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
  );
}
