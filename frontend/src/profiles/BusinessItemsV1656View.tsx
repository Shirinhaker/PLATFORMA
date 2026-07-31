import { useMemo, useState, type ReactNode } from "react";

import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../api/business-online-types";
import {
  recordId,
  recordText,
  type SharedActions,
} from "./BusinessOnlineViews";


const ITEM_FILTERS: ReadonlyArray<readonly [string, string]> = [
  ["all", "Barchasi"],
  ["product", "Mahsulotlar"],
  ["service", "Xizmatlar"],
];

function cleanDraft(row: BusinessOnlineRecord): BusinessOnlineRecord {
  return Object.fromEntries(Object.entries(row).filter(([key]) => (
    !["id", "created_at", "updated_at"].includes(key)
    && !key.endsWith("_url")
  )));
}

function formId(
  resource: BusinessOnlineResource,
  mode: "new" | "edit",
) {
  return `${resource}:${mode}`;
}

function Empty({ children }: { children: ReactNode }) {
  return <div className="business-online__empty">{children}</div>;
}

function EditorForm({
  title,
  fields,
  draft,
  setDraft,
  busy,
  onCancel,
  onSave,
}: {
  title: string;
  fields: string[];
  draft: BusinessOnlineRecord;
  setDraft: (value: BusinessOnlineRecord) => void;
  busy: boolean;
  onCancel: () => void;
  onSave: () => Promise<void>;
}) {
  const labels: Record<string, string> = {
    name: "Nomi",
    title: "Sarlavha",
    kind: "Turi",
    group_id: "Guruh",
    price: "Narxi",
    description: "Tavsif",
    caption: "Qisqa matn",
    placement: "Joylashuvi",
    region: "Viloyat",
    district: "Tuman",
    category: "Toifa",
    media_type: "Media turi",
    media_url: "Media manzili",
    start_at: "Boshlanish vaqti",
    end_at: "Tugash vaqti",
  };
  const longText = new Set(["description", "caption"]);
  return (
    <div className="business-online__form">
      <h2>{title}</h2>
      {fields.map((field) => (
        <label key={field}>
          {labels[field] ?? field}
          {longText.has(field) ? (
            <textarea
              value={String(draft[field] ?? "")}
              onChange={(event) => setDraft({
                ...draft,
                [field]: event.currentTarget.value,
              })}
            />
          ) : (
            <input
              type={field === "price" ? "number" : "text"}
              value={String(draft[field] ?? "")}
              onChange={(event) => setDraft({
                ...draft,
                [field]: event.currentTarget.value,
              })}
            />
          )}
        </label>
      ))}
      <div>
        <button type="button" onClick={onCancel}>Bekor qilish</button>
        <button type="button" disabled={busy} onClick={() => void onSave()}>
          Saqlash
        </button>
      </div>
    </div>
  );
}

function itemKind(row: BusinessOnlineRecord): "product" | "service" {
  const raw = recordText(row, "kind", "item_type", "type").toLowerCase();
  return ["service", "xizmat", "queue", "booking", "medical"].includes(raw)
    ? "service"
    : "product";
}

function itemKindText(row: BusinessOnlineRecord): string {
  return itemKind(row) === "service" ? "Xizmat" : "Mahsulot";
}

function groupValue(row: BusinessOnlineRecord): unknown {
  return row.group_id ?? row.item_group_id ?? row.group;
}

function itemImage(row: BusinessOnlineRecord): string {
  const value = recordText(
    row,
    "image_url",
    "photo_url",
    "media_url",
    "image",
    "photo_file",
  );
  return /^(https?:|data:|blob:|\/)/i.test(value) ? value : "";
}

function unitSuffix(row: BusinessOnlineRecord): string {
  const unit = recordText(row, "unit");
  return unit && unit !== "dona" ? ` / ${unit}` : "";
}

function itemPriceText(row: BusinessOnlineRecord): string {
  const raw = row.price ?? row.price_amount ?? 0;
  const value = Number(raw);
  return Number.isFinite(value) && value > 0
    ? `${String(raw)}${unitSuffix(row)}`
    : "Narx kelishiladi";
}

function GroupMenu({
  name,
  open,
  busy,
  onToggle,
  onRename,
  onRemove,
}: {
  name: string;
  open: boolean;
  busy: boolean;
  onToggle: () => void;
  onRename: () => void;
  onRemove: () => void;
}) {
  return (
    <div className="item-group-actions">
      <button
        type="button"
        className="item-menu-btn"
        aria-label={`${name} amallari`}
        aria-expanded={open}
        onClick={onToggle}
      >
        ⋯
      </button>
      {open && (
        <div className="item-menu on">
          <button type="button" onClick={onRename}>Nomini o‘zgartirish</button>
          <button
            type="button"
            className="danger"
            disabled={busy}
            onClick={onRemove}
          >
            O‘chirish
          </button>
        </div>
      )}
    </div>
  );
}

