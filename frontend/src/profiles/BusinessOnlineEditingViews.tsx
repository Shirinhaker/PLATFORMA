import { useMemo, type ReactNode } from "react";

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
  const filtered = useMemo(() => rows.filter((row) => {
    const rowKind = recordText(row, "kind", "item_type", "type") || "product";
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
              actions.setForm(groupNew);
            }}
          >
            + Guruh
          </button>
          <button
            type="button"
            onClick={() => {
              actions.setDraft({ kind: "product" });
              actions.setForm(itemNew);
            }}
          >
            + Mahsulot/xizmat
          </button>
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

      <div className="business-online__groups business-online__groups--editable">
        {groups.map((group, index) => (
          <article key={String(recordId(group, index))}>
            <b>{recordText(group, "name", "title") || "Guruh"}</b>
            <div>
              <button
                type="button"
                onClick={() => {
                  actions.setDraft({ ...group });
                  actions.setForm(groupEdit);
                }}
              >
                Tahrirlash
              </button>
              <button
                type="button"
                disabled={actions.busy}
                onClick={() => void actions.remove(
                  "item_groups",
                  recordId(group, index),
                )}
              >
                O‘chirish
              </button>
            </div>
          </article>
        ))}
      </div>

      <div className="business-online__product-grid">
        {filtered.length ? filtered.map((row, index) => (
          <article key={String(recordId(row, index))}>
            <div className="business-online__product-image">
              {recordText(row, "image_url", "photo_file")
                ? <img src={recordText(row, "image_url", "photo_file")} alt="" />
                : "🛍️"}
            </div>
            <h3>{recordText(row, "name", "title") || "Nomsiz"}</h3>
            <p>{recordText(row, "description", "descr", "note")}</p>
            <strong>{money(recordNumber(row, "price", "price_amount"))}</strong>
            <div className="business-online__card-actions">
              <button
                type="button"
                onClick={() => {
                  actions.setDraft({ ...row });
                  actions.setForm(itemEdit);
                }}
              >
                Tahrirlash
              </button>
              <button
                type="button"
                disabled={actions.busy}
                onClick={() => void actions.patch(
                  "items",
                  recordId(row, index),
                  { is_active: !Boolean(row.is_active ?? true) },
                )}
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
        )) : <Empty>Mos mahsulot yoki xizmat topilmadi.</Empty>}
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
