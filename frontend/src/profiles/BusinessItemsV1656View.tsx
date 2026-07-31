import { useEffect, useMemo, useState, type ReactNode } from "react";

import type { BusinessOnlineRecord } from "../api/business-online-types";
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

type Props = SharedActions & {
  rows: BusinessOnlineRecord[];
  groups: BusinessOnlineRecord[];
  query: string;
  setQuery: (value: string) => void;
  kind: string;
  setKind: (value: string) => void;
  direction?: string;
};

type Confirmation = {
  title: string;
  text: string;
  action: () => Promise<void>;
};

function cleanDraft(row: BusinessOnlineRecord): BusinessOnlineRecord {
  return Object.fromEntries(Object.entries(row).filter(([key]) => (
    !["id", "created_at", "updated_at"].includes(key)
    && !key.endsWith("_url")
  )));
}

function itemKind(row: BusinessOnlineRecord): "product" | "service" {
  return recordText(row, "kind", "item_type", "type") === "service"
    ? "service"
    : "product";
}

function itemKindText(value: unknown): string {
  return String(value ?? "") === "service" ? "Xizmat" : "Mahsulot";
}

function groupValue(row: BusinessOnlineRecord): unknown {
  return row.group_id ?? row.item_group_id ?? row.group;
}

function itemGroupValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "";
  return String(value);
}

function itemMatchesSearch(row: BusinessOnlineRecord, query: string): boolean {
  if (!query) return true;
  const haystack = `${recordText(row, "name", "title")} ${recordText(
    row,
    "note",
    "description",
    "descr",
  )}`.toLocaleLowerCase("uz");
  return haystack.includes(query);
}

function unitSuffix(value: unknown): string {
  const unit = String(value ?? "").trim();
  return unit && unit !== "dona" ? ` / ${unit}` : "";
}

function itemPriceText(row: BusinessOnlineRecord): string {
  const raw = row.price ?? row.price_amount ?? "";
  const numeric = Number(raw || 0);
  if (!Number.isFinite(numeric) || numeric <= 0) return "Narx kelishiladi";
  const shown = typeof raw === "string" ? raw.trim() : String(raw);
  return `${shown}${unitSuffix(row.unit)}`;
}

function itemImage(row: BusinessOnlineRecord): string {
  return recordText(
    row,
    "photo_file",
    "image_url",
    "photo_url",
    "media_url",
    "image",
  );
}

function itemNote(row: BusinessOnlineRecord, education: boolean): string {
  if (education && itemKind(row) === "service") {
    const mode = recordText(row, "course_mode") === "online"
      ? "Onlayn"
      : recordText(row, "course_mode") === "hybrid"
        ? "Aralash"
        : "Offline";
    const duration = recordText(row, "course_duration");
    const lesson = recordText(row, "lesson_duration");
    return [mode, duration, lesson ? `${lesson} daqiqa` : ""]
      .filter(Boolean)
      .join(" · ");
  }
  return recordText(row, "note", "description", "descr") || "Izoh yo'q";
}

function stockText(row: BusinessOnlineRecord): string {
  if (!Boolean(Number(row.track_stock ?? 0))) return "";
  const raw = Number(row.stock_qty ?? 0);
  const rounded = Math.round(raw * 1000) / 1000;
  return `Qoldiq: ${rounded} ${recordText(row, "unit") || "dona"}`;
}

function ActionMenu({
  label,
  open,
  onToggle,
  children,
  card = false,
}: {
  label: string;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
  card?: boolean;
}) {
  return (
    <div className={card ? "item-group-actions item-card-actions" : "item-group-actions"}>
      <button
        type="button"
        className={card ? "item-menu-btn item-card-menu" : "item-menu-btn"}
        aria-label={`${label} amallari`}
        aria-expanded={open}
        onClick={(event) => {
          event.stopPropagation();
          onToggle();
        }}
      >
        ⋯
      </button>
      {open && (
        <div
          className="item-menu on"
          onClick={(event) => event.stopPropagation()}
        >
          {children}
        </div>
      )}
    </div>
  );
}