function AddItemCard({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      className="item-add-card"
      aria-label="Tovar qo‘shish"
      onClick={onClick}
    >
      <span className="plus">+</span>
      <span>Tovar</span>
    </button>
  );
}

function ProductCard({
  row,
  busy,
  menuOpen,
  onMenuToggle,
  onEdit,
  onMove,
  onRemove,
}: {
  row: BusinessOnlineRecord;
  busy: boolean;
  menuOpen: boolean;
  onMenuToggle: () => void;
  onEdit: () => void;
  onMove: () => void;
  onRemove: () => void;
}) {
  const name = recordText(row, "name", "title") || "Nomsiz";
  const note = recordText(row, "note", "description", "descr") || "Izoh yo‘q";
  const image = itemImage(row);

  return (
    <article className="item-card2" data-item-card={String(row.id ?? "")}>
      <button
        type="button"
        className="item-menu-btn item-card-menu"
        aria-label={`${name} amallari`}
        aria-expanded={menuOpen}
        onClick={onMenuToggle}
      >
        ⋯
      </button>
      {image && (
        <div className="item-card2-img">
          <img src={image} alt="" loading="lazy" />
        </div>
      )}
      <div className="name">{name}</div>
      <div className="price">{itemPriceText(row)}</div>
      <div className="note">{note}</div>
      <span className="kind">{itemKindText(row)}</span>
      {menuOpen && (
        <div className="item-menu on">
          <button type="button" onClick={onEdit}>Tahrirlash</button>
          <button type="button" onClick={onMove}>Guruhini o‘zgartirish</button>
          <button
            type="button"
            className="danger"
            disabled={busy}
            onClick={onRemove}
          >
            O‘chirish
          </button>
        </div>
      )}
    </article>
  );
}

