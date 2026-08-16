import { useCallback, useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type { FollowProfileRead } from "../api/types";
import "./FollowLists.css";

export type FollowListsApi = Pick<ApiClient, "getFollowers" | "getFollowing">;

type Props = {
  api: FollowListsApi;
  kind: "followers" | "following";
  onBack: () => void;
  onOpenProfile: (kind: "user" | "business", publicId: string) => void;
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

function initials(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0))
    .join("")
    .toLocaleUpperCase("uz");
}

function ProfileRow({ row, onOpen }: { row: FollowProfileRead; onOpen: () => void }) {
  const business = row.kind === "business";
  const sub = business
    ? `Biznes${row.info ? ` · ${row.info}` : ""}`
    : `Foydalanuvchi${row.info ? ` · ${row.info}` : ""}`;
  return (
    <button
      type="button"
      className="elon-item follow-list-v1656__row"
      aria-label={`${row.name} profilini ochish`}
      onClick={onOpen}
    >
      <span
        className="li-thumb follow-list-v1656__avatar"
        style={{ background: business ? "var(--primary-tint)" : "var(--amber-tint)" }}
      >
        {row.image_url ? (
          <img
            src={row.image_url}
            alt=""
            style={{
              objectPosition: `${row.crop_x}% ${row.crop_y}%`,
              transform: `scale(${row.crop_zoom})`,
            }}
          />
        ) : business ? (
          "🏪"
        ) : (
          initials(row.name) || "?"
        )}
      </span>
      <span className="li-main">
        <span className="li-title">{row.name}</span>
        <span className="li-meta">{sub}</span>
      </span>
      <span className="chev" aria-hidden="true">
        ›
      </span>
    </button>
  );
}

export function FollowListsV1656({ api, kind, onBack, onOpenProfile }: Props) {
  const [items, setItems] = useState<FollowProfileRead[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result =
        kind === "followers" ? await api.getFollowers() : await api.getFollowing();
      setItems(result.items);
      setCount(result.count);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setLoading(false);
    }
  }, [api, kind]);

  useEffect(() => {
    void load();
  }, [load]);

  const title = kind === "followers" ? "Obunachilarim" : "Kuzatayotganlar";
  return (
    <main className="follow-list-v1656">
      <header className="follow-list-v1656__header">
        <h1>{title}</h1>
        <button type="button" onClick={onBack}>
          Orqaga
        </button>
      </header>
      {error ? (
        <div className="follow-list-v1656__error" role="alert">
          <p>{error}</p>
          <button type="button" onClick={() => void load()}>
            Qayta urinish
          </button>
        </div>
      ) : loading ? (
        <p className="follow-list-v1656__loading">Yuklanmoqda…</p>
      ) : items.length ? (
        <section aria-label={title}>
          <div className="list-sub">
            {count} ta {kind === "followers" ? "obunachi" : "kuzatilmoqda"}
          </div>
          {items.map((row) => (
            <ProfileRow
              key={`${row.kind}:${row.public_id}`}
              row={row}
              onOpen={() => onOpenProfile(row.kind, row.public_id)}
            />
          ))}
        </section>
      ) : (
        <div className="empty follow-list-v1656__empty">
          <h3>{kind === "followers" ? "Obunachilar yo'q" : "Kuzatayotganlar yo'q"}</h3>
          <p>
            {kind === "followers"
              ? "Sizga obuna bo'lganlar shu yerda ko'rinadi."
              : "Biznes yoki mutaxassisni kuzatganingizda shu yerda ko'rinadi."}
          </p>
        </div>
      )}
    </main>
  );
}
