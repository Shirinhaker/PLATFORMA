import { useEffect, useMemo, useState } from "react";

import type { ApiClient } from "../api/client";
import type { ListingCategory, ListingRead } from "../api/types";
import { ListingDetailV1656 } from "./ListingDetailV1656";
import "./ListingsV1656.css";


type ListingsApi = Pick<
  ApiClient,
  "getListingCounts" | "getPublicListings" | "toggleListingSave"
>;

type Props = {
  api: ListingsApi;
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


export function PublicListingsV1656({
  api,
  authenticated,
  onNeedLogin,
  onOpenOwner,
}: Props) {
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [category, setCategory] = useState<ListingCategory | null>(null);
  const [rows, setRows] = useState<ListingRead[]>([]);
  const [sort, setSort] = useState<Sort>("yangi");
  const [opened, setOpened] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    api.getListingCounts()
      .then((value) => { if (active) setCounts(value); })
      .catch(() => undefined);
    return () => { active = false; };
  }, [api]);

  const sorted = useMemo(() => {
    const result = [...rows];
    if (sort === "arzon") return result.sort((a, b) => priceNumber(a.price) - priceNumber(b.price));
    if (sort === "qimmat") return result.sort((a, b) => priceNumber(b.price) - priceNumber(a.price));
    if (sort === "yangi") {
      return result.sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
    }
    return result;
  }, [rows, sort]);

  async function selectCategory(next: ListingCategory) {
    setCategory(next);
    setOpened(null);
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
      setRows((current) => current.map((item) => (
        item.public_id === row.public_id ? { ...item, is_saved: value.saved } : item
      )));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "E'lon saqlanmadi.");
    } finally {
      setSaving(null);
    }
  }

  const selected = CATEGORIES.find((item) => item.key === category);
  return (
    <main className="public-listings-v1656">
      <section id="elonSection">
        <div className="sec-head" id="elonHead"><h2>E’lonlar</h2></div>
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
          {error ? <p className="elon-hint" role="alert">{error}</p> : null}
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
              {sorted.map((row) => {
                const metadata = CATEGORIES.find((item) => item.key === row.cat) ?? FALLBACK_CATEGORY;
                const hasVideo = row.media.some((item) => item.type === "video");
                const open = opened === row.public_id;
                return (
                  <article className="elon-wrap" key={row.public_id}>
                    <button
                      className={`elon-item${open ? " on" : ""}`}
                      type="button"
                      onClick={() => setOpened(open ? null : row.public_id)}
                    >
                      <span
                        className="li-thumb"
                        style={{ background: `linear-gradient(135deg,${metadata.color}33,${metadata.color}14)` }}
                      >
                        <span>{metadata.icon}</span>
                        {hasVideo ? <span className="vbadge">▶</span> : null}
                      </span>
                      <span className="li-main">
                        <span className="li-title">{row.title}</span>
                        <span className="li-price">{row.price}</span>
                        <span className="li-meta">
                          {row.address}{row.media.length ? ` · 📎 ${row.media.length}` : ""}
                        </span>
                      </span>
                      <span className={`chev${open ? " down" : ""}`} aria-hidden="true">›</span>
                    </button>
                    {open ? (
                      <ListingDetailV1656
                        listing={row}
                        saving={saving === row.public_id}
                        onContact={() => onOpenOwner(row.owner_kind, row.owner_public_id)}
                        onSave={() => void save(row)}
                      />
                    ) : null}
                  </article>
                );
              })}
            </>
          ) : null}
        </div>
      </section>
    </main>
  );
}
