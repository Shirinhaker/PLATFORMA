import { useEffect, useState } from "react";

import type { PaymentCatalog } from "../api/types";
import {
  PaymentRequestModal,
  type PaymentRequestApi,
  type PaymentTarget,
} from "../profiles/PaymentRequestModal";
import {
  BusinessAdvertisementsV1656,
  type BusinessAdvertisementsApi,
} from "./BusinessAdvertisements";

export type UserAdvertisementsApi = BusinessAdvertisementsApi & PaymentRequestApi;

type Props = {
  api: UserAdvertisementsApi;
  onBack(): void;
  onOpenListings(): void;
};

export function UserAdvertisementsV1656({ api, onBack, onOpenListings }: Props) {
  const [paymentTarget, setPaymentTarget] = useState<PaymentTarget | null>(null);
  const [catalog, setCatalog] = useState<PaymentCatalog | null>(null);
  const [paymentError, setPaymentError] = useState("");
  const [notice, setNotice] = useState("");

  // Tariflar reklama ekrani ochilganda emas, faqat to'lov so'ralganda
  // yuklanadi. Bu oddiy ko'rishda ortiqcha server so'rovini oldini oladi.
  useEffect(() => {
    if (!paymentTarget || catalog) return;
    let active = true;
    void api
      .getPaymentCatalog()
      .then((value) => {
        if (active) setCatalog(value);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setPaymentTarget(null);
        setPaymentError(
          reason instanceof Error ? reason.message : "To‘lov ma’lumotlari yuklanmadi.",
        );
      });
    return () => {
      active = false;
    };
  }, [api, catalog, paymentTarget]);

  return (
    <main className="business-online owner-listings-v1656 user-advertisements-v1656">
      <header className="business-online-head">
        <button aria-label="Orqaga" className="back-btn" type="button" onClick={onBack}>
          ‹
        </button>
        <h1>Reklamalar</h1>
      </header>
      {notice ? (
        <div className="story-upload-success on" role="status">
          {notice}
        </div>
      ) : null}
      {paymentError ? (
        <div className="payment-load-error" role="status">
          {paymentError}
        </div>
      ) : null}
      <BusinessAdvertisementsV1656
        api={api}
        onOpenListings={onOpenListings}
        openPayment={(target) => {
          setPaymentError("");
          setPaymentTarget(target);
        }}
      />
      {paymentTarget && catalog ? (
        <PaymentRequestModal
          api={api}
          catalog={catalog}
          target={paymentTarget}
          onClose={() => setPaymentTarget(null)}
          onSubmitted={() =>
            setNotice("To‘lov so‘rovi yuborildi. Admin tasdiqlagach reklama ko‘rinadi.")
          }
        />
      ) : null}
    </main>
  );
}
