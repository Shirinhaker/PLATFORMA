import { useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type { ListingCreate, ListingRead } from "../api/types";
import { ListingFormV1656 } from "./ListingFormV1656";
import "./ListingsV1656.css";


export type OwnerListingsApi = Pick<
  ApiClient,
  | "getMyListings"
  | "createListing"
  | "deleteListing"
  | "createUploadGrant"
  | "uploadGrantedFile"
>;

type Props = {
  actor: "user" | "business";
  api: OwnerListingsApi;
  onBack(): void;
};

const ICONS: Record<string, string> = {
  uy: "🏠", ish: "💼", moshina: "🚙", hayvon: "🐾", texnika: "📱", boshqa: "📦",
};


export function OwnerListingsV1656({ actor, api, onBack }: Props) {
  const [rows, setRows] = useState<ListingRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [confirmId, setConfirmId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    api.getMyListings()
      .then((value) => { if (active) setRows(value); })
      .catch((reason) => {
        if (active) setError(reason instanceof Error ? reason.message : "E'lonlar yuklanmadi.");
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [api]);

  async function create(body: ListingCreate) {
    setBusy(true);
    setError("");
    try {
      const created = await api.createListing(body);
      setRows((current) => [created, ...current]);
      setForm(false);
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
      setConfirmId(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "E'lon o'chirilmadi.");
    } finally {
      setBusy(false);
    }
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
        >‹</button>
        <h1>E&apos;lonlar</h1>
      </header>
      <section className="promotion-v1656">
        <div className="ad-tabs">
          <button className="ad-tab" type="button">Reklamalarim</button>
          <button className="ad-tab on" type="button">E&apos;lonlarim</button>
        </div>
        {notice ? <div className="story-upload-success on" role="status">{notice}</div> : null}
        {error ? <div className="story-upload-error on" role="alert">{error}</div> : null}
        {form ? (
          <ListingFormV1656
            actor={actor}
            api={api}
            busy={busy}
            onSave={create}
          />
        ) : (
          <>
            <button
              className="btn btn-primary btn-block"
              type="button"
              onClick={() => { setForm(true); setNotice(""); }}
            >
              + E&apos;lon joylash
            </button>
            {loading ? <div className="list-sub">Yuklanmoqda...</div> : null}
            {!loading && !rows.length ? (
              <div className="empty listing-empty">
                <h3>Hozircha e&apos;lon yo&apos;q</h3><p>Yuqoridagi tugma orqali joylang.</p>
              </div>
            ) : null}
            {rows.map((row) => (
              <article className="elon-item" key={row.public_id}>
                <div className="li-thumb"><span>{ICONS[row.cat] ?? "📦"}</span></div>
                <div className="li-main">
                  <div className="li-title">{row.title}</div>
                  <div className="li-price">{row.price}</div>
                  <div className="li-meta">
                    {row.visibility === "own" ? "🏪 Faqat mehmonlar" : "🌍 Butun platforma"}
                    {` · ${row.status === "active" ? "Faol" : "O'chiq"}`}
                    {row.media.length ? ` · 📎 ${row.media.length}` : ""}
                  </div>
                </div>
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
              </article>
            ))}
          </>
        )}
      </section>
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
              <button className="acf-cancel" type="button" onClick={() => setConfirmId(null)}>
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
    </main>
  );
}
