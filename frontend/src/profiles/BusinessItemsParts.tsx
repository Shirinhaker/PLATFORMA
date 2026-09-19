import { useState, type ReactNode } from "react";
import { ItemDetailsDialog } from "../legacy/public/ItemDetailsDialog";

import type { BusinessOnlineRecord } from "../api/business-online-types";
import { recordId, recordText } from "./BusinessOnlineViews";

export const FILTERS: ReadonlyArray<readonly [string, string]> = [
  ["all", "Barchasi"],
  ["product", "Mahsulotlar"],
  ["service", "Xizmatlar"],
];

export type GroupBlock = {
  group: BusinessOnlineRecord | null;
  id: number | string | null;
  rows: BusinessOnlineRecord[];
};

export function itemKind(row: BusinessOnlineRecord): "product" | "service" {
  return recordText(row, "kind", "item_type", "type") === "service"
    ? "service"
    : "product";
}

export function itemKindWithGroup(
  row: BusinessOnlineRecord,
  groups: BusinessOnlineRecord[],
): "product" | "service" {
  const groupId = row.group_id;
  const group = groups.find(
    (candidate, index) => String(recordId(candidate, index)) === String(groupId ?? ""),
  );
  return group ? itemKind(group) : itemKind(row);
}

export function kindText(value: unknown): string {
  return String(value ?? "") === "service" ? "Xizmat" : "Mahsulot";
}

export function groupIdOf(row: BusinessOnlineRecord): string {
  const value = row.group_id ?? row.item_group_id ?? row.group;
  return value === null || value === undefined || value === "" ? "" : String(value);
}

export function matches(row: BusinessOnlineRecord, query: string): boolean {
  if (!query) return true;
  return `${recordText(row, "name", "title")} ${recordText(
    row,
    "note",
    "description",
    "descr",
  )}`
    .toLocaleLowerCase("uz")
    .includes(query);
}

function priceText(row: BusinessOnlineRecord): string {
  const raw = row.price ?? row.price_amount ?? "";
  if (raw === null || raw === undefined || raw === "" || raw === 0) {
    return "Narx kelishiladi";
  }
  const unit = recordText(row, "unit");
  return `${String(raw)}${unit && unit !== "dona" ? ` / ${unit}` : ""}`;
}

function photo(row: BusinessOnlineRecord): string {
  return recordText(row, "photo_file", "image_url", "photo_url", "media_url");
}

export function CatalogMenu({
  label,
  open,
  onToggle,
  children,
}: {
  label: string;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  return (
    <div className="item-group-actions">
      <button
        type="button"
        className="item-menu-btn"
        aria-label={`${label} amallari`}
        aria-expanded={open}
        onClick={onToggle}
      >
        ⋯
      </button>
      {open && <div className="item-menu on">{children}</div>}
    </div>
  );
}

export function ItemCard({
  row,
  id,
  busy,
  open,
  onToggle,
  onEdit,
  onMove,
  onDelete,
  direction = "",
}: {
  row: BusinessOnlineRecord;
  id: number | string;
  busy: boolean;
  open: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onMove: () => void;
  onDelete: () => void;
  direction?: string;
}) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const name = recordText(row, "name", "title") || "Nomsiz";
  const image = photo(row);
  return (
    <article className="item-card2" data-item-card={String(id)}>
      <button
        type="button"
        className="item-menu-btn item-card-menu"
        aria-label={`${name} amallari`}
        aria-expanded={open}
        onClick={onToggle}
      >
        ⋯
      </button>
      <button
        type="button"
        className="item-details-trigger"
        aria-label={`${name} haqida ma’lumot`}
        aria-haspopup="dialog"
        onClick={() => {
          if (open) onToggle();
          setDetailsOpen(true);
        }}
      >
        {image && (
          <div className="item-card2-img">
            <img src={image} alt="" loading="lazy" />
          </div>
        )}
        <div className="name">{name}</div>
        <div className="price">{priceText(row)}</div>
        <div className="note">
          {recordText(row, "note", "description", "descr") || "Izoh yo'q"}
        </div>
        <span className="kind">{kindText(row.kind)}</span>
      </button>
      {open && (
        <div className="item-menu on">
          <button type="button" onClick={onEdit}>
            Tahrirlash
          </button>
          <button type="button" onClick={onMove}>
            Guruhini o'zgartirish
          </button>
          <button type="button" className="danger" disabled={busy} onClick={onDelete}>
            O'chirish
          </button>
        </div>
      )}
      {detailsOpen ? (
        <ItemDetailsDialog
          education={direction === "Ta'lim faoliyati"}
          item={{
            kind: itemKind(row),
            name,
            image_url: image,
            price_text: priceText(row),
            unit: recordText(row, "unit"),
            note: recordText(row, "note", "description", "descr"),
            queue_enabled: Number(row.queue_enabled) === 1,
            course_mode:
              row.course_mode === "online" || row.course_mode === "hybrid"
                ? row.course_mode
                : "offline",
            course_duration: recordText(row, "course_duration"),
            lesson_duration: Number(row.lesson_duration) || 0,
            age_from: Number(row.age_from) || 0,
            age_to: Number(row.age_to) || 0,
            enrollment_status: row.enrollment_status === "closed" ? "closed" : "open",
          }}
          onClose={() => setDetailsOpen(false)}
        >
          <button
            type="button"
            className="btn btn-soft"
            disabled={busy}
            onClick={() => {
              setDetailsOpen(false);
              onEdit();
            }}
          >
            Tahrirlash
          </button>
        </ItemDetailsDialog>
      ) : null}
    </article>
  );
}

export function AddCard({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      className="item-add-card"
      aria-label="Tovar qo'shish"
      onClick={onClick}
    >
      <span className="plus">+</span>
      <span>Tovar</span>
    </button>
  );
}

export function EmptyState({ query, kind }: { query: string; kind: string }) {
  const state = query.trim()
    ? ["Hech narsa topilmadi", `«${query.trim()}» bo'yicha tovar topilmadi.`]
    : kind === "service"
      ? ["Xizmat yo'q", "Bu turda hozircha tovar yo'q."]
      : kind === "product"
        ? ["Mahsulot yo'q", "Bu turda hozircha tovar yo'q."]
        : [
            "Hozircha tovar yo'q",
            "Avval guruh qo'shing yoki Guruhsiz bo'limidagi + Tovar orqali boshlang.",
          ];
  return (
    <div className="empty item-empty">
      <h3>{state[0]}</h3>
      <p>{state[1]}</p>
    </div>
  );
}
