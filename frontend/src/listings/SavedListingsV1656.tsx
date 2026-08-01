import { useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type { ListingRead } from "../api/types";
import "./ListingsV1656.css";


type Props = {
  getSavedListings: ApiClient["getSavedListings"];
  legacyRows: unknown[];
  onBack(): void;
  onOpenListing(publicId: string): void;
};

function legacyBusinessRows(rows: unknown[]) {
  return rows.filter((row) => (
    row
    && typeof row === "object"
    && String((row as Record<string, unknown>).target_kind ?? "") === "business"
  )) as Record<string, unknown>[];
}


export function SavedListingsV1656({
  getSavedListings,
  legacyRows,
  onBack,
  onOpenListing,
}: Props) {
  const [listings, setListings] = useState<ListingRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    getSavedListings()
      .then((rows) => { if (active) setListings(rows); })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "Saqlanganlar yuklanmadi.");
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [getSavedListings]);

  const businesses = legacyBusinessRows(legacyRows);
  const count = listings.length + businesses.length;

  return (
    <main className="business-online saved-listings-v1656">
      <header className="business-online-head">
        <button aria-label="Orqaga" className="back-btn" type="button" onClick={onBack}>‹</button>
        <h1>Saqlanganlar</h1>
      </header>
      {loading ? <div className="list-sub">Yuklanmoqda...</div> : null}
      {error ? <p className="elon-hint">{error}</p> : null}
      {!loading && !error && !count ? (
        <div className="empty" style={{ padding: "30px 16px" }}>
          <h3>Saqlanganlar yo&apos;q</h3>
          <p>E&apos;lon yoki bizneslarni 🔖 bilan saqlasangiz, shu yerda turadi.</p>
        </div>
      ) : null}
      {!loading && !error && count ? (
        <>
          <div className="list-sub" style={{ marginTop: 8 }}>{count} ta saqlangan</div>
          {listings.map((listing) => (
            <button
              className="elon-item"
              data-listing-public-id={listing.public_id}
              key={listing.public_id}
              type="button"
              onClick={() => onOpenListing(listing.public_id)}
            >
              <div className="li-thumb" style={{ background: "var(--primary-tint)" }}><span>📦</span></div>
              <div className="li-main">
                <div className="li-title">{listing.title}</div>
                <div className="li-price">{listing.price}</div>
                <div className="li-meta">E&apos;lon</div>
              </div>
            </button>
          ))}
          {businesses.map((business, index) => (
            <div className="elon-item" key={String(business.id ?? business.target_id ?? index)}>
              <div className="li-thumb" style={{ background: "var(--primary-tint)" }}><span>🏪</span></div>
              <div className="li-main">
                <div className="li-title">{String(business.name ?? `#${business.target_id ?? business.id ?? ""}`)}</div>
                <div className="li-meta">Biznes · {String(business.info ?? "")}</div>
              </div>
            </div>
          ))}
        </>
      ) : null}
    </main>
  );
}
