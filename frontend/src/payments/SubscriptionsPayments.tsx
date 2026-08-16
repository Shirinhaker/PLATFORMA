import { useCallback, useEffect, useState, type ReactNode } from "react";

import type { ApiClient } from "../api/client";
import type { BusinessOnlineRecord } from "../api/business-online-types";
import type {
  BusinessSubscriptionRecord,
  BusinessSubscriptionSummary,
  PaymentCatalog,
  PaymentRequestRecord,
} from "../api/types";
import {
  PaymentRequestModal,
  type PaymentTarget,
} from "../profiles/PaymentRequestModal";
import { PaymentsView, SubscriptionsView } from "../profiles/BusinessOnlineViews";
import { uploadPaymentReceipt } from "./payment-receipt";
import "../profiles/BusinessOnlineScreen.css";
import "../profiles/BusinessExistingOnline.css";

export type BusinessSubscriptionsApi = Pick<
  ApiClient,
  | "getBusinessSubscription"
  | "getPaymentCatalog"
  | "createPaymentRequest"
  | "createUploadGrant"
  | "uploadGrantedFile"
>;

export type PaymentsApi = Pick<
  ApiClient,
  "getMyPayments" | "resubmitPayment" | "createUploadGrant" | "uploadGrantedFile"
>;

export function supportsBusinessSubscriptionsApi(
  api: object,
): api is BusinessSubscriptionsApi {
  const value = api as Record<string, unknown>;
  return [
    "getBusinessSubscription",
    "getPaymentCatalog",
    "createPaymentRequest",
    "createUploadGrant",
    "uploadGrantedFile",
  ].every((method) => typeof value[method] === "function");
}

export function supportsPaymentsApi(api: object): api is PaymentsApi {
  const value = api as Record<string, unknown>;
  return [
    "getMyPayments",
    "resubmitPayment",
    "createUploadGrant",
    "uploadGrantedFile",
  ].every((method) => typeof value[method] === "function");
}

function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

function shell(title: string, onBack: () => void, content: ReactNode) {
  return (
    <main className="business-online">
      <header className="business-online__heading">
        <button type="button" onClick={onBack}>
          ← Kabinetga qaytish
        </button>
        <div>
          <h1>{title}</h1>
        </div>
      </header>
      {content}
    </main>
  );
}

function subscriptionRecord(row: BusinessSubscriptionRecord): BusinessOnlineRecord {
  return {
    id: row.id,
    plan_code: row.plan_code,
    duration_months: row.duration_months,
    starts_at: row.starts_at,
    expires_at: row.expires_at,
    status: row.status,
    is_demo: row.is_demo,
    is_virtual: row.is_virtual,
    created_at: row.created_at,
  };
}

function paymentRecord(row: PaymentRequestRecord): BusinessOnlineRecord {
  return {
    ...row,
    reason: row.public_reason,
  };
}

export function BusinessSubscriptions({
  api,
  onBack,
  onOpenPayments,
}: {
  api: BusinessSubscriptionsApi;
  onBack: () => void;
  onOpenPayments: () => void;
}) {
  const [summary, setSummary] = useState<BusinessSubscriptionSummary | null>(null);
  const [catalog, setCatalog] = useState<PaymentCatalog | null>(null);
  const [duration, setDuration] = useState(1);
  const [target, setTarget] = useState<PaymentTarget | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [subscription, paymentCatalog] = await Promise.all([
        api.getBusinessSubscription(),
        api.getPaymentCatalog(),
      ]);
      setSummary(subscription);
      setCatalog(paymentCatalog);
    } catch (reason) {
      setError(message(reason));
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  function openPayment(plan: "plus" | "pro") {
    const priceCode = `subscription_${plan}_${duration}m`;
    if (!catalog?.prices.some((price) => price.price_code === priceCode)) {
      setError("Tanlangan tarif hozir faol emas.");
      return;
    }
    setTarget({
      priceCode,
      label: `${plan === "pro" ? "Pro" : "Plus"} obuna · ${duration} oy`,
      planCode: plan,
      durationMonths: duration,
    });
  }

  const rows = summary
    ? [...summary.history.map(subscriptionRecord), subscriptionRecord(summary.current)]
    : [];

  return shell(
    "Obunalarim",
    onBack,
    <>
      {error ? (
        <p className="business-online__error" role="alert">
          {error}
        </p>
      ) : null}
      {loading ? <div className="business-online__loading">Yuklanmoqda…</div> : null}
      {summary ? (
        <SubscriptionsView
          rows={rows}
          duration={duration}
          setDuration={setDuration}
          busy={loading}
          openPayment={openPayment}
        />
      ) : null}
      {target && catalog ? (
        <PaymentRequestModal
          api={api}
          catalog={catalog}
          target={target}
          onClose={() => setTarget(null)}
          onSubmitted={onOpenPayments}
        />
      ) : null}
    </>,
  );
}

export function Payments({
  api,
  onBack,
}: {
  api: PaymentsApi;
  onBack: () => void;
}) {
  const [rows, setRows] = useState<PaymentRequestRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setRows(await api.getMyPayments());
    } catch (reason) {
      setError(message(reason));
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  async function resubmit(id: number | string, file: File) {
    const paymentId = Number(id);
    if (!Number.isSafeInteger(paymentId) || paymentId <= 0) {
      throw new Error("To‘lov raqami noto‘g‘ri.");
    }
    setLoading(true);
    setError("");
    try {
      const receipt = await uploadPaymentReceipt(api, file);
      const updated = await api.resubmitPayment(paymentId, receipt);
      setRows((current) =>
        current.map((row) => (row.id === updated.id ? updated : row)),
      );
    } catch (reason) {
      setError(message(reason));
      throw reason;
    } finally {
      setLoading(false);
    }
  }

  return shell(
    "To‘lovlarim",
    onBack,
    <>
      {error ? (
        <p className="business-online__error" role="alert">
          {error}
        </p>
      ) : null}
      {loading && !rows.length ? (
        <div className="business-online__loading">Yuklanmoqda…</div>
      ) : null}
      <PaymentsView
        rows={rows.map(paymentRecord)}
        loading={loading}
        refresh={() => void load()}
        resubmit={resubmit}
      />
    </>,
  );
}
