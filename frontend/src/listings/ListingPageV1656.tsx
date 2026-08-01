import { useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type { ListingRead } from "../api/types";
import { ListingMediaGridV1656 } from "./ListingMediaGridV1656";
import "./ListingsV1656.css";


type Props = {
  publicId: string;
  getPublicListing: ApiClient["getPublicListing"];
  toggleListingSave?: ApiClient["toggleListingSave"];
  authenticated: boolean;
  onNeedLogin(): void;
  onOpenOwner(kind: "user" | "business", publicId: string): void;
  onTitleChange?(title: string): void;
};


export function ListingPageV1656({
  publicId,
  getPublicListing,
  toggleListingSave,
  authenticated,
  onNeedLogin,
  onOpenOwner,
  onTitleChange,
}: Props) {
  const [listing, setListing] = useState<ListingRead | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");

  useEffect(() => {
    let active = true;
    setListing(null);
    setError("");
    setActionError("");
    getPublicListing(publicId)
      .then((payload) => {
        if (!active) return;
        setListing(payload);
        onTitleChange?.(payload.title);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(reason instanceof Error ? reason.message : "E'lon topilmadi.");
      });
    return () => { active = false; };
  }, [getPublicListing, onTitleChange, publicId]);

  async function save() {
    if (!listing) return;
    if (!authenticated) {
      onNeedLogin();
      return;
    }
    if (!toggleListingSave) return;
    setActionError("");
    setSaving(true);
    try {
      const result = await toggleListingSave(listing.public_id);
      setListing((current) => current ? { ...current, is_saved: result.saved } : current);
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "E'lon saqlanmadi.");
    } finally {
      setSaving(false);
    }
  }

  if (error) {
    return (
      <main className="screen active public-listing-page-v1656" data-screen="list">
        <div className="empty"><h3>Topilmadi</h3><p>{error}</p></div>
      </main>
    );
  }
  if (!listing) {
    return (
      <main className="screen active public-listing-page-v1656" data-screen="list">
        <div className="list-sub">Yuklanmoqda...</div>
      </main>
    );
  }

  return (
    <main className="screen active public-listing-page-v1656" data-screen="list">
      <article className="listing-page-card" id="bizBody">
        {listing.media.length ? (
          <ListingMediaGridV1656 media={listing.media} />
        ) : (
          <div className="biz-hero" style={{ background: "var(--primary-tint)" }}>
            <div className="emoji">📦</div>
          </div>
        )}
        <h1 className="biz-title">{listing.title}</h1>
        <div className="biz-sub">
          <span className="listing-page-price">{listing.price}</span>
          {listing.address ? <><span className="dot-sep" /><span>{listing.address}</span></> : null}
        </div>
        {listing.descr ? <div className="biz-desc">{listing.descr}</div> : null}
        {actionError ? <p className="elon-hint" role="alert">{actionError}</p> : null}
        <div className="actionbar">
          <button
            aria-label={listing.is_saved ? "Saqlangan" : "Saqlash"}
            className="btn btn-soft listing-page-save"
            disabled={saving}
            type="button"
            onClick={() => void save()}
          >
            {listing.is_saved ? "✓" : "🔖"}
          </button>
          <button
            className="btn btn-primary"
            type="button"
            onClick={() => onOpenOwner(listing.owner_kind, listing.owner_public_id)}
          >
            Bog&apos;lanish
          </button>
        </div>
      </article>
    </main>
  );
}
