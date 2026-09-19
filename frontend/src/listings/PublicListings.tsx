import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import type { ApiClient } from "../api/client";
import type { ListingCategory, ListingRead } from "../api/types";
import { ListingDetail } from "./ListingDetail";
import "./Listings.css";

type ListingsApi = Pick<
  ApiClient,
  "getListingCounts" | "getPublicListings" | "toggleListingSave"
>;

type Props = {
  api: ListingsApi;
  openedListingId: string | null;
  onOpenListing(publicId: string, title: string): void;
  authenticated: boolean;
  onNeedLogin?: () => void;
  onOpenOwner(kind: "user" | "business", publicId: string): void;
};

const CATEGORIES: ReadonlyArray<{
  key: ListingCategory;
  name: string;
  icon: string;
  color: string;
}> = [
  { key: "uy", name: "Uy-joy", icon: "🏠", color: "#0EA5E9" },
  { key: "ish", name: "Ish o'rinlari", icon: "💼", color: "#16A34A" },
  { key: "moshina", name: "Moshinalar", icon: "🚙", color: "#EF4444" },
  { key: "hayvon", name: "Hayvonlar", icon: "🐾", color: "#F59E0B" },
  { key: "texnika", name: "Texnika", icon: "📱", color: "#8B5CF6" },
  { key: "boshqa", name: "Boshqalar", icon: "📦", color: "#0E8C84" },
];

type Sort = "yangi" | "arzon" | "qimmat" | "yaqin";
const SORTS: ReadonlyArray<{ key: Sort; label: string }> = [
  { key: "yangi", label: "Yangi" },
  { key: "arzon", label: "Arzon" },
  { key: "qimmat", label: "Qimmat" },
  { key: "yaqin", label: "Yaqin" },
];
const FALLBACK_CATEGORY = {
  key: "boshqa" as const,
  name: "Boshqalar",
  icon: "📦",
  color: "#0E8C84",
};

function priceNumber(value: string) {
  const number = Number(value.replace(/[^0-9]/g, ""));
  return Number.isFinite(number) ? number : 0;
}

function formatListingTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";

  const now = new Date();
  const sameDay =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate();
  const time = new Intl.DateTimeFormat("uz-UZ", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);

  if (sameDay) return `Bugun, ${time}`;
  return new Intl.DateTimeFormat("uz-UZ", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function PublicListings({
  api,
  openedListingId,
  onOpenListing,
  authenticated,
  onNeedLogin,
  onOpenOwner,
}: Props) {
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [category, setCategory] = useState<ListingCategory | null>(null);
  const [rows, setRows] = useState<ListingRead[]>([]);
  const [sort, setSort] = useState<Sort>("yangi");
  const screenRef = useRef<HTMLElement>(null);
  const listPosition = useRef({ scrollTop: 0, publicId: "" });
  const previousOpenedId = useRef(openedListingId);

  useLayoutEffect(() => {
    if (previousOpenedId.current === openedListingId) return;
    previousOpenedId.current = openedListingId;
    const root = screenRef.current;
    const scroller = root?.closest(".app-shell__content");
    if (scroller)
      scroller.scrollTop = openedListingId ? 0 : listPosition.current.scrollTop;
    if (openedListingId) {
      root?.focus({ preventScroll: true });
    } else {
      const card = Array.from(
        root?.querySelectorAll<HTMLButtonElement>("[data-listing-id]") ?? [],
      ).find((button) => button.dataset.listingId === listPosition.current.publicId);
      card?.focus({ preventScroll: true });
    }
  }, [openedListingId]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    api
      .getListingCounts()
      .then((value) => {
        if (active) setCounts(value);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [api]);

  const sorted = useMemo(() => {
    const result = [...rows];
    if (sort === "arzon")
      return result.sort((a, b) => priceNumber(a.price) - priceNumber(b.price));
    if (sort === "qimmat")
      return result.sort((a, b) => priceNumber(b.price) - priceNumber(a.price));
    if (sort === "yangi") {
      return result.sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
    }
    return result;
  }, [rows, sort]);

  async function selectCategory(next: ListingCategory) {
    setCategory(next);
    setLoading(true);
    setError("");
    try {
      setRows(await api.getPublicListings({ cat: next }));
    } catch (reason) {
      setRows([]);
      setError(reason instanceof Error ? reason.message : "E'lonlar yuklanmadi.");
    } finally {
      setLoading(false);
    }
  }

  async function save(row: ListingRead) {
    if (!authenticated) {
      onNeedLogin?.();
      return;
    }
    setError("");
    setSaving(row.public_id);
    try {
      const value = await api.toggleListingSave(row.public_id);
      setRows((current) =>
        current.map((item) =>
          item.public_id === row.public_id ? { ...item, is_saved: value.saved } : item,
        ),
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "E'lon saqlanmadi.");
    } finally {
      setSaving(null);
    }
  }

  const openedRow = rows.find((row) => row.public_id === openedListingId);
  if (openedRow) {
    return (
      <main
        ref={screenRef}
        tabIndex={-1}
        aria-label={openedRow.title}
        className="public-listing-page-v1656"
      >
        <article className="listing-page-card">
          <h1 className="biz-title">{openedRow.title}</h1>
          {error ? (
            <p className="elon-hint" role="alert">
              {error}
            </p>
          ) : null}
          <ListingDetail
            compactMedia
            listing={openedRow}
            saving={saving === openedRow.public_id}
            onContact={() =>
              onOpenOwner(openedRow.owner_kind, openedRow.owner_public_id)
            }
            onSave={() => void save(openedRow)}
          />
        </article>
      </main>
    );
  }

  const selected = CATEGORIES.find((item) => item.key === category);
  return (
    <main ref={screenRef} className="public-listings-v1656">
      <section id="elonSection">
        <div className="sec-head" id="elonHead">
          <h2>E’lonlar</h2>
        </div>
        <p className="elon-hint" id="elonHint">
          Toifani tanlang — tegishli e’lonlar shu oynada chiqadi.
        </p>
        <div className="elon-row" id="elonRow">
          {CATEGORIES.map((item) => (
            <button
              className={`elon-card${category === item.key ? " on" : ""}`}
              key={item.key}
              type="button"
              onClick={() => void selectCategory(item.key)}
            >
              <span
                className="ec-ic"
                style={{ color: item.color, background: `${item.color}22` }}
              >
                {item.icon}
              </span>
              <span className="ec-name">{item.name}</span>
              <span className="ec-count">{counts[item.key] ?? 0} ta e&apos;lon</span>
            </button>
          ))}
        </div>
        <div id="elonList">
          {loading ? <div className="list-sub">Yuklanmoqda...</div> : null}
          {error ? (
            <p className="elon-hint" role="alert">
              {error}
            </p>
          ) : null}
          {!loading && !error && category && !rows.length ? (
            <div className="empty listing-category-empty">
              <h3>Bu toifada e&apos;lon yo&apos;q</h3>
              <p>{selected?.name} bo&apos;yicha hozircha e&apos;lonlar joylanmagan.</p>
            </div>
          ) : null}
          {!loading && rows.length ? (
            <>
              <div className="sort-row">
                {SORTS.map((item) => (
                  <button
                    className={`sort-chip${sort === item.key ? " on" : ""}`}
                    key={item.key}
                    type="button"
                    onClick={() => setSort(item.key)}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              <div className="list-sub">
                {selected?.name} — {sorted.length} ta e&apos;lon
              </div>
              <div className="public-listing-card-grid">
                {sorted.map((row) => {
                  const metadata =
                    CATEGORIES.find((item) => item.key === row.cat) ??
                    FALLBACK_CATEGORY;
                  const preview =
                    row.media.find((item) => item.type === "photo") ?? row.media[0];
                  const hasVideo = row.media.some((item) => item.type === "video");
                  return (
                    <article className="elon-wrap" key={row.public_id}>
                      <button
                        data-listing-id={row.public_id}
                        className="elon-item public-listing-card"
                        type="button"
                        onClick={() => {
                          listPosition.current = {
                            scrollTop:
                              screenRef.current?.closest(".app-shell__content")
                                ?.scrollTop ?? 0,
                            publicId: row.public_id,
                          };
                          onOpenListing(row.public_id, row.title);
                        }}
                      >
                        <span
                          className="public-listing-card-media"
                          style={{
                            background: `linear-gradient(135deg,${metadata.color}33,${metadata.color}14)`,
                          }}
                        >
                          {preview?.type === "photo" ? (
                            <img
                              alt={`${row.title} — asosiy rasm`}
                              loading="lazy"
                              src={preview.url}
                            />
                          ) : null}
                          {preview?.type === "video" ? (
                            <video
                              muted
                              playsInline
                              preload="metadata"
                              src={preview.url}
                            />
                          ) : null}
                          {!preview ? (
                            <span
                              className="public-listing-card-fallback"
                              aria-hidden="true"
                            >
                              {metadata.icon}
                            </span>
                          ) : null}
                          {preview?.type === "video" ? (
                            <span
                              className="public-listing-card-play"
                              aria-hidden="true"
                            >
                              ▶
                            </span>
                          ) : null}
                          {row.media.length ? (
                            <span className="public-listing-card-count">
                              1 / {row.media.length}
                            </span>
                          ) : null}
                        </span>
                        <span className="li-main public-listing-card-info">
                          <span className="li-title">{row.title}</span>
                          <span className="li-price">
                            {row.price || "Narx kelishilgan"}
                          </span>
                          <span className="li-meta">
                            {[row.address, formatListingTime(row.created_at)]
                              .filter(Boolean)
                              .join(" · ")}
                          </span>
                          {row.media.length ? (
                            <span className="public-listing-card-media-summary">
                              {row.media.filter((item) => item.type === "photo").length}{" "}
                              rasm
                              {hasVideo
                                ? ` · ${row.media.filter((item) => item.type === "video").length} video`
                                : ""}
                            </span>
                          ) : null}
                        </span>
                      </button>
                    </article>
                  );
                })}
              </div>
            </>
          ) : null}
        </div>
      </section>
    </main>
  );
}
