import { useMemo, useState, type ReactNode } from "react";

import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../api/business-online-types";
import {
  recordId,
  recordNumber,
  recordText,
  type SharedActions,
} from "./BusinessOnlineViews";
import { money } from "./business-profile-config";


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

function ActionMenu({
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
    <div className="business-items__menu">
      <button
        type="button"
        className="business-items__menu-trigger"
        aria-label={`${label} amallari`}
        aria-expanded={open}
        onClick={onToggle}
      >
        •••
      </button>
      {open && <div className="business-items__menu-panel">{children}</div>}
    </div>
  );
}

function AddItemTile({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      className="business-items__add-tile"
      aria-label="Tovar qo‘shish"
      onClick={onClick}
    >
      <span>+</span>
      <b>Tovar</b>
    </button>
  );
}

function ProductCard({
  row,
  index,
  busy,
  menuOpen,
  onMenuToggle,
  onEdit,
  onToggleActive,
  onRemove,
}: {
  row: BusinessOnlineRecord;
  index: number;
  busy: boolean;
  menuOpen: boolean;
  onMenuToggle: () => void;
  onEdit: () => void;
  onToggleActive: () => void;
  onRemove: () => void;
}) {
  const name = recordText(row, "name", "title") || "Nomsiz";
  const description = recordText(row, "description", "descr", "note") || "Izoh yo‘q";
  const price = recordNumber(row, "price", "price_amount");
  const kind = itemKind(row);
  const image = itemImage(row);
  const active = Boolean(row.is_active ?? true);

  return (
    <article className="business-items__card">
      {image && (
        <div className="business-items__card-image">
          <img
            src={image}
            alt=""
            onError={(event) => {
              event.currentTarget.parentElement?.remove();
            }}
          />
        </div>
      )}
      <ActionMenu
        label={name}
        open={menuOpen}
        onToggle={onMenuToggle}
      >
        <button type="button" onClick={onEdit}>Tahrirlash</button>
        <button type="button" disabled={busy} onClick={onToggleActive}>
          {active ? "Yashirish" : "Ko‘rsatish"}
        </button>
        <button type="button" disabled={busy} onClick={onRemove}>O‘chirish</button>
      </ActionMenu>
      <h3>{name}</h3>
      <strong className={price > 0 ? "" : "negotiable"}>
        {price > 0 ? money(price) : "Narx kelishiladi"}
      </strong>
      <p>{description}</p>
      <span className="business-items__kind">
        {kind === "service" ? "Xizmat" : "Mahsulot"}
      </span>
    </article>
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
  const filtered = useMemo(() => rows.filter((row) => {
    const rowKind = itemKind(row);
    const haystack = `${recordText(row, "name", "title")} ${recordText(
      row,
      "description",
      "descr",
    )}`.toLocaleLowerCase("uz");
    return (kind === "all" || kind === rowKind)
      && haystack.includes(query.toLocaleLowerCase("uz"));
  }), [rows, kind, query]);

  const groupNew = formId("item_groups", "new");
  const groupEdit = formId("item_groups", "edit");
  const itemNew = formId("items", "new");
  const itemEdit = formId("items", "edit");
  const editingId = actions.draft.id;

  const sections = useMemo(() => groups.map((group, index) => {
    const id = recordId(group, index);
    const items = filtered.filter((row) => {
      const value = groupValue(row);
      return value !== null
        && value !== undefined
        && value !== ""
        && String(value) === String(id);
    });
    return { group, id, items, index };
  }), [groups, filtered]);

  const knownGroupIds = useMemo(
    () => new Set(groups.map((group, index) => String(recordId(group, index)))),
    [groups],
  );
  const ungrouped = useMemo(() => filtered.filter((row) => {
    const value = groupValue(row);
    return value === null
      || value === undefined
      || value === ""
      || !knownGroupIds.has(String(value));
  }), [filtered, knownGroupIds]);

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

  function startNewItem(groupId: number | string | null) {
    actions.setDraft({ kind: "product", group_id: groupId });
    actions.setForm(itemNew);
  }

  return (
    <section className="business-items">
      <p className="business-items__intro">
        Guruhlar pastga, tovarlar esa o‘ng-chapga suriladigan kartochka ko‘rinishida chiqadi.
      </p>
      <div className="business-online__search business-items__search">
        <span>🔍</span>
        <input
          value={query}
          onChange={(event) => setQuery(event.currentTarget.value)}
          placeholder="Tovar qidirish..."
        />
      </div>
      <div className="business-online__filters business-items__filters">
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
      <button
        type="button"
        className="business-items__add-group"
        onClick={() => {
          actions.setDraft({ kind: "product" });
          actions.setForm(groupNew);
        }}
      >
        + Guruh qo‘shish
      </button>

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

      <div className="business-items__sections">
        {sections.map(({ group, id, items: groupItems, index }) => {
          const groupName = recordText(group, "name", "title") || "Guruh";
          const groupKind = itemKind(group) === "service"
            ? "Xizmat guruhi"
            : "Mahsulot guruhi";
          const menuKey = `group:${String(id)}`;
          return (
            <section className="business-items__section" key={String(id)}>
              <header className="business-items__section-heading">
                <div>
                  <h2>{groupName}</h2>
                  <p>{groupKind} · {groupItems.length} ta</p>
                </div>
                <ActionMenu
                  label={groupName}
                  open={openMenu === menuKey}
                  onToggle={() => setOpenMenu((current) => (
                    current === menuKey ? null : menuKey
                  ))}
                >
                  <button
                    type="button"
                    onClick={() => {
                      actions.setDraft({ ...group });
                      actions.setForm(groupEdit);
                      setOpenMenu(null);
                    }}
                  >
                    Tahrirlash
                  </button>
                  <button
                    type="button"
                    disabled={actions.busy}
                    onClick={() => void actions.remove("item_groups", id)}
                  >
                    O‘chirish
                  </button>
                </ActionMenu>
              </header>
              <div className="business-items__rail">
                {groupItems.map((row, itemIndex) => {
                  const itemId = recordId(row, itemIndex);
                  const itemMenu = `item:${String(itemId)}`;
                  return (
                    <ProductCard
                      key={String(itemId)}
                      row={row}
                      index={itemIndex}
                      busy={actions.busy}
                      menuOpen={openMenu === itemMenu}
                      onMenuToggle={() => setOpenMenu((current) => (
                        current === itemMenu ? null : itemMenu
                      ))}
                      onEdit={() => {
                        actions.setDraft({ ...row });
                        actions.setForm(itemEdit);
                        setOpenMenu(null);
                      }}
                      onToggleActive={() => void actions.patch(
                        "items",
                        itemId,
                        { is_active: !Boolean(row.is_active ?? true) },
                      )}
                      onRemove={() => void actions.remove("items", itemId)}
                    />
                  );
                })}
                <AddItemTile onClick={() => startNewItem(id)} />
              </div>
            </section>
          );
        })}

        <section className="business-items__section">
          <header className="business-items__section-heading">
            <div>
              <h2>Guruhsiz</h2>
              <p>Guruhlanmagan · {ungrouped.length} ta</p>
            </div>
          </header>
          <div className="business-items__rail">
            {ungrouped.map((row, itemIndex) => {
              const itemId = recordId(row, itemIndex);
              const itemMenu = `item:${String(itemId)}`;
              return (
                <ProductCard
                  key={String(itemId)}
                  row={row}
                  index={itemIndex}
                  busy={actions.busy}
                  menuOpen={openMenu === itemMenu}
                  onMenuToggle={() => setOpenMenu((current) => (
                    current === itemMenu ? null : itemMenu
                  ))}
                  onEdit={() => {
                    actions.setDraft({ ...row });
                    actions.setForm(itemEdit);
                    setOpenMenu(null);
                  }}
                  onToggleActive={() => void actions.patch(
                    "items",
                    itemId,
                    { is_active: !Boolean(row.is_active ?? true) },
                  )}
                  onRemove={() => void actions.remove("items", itemId)}
                />
              );
            })}
            <AddItemTile onClick={() => startNewItem(null)} />
          </div>
        </section>
      </div>
    </section>
  );
}


export function CrudEditorView({
  resource,
  rows,
  addLabel,
  empty,
  fields,
  extraAction,
  ...actions
}: SharedActions & {
  resource: BusinessOnlineResource;
  rows: BusinessOnlineRecord[];
  addLabel: string;
  empty: string;
  fields: string[];
  extraAction?: (row: BusinessOnlineRecord, index: number) => ReactNode;
}) {
  const newForm = formId(resource, "new");
  const editForm = formId(resource, "edit");
  const editingId = actions.draft.id;

  async function save() {
    if (actions.form === editForm && editingId !== undefined) {
      await actions.patch(resource, String(editingId), cleanDraft(actions.draft));
    } else {
      await actions.create(resource, cleanDraft(actions.draft));
    }
    actions.setForm(null);
    actions.setDraft({});
  }

  return (
    <section>
      <div className="business-online__toolbar">
        <p>{rows.length} ta yozuv</p>
        <button
          type="button"
          onClick={() => {
            actions.setDraft({ status: "active" });
            actions.setForm(newForm);
          }}
        >
          {addLabel}
        </button>
      </div>
      {[newForm, editForm].includes(actions.form ?? "") && (
        <EditorForm
          title={actions.form === editForm
            ? "Yozuvni tahrirlash"
            : addLabel.replace(/^\+\s*/, "Yangi ")}
          fields={fields}
          draft={actions.draft}
          setDraft={actions.setDraft}
          busy={actions.busy}
          onCancel={() => actions.setForm(null)}
          onSave={save}
        />
      )}
      <div className="business-online__cards">
        {rows.length ? rows.map((row, index) => (
          <article key={String(recordId(row, index))}>
            <header>
              <b>
                {recordText(row, "title", "name", "caption")
                  || `#${recordId(row, index)}`}
              </b>
              <span>{recordText(row, "status") || "Holat yo‘q"}</span>
            </header>
            <p>{recordText(row, "description", "descr", "caption", "note")}</p>
            {recordNumber(row, "price", "amount", "budget") > 0 && (
              <strong>{money(recordNumber(row, "price", "amount", "budget"))}</strong>
            )}
            <div className="business-online__card-actions">
              {extraAction?.(row, index)}
              <button
                type="button"
                onClick={() => {
                  actions.setDraft({ ...row });
                  actions.setForm(editForm);
                }}
              >
                Tahrirlash
              </button>
              <button
                type="button"
                disabled={actions.busy}
                onClick={() => void actions.patch(
                  resource,
                  recordId(row, index),
                  {
                    status: recordText(row, "status") === "active"
                      ? "paused"
                      : "active",
                  },
                )}
              >
                {recordText(row, "status") === "active"
                  ? "To‘xtatish"
                  : "Faollashtirish"}
              </button>
              <button
                type="button"
                disabled={actions.busy}
                onClick={() => void actions.remove(resource, recordId(row, index))}
              >
                O‘chirish
              </button>
            </div>
          </article>
        )) : <Empty>{empty}</Empty>}
      </div>
    </section>
  );
}
