import { useMemo, useState } from "react";

import type { BusinessOnlineRecord } from "../api/business-online-types";
import {
  recordId,
  recordText,
  type SharedActions,
} from "./BusinessOnlineViews";


const FILTERS: ReadonlyArray<readonly [string, string]> = [
  ["all", "Barchasi"],
  ["product", "Mahsulotlar"],
  ["service", "Xizmatlar"],
];

type Props = SharedActions & {
  rows: BusinessOnlineRecord[];
  groups: BusinessOnlineRecord[];
  query: string;
  setQuery: (value: string) => void;
  kind: string;
  setKind: (value: string) => void;
};

type GroupBlock = {
  group: BusinessOnlineRecord | null;
  id: number | string | null;
  rows: BusinessOnlineRecord[];
};

function itemKind(row: BusinessOnlineRecord): "product" | "service" {
  return recordText(row, "kind", "item_type", "type") === "service"
    ? "service"
    : "product";
}

function kindText(value: unknown): string {
  return String(value ?? "") === "service" ? "Xizmat" : "Mahsulot";
}

function groupIdOf(row: BusinessOnlineRecord): string {
  const value = row.group_id ?? row.item_group_id ?? row.group;
  return value === null || value === undefined || value === ""
    ? ""
    : String(value);
}

function matches(row: BusinessOnlineRecord, query: string): boolean {
  if (!query) return true;
  const text = `${recordText(row, "name", "title")} ${recordText(
    row,
    "note",
    "description",
    "descr",
  )}`.toLocaleLowerCase("uz");
  return text.includes(query);
}

function priceText(row: BusinessOnlineRecord): string {
  const raw = row.price ?? row.price_amount ?? "";
  const numeric = Number(raw || 0);
  if (!Number.isFinite(numeric) || numeric <= 0) return "Narx kelishiladi";
  const unit = recordText(row, "unit");
  return `${String(raw)}${unit && unit !== "dona" ? ` / ${unit}` : ""}`;
}

function photo(row: BusinessOnlineRecord): string {
  return recordText(
    row,
    "photo_file",
    "image_url",
    "photo_url",
    "media_url",
  );
}

