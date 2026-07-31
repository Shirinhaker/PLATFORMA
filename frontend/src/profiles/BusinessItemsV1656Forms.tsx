import type { BusinessOnlineRecord } from "../api/business-online-types";
import { recordId, recordText } from "./BusinessOnlineViews";


const UNITS = [
  "dona",
  "kg",
  "g",
  "litr",
  "ml",
  "metr",
  "sm",
  "m²",
  "to'plam",
  "quti",
  "juft",
  "porsiya",
  "soat",
  "kun",
  "marta",
];

export function cleanItemDraft(
  row: BusinessOnlineRecord,
): BusinessOnlineRecord {
  return Object.fromEntries(Object.entries(row).filter(([key]) => (
    !["id", "created_at", "updated_at"].includes(key)
    && !key.endsWith("_url")
  )));
}

function rowKind(row: BusinessOnlineRecord): "product" | "service" {
  return recordText(row, "kind", "item_type", "type") === "service"
    ? "service"
    : "product";
}

export function GroupForm({
  draft,
  setDraft,
  busy,
  editing,
  onCancel,
  onSave,
}: {
  draft: BusinessOnlineRecord;
  setDraft: (value: BusinessOnlineRecord) => void;
  busy: boolean;
  editing: boolean;
  onCancel: () => void;
  onSave: () => Promise<void>;
}) {
  return (
    <section className="item-form-card">
      <h2>{editing ? "Guruh nomini o'zgartirish" : "Yangi guruh"}</h2>
      <label>
        Guruh nomi
        <input
          aria-label="Guruh nomi"
          value={String(draft.name ?? "")}
          onChange={(event) => setDraft({
            ...draft,
            name: event.currentTarget.value,
          })}
        />
      </label>
      <div className="item-kind-row" role="group" aria-label="Guruh turi">
        <button
          type="button"
          className={rowKind(draft) === "product" ? "on" : ""}
          onClick={() => setDraft({ ...draft, kind: "product" })}
        >
          Mahsulotlar
        </button>
        <button
          type="button"
          className={rowKind(draft) === "service" ? "on" : ""}
          onClick={() => setDraft({ ...draft, kind: "service" })}
        >
          Xizmatlar
        </button>
      </div>
      <div className="item-form-actions">
        <button type="button" onClick={onCancel}>Bekor qilish</button>
        <button type="button" disabled={busy} onClick={() => void onSave()}>
          Saqlash
        </button>
      </div>
    </section>
  );
}

export function ItemForm({
  draft,
  groups,
  setDraft,
  busy,
  editing,
  onCancel,
  onSave,
}: {
  draft: BusinessOnlineRecord;
  groups: BusinessOnlineRecord[];
  setDraft: (value: BusinessOnlineRecord) => void;
  busy: boolean;
  editing: boolean;
  onCancel: () => void;
  onSave: () => Promise<void>;
}) {
  const kind = rowKind(draft);
  const trackStock = Boolean(Number(draft.track_stock ?? 0));
  const note = String(draft.note ?? draft.description ?? "");

  return (
    <section className="item-form-card">
      <h2>
        {editing
          ? "Mahsulot yoki xizmatni tahrirlash"
          : "Yangi mahsulot yoki xizmat"}
      </h2>
      <div className="item-kind-row" role="group" aria-label="Tovar turi">
        <button
          type="button"
          className={kind === "product" ? "on" : ""}
          onClick={() => setDraft({ ...draft, kind: "product" })}
        >
          Mahsulot
        </button>
        <button
          type="button"
          className={kind === "service" ? "on" : ""}
          onClick={() => setDraft({ ...draft, kind: "service" })}
        >
          Xizmat
        </button>
      </div>
      <label>
        Guruh
        <select
          value={String(draft.group_id ?? "")}
          onChange={(event) => setDraft({
            ...draft,
            group_id: event.currentTarget.value || null,
          })}
        >
          <option value="">Guruhsiz</option>
          {groups.map((group, index) => {
            const id = recordId(group, index);
            return (
              <option key={String(id)} value={String(id)}>
                {recordText(group, "name", "title") || "Guruh"}
                {" — "}
                {rowKind(group) === "service" ? "Xizmat" : "Mahsulot"}
              </option>
            );
          })}
        </select>
      </label>
      <label>
        Nomi
        <input
          aria-label="Nomi"
          value={String(draft.name ?? "")}
          placeholder="Masalan: Non"
          onChange={(event) => setDraft({
            ...draft,
            name: event.currentTarget.value,
          })}
        />
      </label>
      <label>
        Narxi
        <input
          value={String(draft.price ?? "")}
          placeholder="Masalan: 2 000 so'm"
          onChange={(event) => setDraft({
            ...draft,
            price: event.currentTarget.value,
          })}
        />
      </label>
      {kind === "product" && (
        <>
          <label>
            O'lchov birligi
            <select
              value={String(draft.unit ?? "dona")}
              onChange={(event) => setDraft({
                ...draft,
                unit: event.currentTarget.value,
              })}
            >
              {UNITS.map((unit) => (
                <option key={unit} value={unit}>{unit}</option>
              ))}
            </select>
          </label>
          <label>
            Omborda hisoblash
            <select
              value={trackStock ? "1" : "0"}
              onChange={(event) => setDraft({
                ...draft,
                track_stock: Number(event.currentTarget.value),
              })}
            >
              <option value="0">Yo'q</option>
              <option value="1">Ha — qoldiq yuritiladi</option>
            </select>
          </label>
        </>
      )}
      <label>
        Izoh — ixtiyoriy
        <textarea
          value={note}
          placeholder="Izoh"
          onChange={(event) => setDraft({
            ...draft,
            note: event.currentTarget.value,
            description: event.currentTarget.value,
          })}
        />
      </label>
      <div className="item-form-actions">
        <button type="button" onClick={onCancel}>Bekor qilish</button>
        <button type="button" disabled={busy} onClick={() => void onSave()}>
          Saqlash
        </button>
      </div>
    </section>
  );
}
