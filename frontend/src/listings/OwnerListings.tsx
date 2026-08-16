import { useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type { ListingCreate, ListingRead, PaymentCatalog } from "../api/types";
import {
  PaymentRequestModal,
  type PaymentRequestApi,
} from "../profiles/PaymentRequestModal";
import { ListingFormV1656 } from "./ListingForm";
import { ListingMediaGridV1656 } from "./ListingMediaGrid";
import "./Listings.css";

export type OwnerListingsApi = Pick<
  ApiClient,
  | "getMyListings"
  | "createListing"
  | "deleteListing"
  | "createUploadGrant"
  | "uploadGrantedFile"
> &
  Partial<Pick<ApiClient, "getPaymentCatalog" | "createPaymentRequest">>;

type Props = {
  actor: "user" | "business";
  api: OwnerListingsApi;
  onBack(): void;
  onOpenAdvertisements?: () => void;
  /** Biznes kabinetida umumiy reklama/e'lon ekrani ichida ko'rsatadi. */
  embedded?: boolean;
};

const ICONS: Record<string, string> = {
  uy: "🏠",
  ish: "💼",
  moshina: "🚙",
  hayvon: "🐾",
  texnika: "📱",
  boshqa: "📦",
};

/** v1656 `payments.py:57` dagi tarif kodi. */
const LISTING_PRICE_CODE = "listing_publish";

function statusText(status: ListingRead["status"]) {
  if (status === "payment_pending") return "To‘lov kutilmoqda";
  return status === "active" ? "Faol" : "O'chiq";
}

export function OwnerListingsV1656({
  actor,
  api,
  onBack,
  onOpenAdvertisements,
  embedded = false,
}: Props) {
  const [rows, setRows] = useState<ListingRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [opened, setOpened] = useState<string | null>(null);
  // To'lov oynasi: e'lon joylangach yoki "To'lov qilish" bosilganda.
  const [payFor, setPayFor] = useState<ListingRead | null>(null);
  const [catalog, setCatalog] = useState<PaymentCatalog | null>(null);
  const canPay = Boolean(api.getPaymentCatalog && api.createPaymentRequest);

  // Katalog aynan to'lov so'ralganda yuklanadi — ekran ochilishida emas.
  useEffect(() => {
    if (!payFor || catalog || !api.getPaymentCatalog) return;
    let active = true;
    void api
      .getPaymentCatalog()
      .then((value) => {
        if (active) setCatalog(value);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setPayFor(null);
        setError(
          reason instanceof Error ? reason.message : "To‘lov ma’lumotlari yuklanmadi.",
        );
      });
    return () => {
      active = false;
    };
  }, [api, payFor, catalog]);

  useEffect(() => {
    let active = true;
    api
      .getMyListings()
      .then((value) => {
        if (active) setRows(value);
      })
      .catch((reason) => {
        if (active)
          setError(reason instanceof Error ? reason.message : "E'lonlar yuklanmadi.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api]);

  async function create(body: ListingCreate) {
    setBusy(true);
    setError("");
    try {
      const created = await api.createListing(body);
      setRows((current) => [created, ...current]);
      setForm(false);
      if (created.status === "payment_pending") {
        // To'lovsiz e'lon ro'yxatlarga tushmaydi, shuning uchun oyna
        // darhol ochiladi — foydalanuvchi qadamni o'tkazib yubormaydi.
        setNotice("E'lon saqlandi. To'lovdan so'ng ko'rinadi.");
        if (canPay) setPayFor(created);
        return;
      }
      setNotice("E'lon joylandi ✅");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "E'lon joylanmadi.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(publicId: string) {
    setBusy(true);
    setError("");
    try {
      await api.deleteListing(publicId);
      setRows((current) => current.filter((row) => row.public_id !== publicId));
      setOpened((current) => (current === publicId ? null : current));
      setConfirmId(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "E'lon o'chirilmadi.");
    } finally {
      setBusy(false);
    }
  }

  const content = (
    <>
      <section className="promotion-v1656">
        <div className="ad-tabs">
          <button className="ad-tab" type="button" onClick={onOpenAdvertisements}>
            Reklamalarim
          </button>
          <button className="ad-tab on" type="button">
            E&apos;lonlarim
          </button>
        </div>
        {notice ? (
          <div className="story-upload-success on" role="status">
            {notice}
          </div>
        ) : null}
        {error ? (
          <div className="story-upload-error on" role="alert">
            {error}
          </div>
        ) : null}
        {form ? (
          <>
            {embedded ? (
              <button
                className="btn btn-soft btn-block"
                type="button"
                onClick={() => {
                  setForm(false);
                  setError("");
                }}
              >
                ← E&apos;lonlarimga qaytish
              </button>
            ) : null}
            <ListingFormV1656 actor={actor} api={api} busy={busy} onSave={create} />
          </>
        ) : (
          <>
            <button
              className="btn btn-primary btn-block"
              type="button"
              onClick={() => {
                setForm(true);
                setNotice("");
              }}
            >
              + E&apos;lon joylash
            </button>
            {loading ? <div className="list-sub">Yuklanmoqda...</div> : null}
            {!loading && !rows.length ? (
              <div className="empty listing-empty">
                <h3>Hozircha e&apos;lon yo&apos;q</h3>
                <p>Yuqoridagi tugma orqali joylang.</p>
              </div>
            ) : null}
            {rows.map((row) => {
              const open = opened === row.public_id;
              return (
                <article className="owner-listing-wrap" key={row.public_id}>
                  <div className={`elon-item${open ? " on" : ""}`}>
                    <button
                      aria-expanded={open}
                      aria-label={`${row.title} e'lonini ko'rish`}
                      className="owner-listing-open"
                      type="button"
                      onClick={() => setOpened(open ? null : row.public_id)}
                    >
                      <span className="li-thumb">
                        <span>{ICONS[row.cat] ?? "📦"}</span>
                      </span>
                      <span className="li-main">
                        <span className="li-title">{row.title}</span>
                        <span className="li-price">{row.price}</span>
                        <span className="li-meta">
                          {row.visibility === "own"
                            ? "🏪 Faqat mehmonlar"
                            : "🌍 Butun platforma"}
                          {` · ${statusText(row.status)}`}
                          {row.media.length ? ` · 📎 ${row.media.length}` : ""}
                        </span>
                      </span>
                      <span className={`chev${open ? " down" : ""}`} aria-hidden="true">
                        ›
                      </span>
                    </button>
                    <div className="owner-listing-actions">
                      {row.status === "payment_pending" && canPay ? (
                        <button
                          className="btn btn-primary listing-pay-btn"
                          type="button"
                          onClick={() => {
                            setError("");
                            setPayFor(row);
                          }}
                        >
                          To‘lov qilish
                        </button>
                      ) : null}
                      <button
                        aria-label="E'lonni o'chirish"
                        className="mini-ic"
                        type="button"
                        onClick={() => setConfirmId(row.public_id)}
                      >
                        <svg
                          aria-hidden="true"
                          fill="none"
                          stroke="currentColor"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="2"
                          viewBox="0 0 24 24"
                        >
                          <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
                        </svg>
                      </button>
                    </div>
                  </div>
                  {open ? (
                    <div className="el-detail owner-listing-detail">
                      <ListingMediaGridV1656 media={row.media} />
                      <div className="el-price">{row.price || "Narx kelishilgan"}</div>
                      {row.address ? (
                        <div className="el-addr">📍 {row.address}</div>
                      ) : null}
                      {row.descr ? <div className="el-desc">{row.descr}</div> : null}
                    </div>
                  ) : null}
                </article>
              );
            })}
          </>
        )}
      </section>
      {payFor && catalog ? (
        <PaymentRequestModal
          api={api as PaymentRequestApi}
          catalog={catalog}
          target={{
            serviceType: "listing",
            priceCode: LISTING_PRICE_CODE,
            label: `E'lon joylash · ${payFor.title}`,
            targetPublicId: payFor.public_id,
          }}
          onClose={() => setPayFor(null)}
          onSubmitted={() =>
            setNotice("To'lov so'rovi yuborildi. Admin tasdiqlagach e'lon ko'rinadi.")
          }
        />
      ) : null}
      {confirmId ? (
        <>
          <button
            aria-label="Bekor qilish"
            className="app-modal-back on"
            type="button"
            onClick={() => setConfirmId(null)}
          />
          <div className="app-confirm on" role="dialog" aria-modal="true">
            <p className="acf-text">Bu e&apos;lon o&apos;chirilsinmi?</p>
            <div className="acf-btns">
              <button
                className="acf-cancel"
                type="button"
                onClick={() => setConfirmId(null)}
              >
                Bekor qilish
              </button>
              <button
                className="acf-ok danger"
                disabled={busy}
                type="button"
                onClick={() => void remove(confirmId)}
              >
                O&apos;chirish
              </button>
            </div>
          </div>
        </>
      ) : null}
    </>
  );

  if (embedded) {
    return <div className="owner-listings-v1656">{content}</div>;
  }

  return (
    <main className="business-online owner-listings-v1656">
      <header className="business-online-head">
        <button
          className="back-btn"
          aria-label="Orqaga"
          type="button"
          onClick={() => {
            if (form) {
              setForm(false);
              setError("");
              return;
            }
            onBack();
          }}
        >
          ‹
        </button>
        <h1>E&apos;lonlar</h1>
      </header>
      {content}
    </main>
  );
}