function ItemsEmpty({ query, kind }: { query: string; kind: string }) {
  if (query.trim()) {
    return (
      <Empty>
        <h3>Hech narsa topilmadi</h3>
        <p>«{query.trim()}» bo‘yicha tovar topilmadi.</p>
      </Empty>
    );
  }
  if (kind === "service") {
    return (
      <Empty>
        <h3>Xizmat yo‘q</h3>
        <p>Bu turda hozircha tovar yo‘q.</p>
      </Empty>
    );
  }
  if (kind === "product") {
    return (
      <Empty>
        <h3>Mahsulot yo‘q</h3>
        <p>Bu turda hozircha tovar yo‘q.</p>
      </Empty>
    );
  }
  return (
    <Empty>
      <h3>Hozircha tovar yo‘q</h3>
      <p>Avval guruh qo‘shing yoki Guruhsiz bo‘limidagi + Tovar orqali boshlang.</p>
    </Empty>
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
}: SharedActions & {
  rows: BusinessOnlineRecord[];
  groups: BusinessOnlineRecord[];
  query: string;
  setQuery: (value: string) => void;
  kind: string;
  setKind: (value: string) => void;
}) {
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const normalizedQuery = query.trim().toLocaleLowerCase("uz");
  const searchActive = normalizedQuery.length > 0;
  const showAdd = !searchActive;

  const groupNew = formId("item_groups", "new");
  const groupEdit = formId("item_groups", "edit");
  const itemNew = formId("items", "new");
  const itemEdit = formId("items", "edit");
  const editingId = actions.draft.id;

  const knownGroupIds = useMemo(
    () => new Set(groups.map((group, index) => String(recordId(group, index)))),
    [groups],
  );

  const sections = useMemo(() => groups
    .filter((group) => kind === "all" || itemKind(group) === kind)
    .map((group, index) => {
      const id = recordId(group, index);
      let items = rows.filter((row) => {
        const value = groupValue(row);
        return value !== null
          && value !== undefined
          && value !== ""
          && String(value) === String(id);
      });
      if (searchActive) {
        items = items.filter((row) => {
          const haystack = `${recordText(row, "name", "title")} ${recordText(
            row,
            "note",
            "description",
            "descr",
          )}`.toLocaleLowerCase("uz");
          return haystack.includes(normalizedQuery);
        });
      }
      return { group, id, items };
    })
    .filter((section) => !searchActive || section.items.length > 0), [
      groups,
      rows,
      kind,
      searchActive,
      normalizedQuery,
    ]);

  const ungrouped = useMemo(() => {
    let items = rows.filter((row) => {
      const value = groupValue(row);
      return value === null
        || value === undefined
        || value === ""
        || !knownGroupIds.has(String(value));
    });
    if (kind !== "all") {
      items = items.filter((row) => itemKind(row) === kind);
    }
    if (searchActive) {
      items = items.filter((row) => {
        const haystack = `${recordText(row, "name", "title")} ${recordText(
          row,
          "note",
          "description",
          "descr",
        )}`.toLocaleLowerCase("uz");
        return haystack.includes(normalizedQuery);
      });
    }
    return items;
  }, [rows, knownGroupIds, kind, searchActive, normalizedQuery]);

  const showUngrouped = ungrouped.length > 0
    || (!searchActive && kind === "all" && groups.length === 0);
  const hasBlocks = sections.length > 0 || showUngrouped;

  async function saveGroup() {
    if (actions.form === groupEdit && editingId !== undefined) {
      await actions.patch("item_groups", String(editingId), cleanDraft(actions.draft));
    } else {
      await actions.create("item_groups", cleanDraft(actions.draft));
    }
    actions.setForm(null);
    actions.setDraft({});
  }

  async function saveItem() {
    if (actions.form === itemEdit && editingId !== undefined) {
      await actions.patch("items", String(editingId), cleanDraft(actions.draft));
    } else {
      await actions.create("items", cleanDraft(actions.draft));
    }
    actions.setForm(null);
    actions.setDraft({});
  }

  function openItemForm(row: BusinessOnlineRecord) {
    actions.setDraft({ ...row });
    actions.setForm(itemEdit);
    setOpenMenu(null);
  }

  function startNewItem(groupId: number | string | null) {
    actions.setDraft({ kind: "product", group_id: groupId });
    actions.setForm(itemNew);
  }

  function renderProduct(row: BusinessOnlineRecord, itemIndex: number) {
    const itemId = recordId(row, itemIndex);
    const itemMenu = `item:${String(itemId)}`;
    return (
      <ProductCard
        key={String(itemId)}
        row={row}
        busy={actions.busy}
        menuOpen={openMenu === itemMenu}
        onMenuToggle={() => setOpenMenu((current) => (
          current === itemMenu ? null : itemMenu
        ))}
        onEdit={() => openItemForm(row)}
        onMove={() => openItemForm(row)}
        onRemove={() => void actions.remove("items", itemId)}
      />
    );
  }

  return (
    <section className="business-items">
      <p className="elon-hint business-items__intro">
        Guruhlar pastga, tovarlar esa o‘ng-chapga suriladigan kartochka ko‘rinishida chiqadi.
      </p>
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
        <div className="item-filter">
          {ITEM_FILTERS.map(([filterKey, label]) => (
            <button
              type="button"
              className={`sort-chip${kind === filterKey ? " on" : ""}`}
              key={filterKey}
              onClick={() => setKind(filterKey)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {[groupNew, groupEdit].includes(actions.form ?? "") && (
        <EditorForm
          title={actions.form === groupEdit ? "Guruhni tahrirlash" : "Yangi guruh"}
          fields={["name", "kind"]}
          draft={actions.draft}
          setDraft={actions.setDraft}
          busy={actions.busy}
          onCancel={() => actions.setForm(null)}
          onSave={saveGroup}
        />
      )}
      {[itemNew, itemEdit].includes(actions.form ?? "") && (
        <EditorForm
          title={actions.form === itemEdit
            ? "Mahsulot yoki xizmatni tahrirlash"
            : "Yangi mahsulot yoki xizmat"}
          fields={["name", "kind", "group_id", "price", "description"]}
          draft={actions.draft}
          setDraft={actions.setDraft}
          busy={actions.busy}
          onCancel={() => actions.setForm(null)}
          onSave={saveItem}
        />
      )}

      {showAdd && (
        <button
          type="button"
          className="item-group-add-btn"
          onClick={() => {
            actions.setDraft({ kind: "product" });
            actions.setForm(groupNew);
          }}
        >
          + Guruh qo‘shish
        </button>
      )}

      {!hasBlocks && <ItemsEmpty query={query} kind={kind} />}

      {sections.map(({ group, id, items }) => {
        const groupName = recordText(group, "name", "title") || "Guruh";
        const menuKey = `group:${String(id)}`;
        return (
          <section className="item-group-block" data-group-block={String(id)} key={String(id)}>
            <header className="item-group-head">
              <div className="item-group-title">
                <h3>{groupName}</h3>
                <p>{itemKindText(group)} guruhi · {items.length} ta</p>
              </div>
              <GroupMenu
                name={groupName}
                open={openMenu === menuKey}
                busy={actions.busy}
                onToggle={() => setOpenMenu((current) => (
                  current === menuKey ? null : menuKey
                ))}
                onRename={() => {
                  actions.setDraft({ ...group });
                  actions.setForm(groupEdit);
                  setOpenMenu(null);
                }}
                onRemove={() => void actions.remove("item_groups", id)}
              />
            </header>
            <div className="item-hrow">
              {items.map(renderProduct)}
              {showAdd && <AddItemCard onClick={() => startNewItem(id)} />}
            </div>
          </section>
        );
      })}

      {showUngrouped && (
        <section className="item-group-block" data-group-block="none">
          <header className="item-group-head">
            <div className="item-group-title">
              <h3>Guruhsiz</h3>
              <p>Guruh tanlanmagan · {ungrouped.length} ta</p>
            </div>
          </header>
          <div className="item-hrow">
            {ungrouped.map(renderProduct)}
            {showAdd && <AddItemCard onClick={() => startNewItem(null)} />}
          </div>
        </section>
      )}
    </section>
  );
}
