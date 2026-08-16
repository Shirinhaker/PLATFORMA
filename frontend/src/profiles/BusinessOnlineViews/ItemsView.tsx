// `BusinessOnlineViews.tsx` dan ajratildi.
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../../api/business-online-types";
import { money } from "../business-profile-config";
import {
  Empty,
  ITEM_FILTERS,
  InlineForm,
  SharedActions,
  recordId,
  recordNumber,
  recordText,
} from "./shared";

export function ItemsView({
  rows,
  groups,
  query,
  setQuery,
  kind,
  setKind,
  ...actions
}: SharedActions & {
  rows: BusinessOnlineRecord[];
  groups: BusinessOnlineRecord[];
  query: string;
  setQuery: (value: string) => void;
  kind: string;
  setKind: (value: string) => void;
}) {
  const filtered = useMemo(
    () =>
      rows.filter((row) => {
        const rowKind = recordText(row, "kind", "item_type", "type") || "product";
        const haystack = `${recordText(row, "name", "title")} ${recordText(
          row,
          "description",
          "descr",
        )}`.toLocaleLowerCase("uz");
        return (
          (kind === "all" || kind === rowKind) &&
          haystack.includes(query.toLocaleLowerCase("uz"))
        );
      }),
    [rows, kind, query],
  );

  return (
    <section>
      <div className="business-online__toolbar business-online__toolbar--wrap">
        <div className="business-online__search">
          <span>🔍</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.currentTarget.value)}
            placeholder="Tovar qidirish..."
          />
        </div>
        <div className="business-online__filters">
          {ITEM_FILTERS.map(([filterKey, label]) => (
            <button
              type="button"
              className={kind === filterKey ? "active" : ""}
              key={filterKey}
              onClick={() => setKind(filterKey)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="business-online__actions">
          <button
            type="button"
            onClick={() => {
              actions.setDraft({ kind: "product" });
              actions.setForm("group");
            }}
          >
            + Guruh
          </button>
          <button
            type="button"
            onClick={() => {
              actions.setDraft({ kind: "product" });
              actions.setForm("item");
            }}
          >
            + Mahsulot/xizmat
          </button>
        </div>
      </div>
      {actions.form && (
        <InlineForm
          title={
            actions.form === "group" ? "Yangi guruh" : "Yangi mahsulot yoki xizmat"
          }
          fields={
            actions.form === "group"
              ? ["name", "kind"]
              : ["name", "kind", "group_id", "price", "description"]
          }
          draft={actions.draft}
          setDraft={actions.setDraft}
          busy={actions.busy}
          onCancel={() => actions.setForm(null)}
          onSave={() =>
            actions.create(
              actions.form === "group" ? "item_groups" : "items",
              actions.draft,
            )
          }
        />
      )}
      <div className="business-online__groups">
        {groups.map((group, index) => (
          <span key={String(recordId(group, index))}>
            {recordText(group, "name", "title") || "Guruh"}
          </span>
        ))}
      </div>
      <div className="business-online__product-grid">
        {filtered.length ? (
          filtered.map((row, index) => (
            <article key={String(recordId(row, index))}>
              <div className="business-online__product-image">
                {recordText(row, "image_url", "photo_file") ? (
                  <img src={recordText(row, "image_url", "photo_file")} alt="" />
                ) : (
                  "🛍️"
                )}
              </div>
              <h3>{recordText(row, "name", "title") || "Nomsiz"}</h3>
              <p>{recordText(row, "description", "descr", "note")}</p>
              <strong>{money(recordNumber(row, "price", "price_amount"))}</strong>
              <div>
                <button
                  type="button"
                  disabled={actions.busy}
                  onClick={() =>
                    void actions.patch("items", recordId(row, index), {
                      is_active: !Boolean(row.is_active ?? true),
                    })
                  }
                >
                  {Boolean(row.is_active ?? true) ? "Yashirish" : "Ko‘rsatish"}
                </button>
                <button
                  type="button"
                  disabled={actions.busy}
                  onClick={() => void actions.remove("items", recordId(row, index))}
                >
                  O‘chirish
                </button>
              </div>
            </article>
          ))
        ) : (
          <Empty>Mos mahsulot yoki xizmat topilmadi.</Empty>
        )}
      </div>
    </section>
  );
}