function ConfirmDialog({
  confirmation,
  busy,
  onClose,
}: {
  confirmation: Confirmation;
  busy: boolean;
  onClose: () => void;
}) {
  return (
    <div className="item-confirm-backdrop" role="presentation">
      <section
        className="item-confirm-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="item-confirm-title"
      >
        <h2 id="item-confirm-title">{confirmation.title}</h2>
        <p>{confirmation.text}</p>
        <div>
          <button type="button" disabled={busy} onClick={onClose}>
            Bekor qilish
          </button>
          <button
            type="button"
            className="danger"
            disabled={busy}
            onClick={() => void confirmation.action()}
          >
            O'chirish
          </button>
        </div>
      </section>
    </div>
  );
}

function GroupForm({
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
          className={itemKind(draft) === "product" ? "on" : ""}
          onClick={() => setDraft({ ...draft, kind: "product" })}
        >
          Mahsulotlar
        </button>
        <button
          type="button"
          className={itemKind(draft) === "service" ? "on" : ""}
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

function ItemForm({
  draft,
  groups,
  busy,
  editing,
  education,
  setDraft,
  onCancel,
  onSave,
}: {
  draft: BusinessOnlineRecord;
  groups: BusinessOnlineRecord[];
  busy: boolean;
  editing: boolean;
  education: boolean;
  setDraft: (value: BusinessOnlineRecord) => void;
  onCancel: () => void;
  onSave: () => Promise<void>;
}) {
  const kind = education ? "service" : itemKind(draft);
  const trackStock = Boolean(Number(draft.track_stock ?? 0));
  return (
    <section className="item-form-card">
      <h2>{editing ? "Mahsulot yoki xizmatni tahrirlash" : education ? "Yangi kurs yoki xizmat" : "Yangi mahsulot yoki xizmat"}</h2>
      {!education && (
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
      )}
      <label>
        Guruh
        <select
          value={itemGroupValue(draft.group_id)}
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
                {recordText(group, "name", "title") || "Guruh"} — {itemKindText(group.kind)}
              </option>
            );
          })}
        </select>
      </label>
      <label>
        {education ? "Kurs yoki xizmat nomi" : "Nomi"}
        <input
          aria-label="Nomi"
          value={String(draft.name ?? "")}
          placeholder={education ? "Masalan: Ingliz tili A1" : "Masalan: Non"}
          onChange={(event) => setDraft({
            ...draft,
            name: event.currentTarget.value,
          })}
        />
      </label>
      <label>
        {education ? "Kurs narxi" : "Narxi"}
        <input
          value={String(draft.price ?? "")}
          placeholder="Masalan: 2 000 so'm"
          onChange={(event) => setDraft({
            ...draft,
            price: event.currentTarget.value,
          })}
        />
      </label>
      {education ? (
        <>
          <label>
            Ta'lim shakli
            <select
              value={String(draft.course_mode ?? "offline")}
              onChange={(event) => setDraft({
                ...draft,
                course_mode: event.currentTarget.value,
              })}
            >
              <option value="offline">Offline</option>
              <option value="online">Onlayn</option>
              <option value="hybrid">Aralash</option>
            </select>
          </label>
          <label>
            Kurs davomiyligi
            <input
              value={String(draft.course_duration ?? "")}
              placeholder="Masalan: 3 oy yoki 24 dars"
              onChange={(event) => setDraft({
                ...draft,
                course_duration: event.currentTarget.value,
              })}
            />
          </label>
          <label>
            Bitta dars davomiyligi
            <select
              value={String(draft.lesson_duration ?? 60)}
              onChange={(event) => setDraft({
                ...draft,
                lesson_duration: event.currentTarget.value,
              })}
            >
              {[45, 60, 90, 120, 180].map((minute) => (
                <option key={minute} value={minute}>{minute} daqiqa</option>
              ))}
            </select>
          </label>
        </>
      ) : (
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
              {UNITS.map((unit) => <option key={unit} value={unit}>{unit}</option>)}
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
        {education ? "Kurs tavsifi" : "Izoh — ixtiyoriy"}
        <textarea
          value={String(draft.note ?? draft.description ?? "")}
          placeholder={education ? "Kurs haqida batafsil ma'lumot" : "Izoh"}
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

function ItemCard({
  row,
  itemId,
  education,
  busy,
  menuOpen,
  onMenuToggle,
  onEdit,
  onMove,
  onDelete,
}: {
  row: BusinessOnlineRecord;
  itemId: number | string;
  education: boolean;
  busy: boolean;
  menuOpen: boolean;
  onMenuToggle: () => void;
  onEdit: () => void;
  onMove: () => void;
  onDelete: () => void;
}) {
  const name = recordText(row, "name", "title") || "Nomsiz";
  const image = itemImage(row);
  const stock = stockText(row);
  return (
    <article className="item-card2" data-item-card={String(itemId)}>
      <ActionMenu
        card
        label={name}
        open={menuOpen}
        onToggle={onMenuToggle}
      >
        <button type="button" onClick={onEdit}>Tahrirlash</button>
        <button type="button" onClick={onMove}>Guruhini o'zgartirish</button>
        <button type="button" className="danger" disabled={busy} onClick={onDelete}>
          O'chirish
        </button>
      </ActionMenu>
      {image && (
        <div className="item-card2-img">
          <img src={image} alt="" loading="lazy" />
        </div>
      )}
      <div className="name">{name}</div>
      <div className="price">{itemPriceText(row)}</div>
      <div className="note">{itemNote(row, education)}</div>
      <span className="kind">{itemKindText(row.kind)}</span>
      {stock && <span className="idesc item-stock-text">{stock}</span>}
    </article>
  );
}

function AddItemCard({
  education,
  onClick,
}: {
  education: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="item-add-card"
      aria-label={education ? "Kurs qo'shish" : "Tovar qo'shish"}
      onClick={onClick}
    >
      <span className="plus">+</span>
      <span>{education ? "Kurs" : "Tovar"}</span>
    </button>
  );
}

function GroupBlock({
  group,
  groupId,
  items,
  showAdd,
  education,
  busy,
  openMenu,
  setOpenMenu,
  onGroupEdit,
  onGroupDelete,
  onItemAdd,
  onItemEdit,
  onItemMove,
  onItemDelete,
}: {
  group: BusinessOnlineRecord | null;
  groupId: number | string | null;
  items: BusinessOnlineRecord[];
  showAdd: boolean;
  education: boolean;
  busy: boolean;
  openMenu: string | null;
  setOpenMenu: (value: string | null) => void;
  onGroupEdit: (group: BusinessOnlineRecord) => void;
  onGroupDelete: (group: BusinessOnlineRecord, id: number | string) => void;
  onItemAdd: (groupId: number | string | null, group?: BusinessOnlineRecord | null) => void;
  onItemEdit: (row: BusinessOnlineRecord) => void;
  onItemMove: (row: BusinessOnlineRecord) => void;
  onItemDelete: (row: BusinessOnlineRecord, id: number | string) => void;
}) {
  const real = Boolean(group);
  const title = group ? recordText(group, "name", "title") || "Guruh" : "Guruhsiz";
  const subtitle = group
    ? `${itemKindText(group.kind)} guruhi · ${items.length} ta`
    : `Guruh tanlanmagan · ${items.length} ta`;
  const groupMenuKey = `group:${String(groupId ?? "")}`;
  return (
    <section className="item-group-block" data-group-block={String(groupId ?? "none")}>
      <header className="item-group-head">
        <div className="item-group-title">
          <h3>{title}</h3>
          <p>{subtitle}</p>
        </div>
        {real && group && groupId !== null && (
          <ActionMenu
            label={title}
            open={openMenu === groupMenuKey}
            onToggle={() => setOpenMenu(openMenu === groupMenuKey ? null : groupMenuKey)}
          >
            <button type="button" onClick={() => onGroupEdit(group)}>
              Nomini o'zgartirish
            </button>
            <button
              type="button"
              className="danger"
              disabled={busy}
              onClick={() => onGroupDelete(group, groupId)}
            >
              O'chirish
            </button>
          </ActionMenu>
        )}
      </header>
      <div className="item-hrow">
        {items.map((row, index) => {
          const id = recordId(row, index);
          const menuKey = `item:${String(id)}`;
          return (
            <ItemCard
              key={String(id)}
              row={row}
              itemId={id}
              education={education}
              busy={busy}
              menuOpen={openMenu === menuKey}
              onMenuToggle={() => setOpenMenu(openMenu === menuKey ? null : menuKey)}
              onEdit={() => onItemEdit(row)}
              onMove={() => onItemMove(row)}
              onDelete={() => onItemDelete(row, id)}
            />
          );
        })}
        {showAdd && (
          <AddItemCard
            education={education}
            onClick={() => onItemAdd(groupId, group)}
          />
        )}
      </div>
    </section>
  );
}

export function ItemsEditorView({
  rows,
  groups,
  query,
  setQuery,
  kind,
  setKind,
  direction = "",
  ...actions
}: Props) {
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const education = direction === "Ta'lim faoliyati"
    || String((globalThis as { __businessDirection?: string }).__businessDirection ?? "") === "Ta'lim faoliyati";
  const activeKind = education ? "service" : kind;
  const normalizedQuery = query.trim().toLocaleLowerCase("uz");
  const searchActive = normalizedQuery.length > 0;
  const showAdd = !searchActive;

  const used = useMemo(
    () => new Set(groups.map((group, index) => String(recordId(group, index)))),
    [groups],
  );

  const groupBlocks = useMemo(() => groups.flatMap((group, index) => {
    if (activeKind !== "all" && itemKind(group) !== activeKind) return [];
    const id = recordId(group, index);
    let items = rows.filter((row) => (
      String(itemGroupValue(groupValue(row))) === String(id)
    ));
    if (searchActive) {
      items = items.filter((row) => itemMatchesSearch(row, normalizedQuery));
      if (items.length === 0) return [];
    }
    return [{ group, id, items }];
  }), [groups, rows, activeKind, searchActive, normalizedQuery]);

  const ungrouped = useMemo(() => {
    let items = rows.filter((row) => {
      const value = itemGroupValue(groupValue(row));
      return !value || !used.has(value);
    });
    if (activeKind !== "all") {
      items = items.filter((row) => itemKind(row) === activeKind);
    }
    if (searchActive) {
      items = items.filter((row) => itemMatchesSearch(row, normalizedQuery));
    }
    return items;
  }, [rows, used, activeKind, searchActive, normalizedQuery]);

  const showEmptyUngrouped = !searchActive && activeKind === "all" && groups.length === 0;
  const hasBlocks = groupBlocks.length > 0 || ungrouped.length > 0 || showEmptyUngrouped;
  const groupNew = "item_groups:new";
  const groupEdit = "item_groups:edit";
  const itemNew = "items:new";
  const itemEdit = "items:edit";

  useEffect(() => {
    const close = (event: MouseEvent) => {
      const target = event.target;
      if (!(target instanceof Element) || !target.closest(".item-group-actions")) {
        setOpenMenu(null);
      }
    };
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, []);

  async function saveGroup() {
    const name = recordText(actions.draft, "name").trim();
    if (!name) return;
    const payload = cleanDraft({
      ...actions.draft,
      name,
      kind: itemKind(actions.draft),
    });
    if (actions.form === groupEdit && actions.draft.id !== undefined) {
      await actions.patch("item_groups", String(actions.draft.id), payload);
    } else {
      await actions.create("item_groups", payload);
    }
    actions.setForm(null);
    actions.setDraft({});
  }

  async function saveItem() {
    const name = recordText(actions.draft, "name").trim();
    if (!name) return;
    const payload = cleanDraft({
      ...actions.draft,
      name,
      kind: education ? "service" : itemKind(actions.draft),
      group_id: actions.draft.group_id === "" ? null : actions.draft.group_id,
    });
    if (actions.form === itemEdit && actions.draft.id !== undefined) {
      await actions.patch("items", String(actions.draft.id), payload);
    } else {
      await actions.create("items", payload);
    }
    actions.setForm(null);
    actions.setDraft({});
  }

  function openNewItem(groupId: number | string | null, group?: BusinessOnlineRecord | null) {
    actions.setDraft({
      kind: education ? "service" : group ? itemKind(group) : activeKind === "service" ? "service" : "product",
      group_id: groupId,
      unit: "dona",
      track_stock: 0,
      course_mode: "offline",
      lesson_duration: 60,
    });
    actions.setForm(itemNew);
    setOpenMenu(null);
  }

  function openItem(row: BusinessOnlineRecord) {
    actions.setDraft({ ...row });
    actions.setForm(itemEdit);
    setOpenMenu(null);
  }

  function askGroupDelete(group: BusinessOnlineRecord, id: number | string) {
    const name = recordText(group, "name", "title") || "Guruh";
    setOpenMenu(null);
    setConfirmation({
      title: "Guruhni o'chirish",
      text: `'${name}' guruhi o'chirilsinmi?\n\nIchidagi tovarlar o'chmaydi, Guruhsiz bo'limiga o'tadi.`,
      action: async () => {
        await actions.remove("item_groups", id);
        setConfirmation(null);
      },
    });
  }

  function askItemDelete(row: BusinessOnlineRecord, id: number | string) {
    setOpenMenu(null);
    setConfirmation({
      title: "Tovarni o'chirish",
      text: `"${recordText(row, "name", "title") || "Tovar"}" o'chirilsinmi?`,
      action: async () => {
        await actions.remove("items", id);
        setConfirmation(null);
      },
    });
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
            type="text"
            value={query}
            placeholder={education ? "Kurs yoki xizmat qidirish..." : "Tovar qidirish..."}
            autoComplete="off"
            onChange={(event) => setQuery(event.currentTarget.value)}
          />
        </div>
        {!education && (
          <div className="item-filter" role="group" aria-label="Tovar filtri">
            {ITEM_FILTERS.map(([filterKey, label]) => (
              <button
                type="button"
                key={filterKey}
                className={activeKind === filterKey ? "sort-chip on" : "sort-chip"}
                onClick={() => setKind(filterKey)}
              >
                {label}
              </button>
            ))}
          </div>
        )}
      </div>

      {showAdd && (
        <button
          type="button"
          className="item-group-add-btn"
          onClick={() => {
            actions.setDraft({ kind: education ? "service" : "product" });
            actions.setForm(groupNew);
          }}
        >
          + Guruh qo'shish
        </button>
      )}

      {[groupNew, groupEdit].includes(actions.form ?? "") && (
        <GroupForm
          draft={actions.draft}
          setDraft={actions.setDraft}
          busy={actions.busy}
          editing={actions.form === groupEdit}
          onCancel={() => actions.setForm(null)}
          onSave={saveGroup}
        />
      )}
      {[itemNew, itemEdit].includes(actions.form ?? "") && (
        <ItemForm
          draft={actions.draft}
          groups={groups}
          busy={actions.busy}
          editing={actions.form === itemEdit}
          education={education}
          setDraft={actions.setDraft}
          onCancel={() => actions.setForm(null)}
          onSave={saveItem}
        />
      )}

      <div className="items-list">
        {groupBlocks.map(({ group, id, items }) => (
          <GroupBlock
            key={String(id)}
            group={group}
            groupId={id}
            items={items}
            showAdd={showAdd}
            education={education}
            busy={actions.busy}
            openMenu={openMenu}
            setOpenMenu={setOpenMenu}
            onGroupEdit={(value) => {
              actions.setDraft({ ...value });
              actions.setForm(groupEdit);
              setOpenMenu(null);
            }}
            onGroupDelete={askGroupDelete}
            onItemAdd={openNewItem}
            onItemEdit={openItem}
            onItemMove={openItem}
            onItemDelete={askItemDelete}
          />
        ))}
        {(ungrouped.length > 0 || showEmptyUngrouped) && (
          <GroupBlock
            group={null}
            groupId={null}
            items={ungrouped}
            showAdd={showAdd}
            education={education}
            busy={actions.busy}
            openMenu={openMenu}
            setOpenMenu={setOpenMenu}
            onGroupEdit={() => undefined}
            onGroupDelete={() => undefined}
            onItemAdd={openNewItem}
            onItemEdit={openItem}
            onItemMove={openItem}
            onItemDelete={askItemDelete}
          />
        )}
        {!hasBlocks && (
          <div className="empty item-empty">
            {searchActive ? (
              <>
                <h3>Hech narsa topilmadi</h3>
                <p>«{query.trim()}» bo'yicha tovar topilmadi.</p>
              </>
            ) : activeKind === "service" ? (
              <>
                <h3>Xizmat yo'q</h3>
                <p>Bu turda hozircha tovar yo'q.</p>
              </>
            ) : activeKind === "product" ? (
              <>
                <h3>Mahsulot yo'q</h3>
                <p>Bu turda hozircha tovar yo'q.</p>
              </>
            ) : (
              <>
                <h3>Hozircha tovar yo'q</h3>
                <p>Avval guruh qo'shing yoki Guruhsiz bo'limidagi + Tovar orqali boshlang.</p>
              </>
            )}
          </div>
        )}
      </div>

      {confirmation && (
        <ConfirmDialog
          confirmation={confirmation}
          busy={actions.busy}
          onClose={() => setConfirmation(null)}
        />
      )}
    </section>
  );
}
