import type { ReactNode } from "react";

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
