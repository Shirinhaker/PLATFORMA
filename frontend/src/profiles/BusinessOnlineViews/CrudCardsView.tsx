// `BusinessOnlineViews.tsx` dan ajratildi.
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../../api/business-online-types";
import { money } from "../business-profile-config";
import {
  Empty,
  InlineForm,
  SharedActions,
  notifyTime,
  recordId,
  recordNumber,
  recordText,
  statusLabel,
} from "./shared";

export function CrudCardsView({
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
  return (
    <section>
      <div className="business-online__toolbar">
        <p>{rows.length} ta yozuv</p>
        <button
          type="button"
          onClick={() => {
            actions.setDraft({ status: "active" });
            actions.setForm(resource);
          }}
        >
          {addLabel}
        </button>
      </div>
      {actions.form === resource && (
        <InlineForm
          title={addLabel.replace(/^\+\s*/, "Yangi ")}
          fields={fields}
          draft={actions.draft}
          setDraft={actions.setDraft}
          busy={actions.busy}
          onCancel={() => actions.setForm(null)}
          onSave={() => actions.create(resource, actions.draft)}
        />
      )}
      <div className="business-online__cards">
        {rows.length ? (
          rows.map((row, index) => (
            <article key={String(recordId(row, index))}>
              <header>
                <b>
                  {recordText(row, "title", "name", "caption") ||
                    `#${recordId(row, index)}`}
                </b>
                <span>{statusLabel(row.status)}</span>
              </header>
              <p>{recordText(row, "description", "descr", "caption", "note")}</p>
              {recordNumber(row, "price", "amount", "budget") > 0 && (
                <strong>{money(recordNumber(row, "price", "amount", "budget"))}</strong>
              )}
              <small>{notifyTime(row.created_at)}</small>
              <div className="business-online__card-actions">
                {extraAction?.(row, index)}
                <button
                  type="button"
                  disabled={actions.busy}
                  onClick={() =>
                    void actions.patch(resource, recordId(row, index), {
                      status:
                        recordText(row, "status") === "active" ? "paused" : "active",
                    })
                  }
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
          ))
        ) : (
          <Empty>{empty}</Empty>
        )}
      </div>
    </section>
  );
}
