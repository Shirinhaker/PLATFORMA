// `BusinessOnlineViews.tsx` dan ajratildi.
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../../api/business-online-types";
import { money } from "../business-profile-config";
import { recordId, recordText } from "./shared";

export function PeopleView({
  rows,
  kind,
}: {
  rows: BusinessOnlineRecord[];
  busy: boolean;
  kind: "followers" | "following";
}) {
  return (
    <section>
      {rows.length ? (
        <>
          <div className="list-sub">
            {rows.length} ta {kind === "followers" ? "obunachi" : "kuzatilmoqda"}
          </div>
          {rows.map((row, index) => {
            const personKind = recordText(row, "kind", "target_kind") || "user";
            const name =
              recordText(row, "name", "target_name", "business_name") || "Profil";
            const initials = name
              .trim()
              .split(/\s+/)
              .slice(0, 2)
              .map((part) => part.charAt(0))
              .join("")
              .toLocaleUpperCase("uz");
            const info = recordText(row, "info", "username", "public_username");
            return (
              <article className="elon-item" key={String(recordId(row, index))}>
                <div
                  className="li-thumb"
                  style={{
                    background:
                      personKind === "business"
                        ? "var(--koprik-primary-tint)"
                        : "var(--koprik-amber-tint)",
                  }}
                >
                  {personKind === "business" ? "🏪" : initials || "?"}
                </div>
                <div className="li-main">
                  <div className="li-title">{name}</div>
                  <div className="li-meta">
                    {personKind === "business"
                      ? `Biznes · ${info}`
                      : `Foydalanuvchi${info ? ` · ${info}` : ""}`}
                  </div>
                </div>
                <span className="chev">›</span>
              </article>
            );
          })}
        </>
      ) : (
        <div className="empty people-empty">
          <h3>{kind === "followers" ? "Obunachilar yo'q" : "Kuzatayotganlar yo'q"}</h3>
          <p>
            {kind === "followers"
              ? "Sizga obuna bo'lganlar shu yerda ko'rinadi."
              : "Biznes yoki mutaxassisni kuzatganingizda shu yerda ko'rinadi."}
          </p>
        </div>
      )}
    </section>
  );
}