function CatalogMenu({
  label,
  open,
  onToggle,
  children,
}: {
  label: string;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
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

function ItemCard({
  row,
  id,
  busy,
  open,
  onToggle,
  onEdit,
  onMove,
  onDelete,
}: {
  row: BusinessOnlineRecord;
  id: number | string;
  busy: boolean;
  open: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onMove: () => void;
  onDelete: () => void;
}) {
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
      {open && (
        <div className="item-menu on">
          <button type="button" onClick={onEdit}>Tahrirlash</button>
          <button type="button" onClick={onMove}>Guruhini o'zgartirish</button>
          <button
            type="button"
            className="danger"
            disabled={busy}
            onClick={onDelete}
          >
            O'chirish
          </button>
        </div>
      )}
    </article>
  );
}

function AddCard({ onClick }: { onClick: () => void }) {
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

function EmptyState({ query, kind }: { query: string; kind: string }) {
  if (query.trim()) {
    return (
      <div className="empty item-empty">
        <h3>Hech narsa topilmadi</h3>
        <p>«{query.trim()}» bo'yicha tovar topilmadi.</p>
      </div>
    );
  }
  if (kind === "service") {
    return (
      <div className="empty item-empty">
        <h3>Xizmat yo'q</h3>
        <p>Bu turda hozircha tovar yo'q.</p>
      </div>
    );
  }
  if (kind === "product") {
    return (
      <div className="empty item-empty">
        <h3>Mahsulot yo'q</h3>
        <p>Bu turda hozircha tovar yo'q.</p>
      </div>
    );
  }
  return (
    <div className="empty item-empty">
      <h3>Hozircha tovar yo'q</h3>
      <p>Avval guruh qo'shing yoki Guruhsiz bo'limidagi + Tovar orqali boshlang.</p>
    </div>
  );
}

export function ItemsEditorView({
  rows,
  groups,
  query,
  setQuery,
  kind,
  setKind,
  ...actions
}: Props) {
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const normalizedQuery = query.trim().toLocaleLowerCase("uz");
  const searchActive = normalizedQuery.length > 0;
  const showAdd = !searchActive;

  const knownGroups = useMemo(
    () => new Set(groups.map((group, index) => String(recordId(group, index)))),
    [groups],
  );

  const blocks = useMemo<GroupBlock[]>(() => {
    const result: GroupBlock[] = [];
    groups.forEach((group, index) => {
      if (kind !== "all" && itemKind(group) !== kind) return;
      const id = recordId(group, index);
      let groupRows = rows.filter((row) => groupIdOf(row) === String(id));
      if (searchActive) {
        groupRows = groupRows.filter((row) => matches(row, normalizedQuery));
        if (groupRows.length === 0) return;
      }
      result.push({ group, id, rows: groupRows });
    });

    let ungrouped = rows.filter((row) => {
      const value = groupIdOf(row);
      return !value || !knownGroups.has(value);
    });
    if (kind !== "all") {
      ungrouped = ungrouped.filter((row) => itemKind(row) === kind);
    }
    if (searchActive) {
      ungrouped = ungrouped.filter((row) => matches(row, normalizedQuery));
    }
    const showEmptyUngrouped = !searchActive && kind === "all" && groups.length === 0;
    if (ungrouped.length > 0 || showEmptyUngrouped) {
      result.push({ group: null, id: null, rows: ungrouped });
    }
    return result;
  }, [groups, rows, kind, searchActive, normalizedQuery, knownGroups]);

  function editItem(row: BusinessOnlineRecord) {
    actions.setDraft({ ...row });
    actions.setForm("items:edit");
    setOpenMenu(null);
  }

  return (
    <section className="business-items">
      <div className="elon-hint item-intro">
        Guruhlar pastga, tovarlar esa o'ng-chapga suriladigan kartochka ko'rinishida chiqadi.
      </div>
      <div className="item-tools">
        <div className="item-search">
          <span className="ic">🔍</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.currentTarget.value)}
            placeholder="Tovar qidirish..."
            autoComplete="off"
          />
        </div>
        <div className="item-filter" role="group" aria-label="Tovar filtri">
          {FILTERS.map(([filter, label]) => (
            <button
              type="button"
              key={filter}
              className={kind === filter ? "sort-chip on" : "sort-chip"}
              onClick={() => setKind(filter)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {showAdd && (
        <button
          type="button"
          className="item-group-add-btn"
          onClick={() => {
            actions.setDraft({ kind: "product" });
            actions.setForm("item_groups:new");
          }}
        >
          + Guruh qo'shish
        </button>
      )}

      <div className="items-list">
        {blocks.map((block) => {
          const groupName = block.group
            ? recordText(block.group, "name", "title") || "Guruh"
            : "Guruhsiz";
          const subtitle = block.group
            ? `${kindText(block.group.kind)} guruhi · ${block.rows.length} ta`
            : `Guruh tanlanmagan · ${block.rows.length} ta`;
          const groupMenu = `group:${String(block.id ?? "none")}`;
          return (
            <section
              className="item-group-block"
              data-group-block={String(block.id ?? "none")}
              key={String(block.id ?? "none")}
            >
              <header className="item-group-head">
                <div className="item-group-title">
                  <h3>{groupName}</h3>
                  <p>{subtitle}</p>
                </div>
                {block.group && block.id !== null && (
                  <CatalogMenu
                    label={groupName}
                    open={openMenu === groupMenu}
                    onToggle={() => setOpenMenu(
                      openMenu === groupMenu ? null : groupMenu,
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => {
                        actions.setDraft({ ...block.group });
                        actions.setForm("item_groups:edit");
                        setOpenMenu(null);
                      }}
                    >
                      Nomini o'zgartirish
                    </button>
                    <button
                      type="button"
                      className="danger"
                      disabled={actions.busy}
                      onClick={() => void actions.remove("item_groups", block.id!)}
                    >
                      O'chirish
                    </button>
                  </CatalogMenu>
                )}
              </header>
              <div className="item-hrow">
                {block.rows.map((row, index) => {
                  const id = recordId(row, index);
                  const menu = `item:${String(id)}`;
                  return (
                    <ItemCard
                      key={String(id)}
                      row={row}
                      id={id}
                      busy={actions.busy}
                      open={openMenu === menu}
                      onToggle={() => setOpenMenu(openMenu === menu ? null : menu)}
                      onEdit={() => editItem(row)}
                      onMove={() => editItem(row)}
                      onDelete={() => void actions.remove("items", id)}
                    />
                  );
                })}
                {showAdd && (
                  <AddCard
                    onClick={() => {
                      actions.setDraft({
                        kind: block.group ? itemKind(block.group) : "product",
                        group_id: block.id,
                      });
                      actions.setForm("items:new");
                    }}
                  />
                )}
              </div>
            </section>
          );
        })}
        {blocks.length === 0 && <EmptyState query={query} kind={kind} />}
      </div>
    </section>
  );
}
