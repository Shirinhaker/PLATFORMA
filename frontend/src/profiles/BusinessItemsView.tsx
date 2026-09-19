import { useMemo, useState } from "react";

import type { BusinessOnlineRecord } from "../api/business-online-types";
import { recordId, recordText, type SharedActions } from "./BusinessOnlineViews";
import { cleanItemDraft, GroupForm, ItemForm } from "./BusinessItemsForms";
import {
  AddCard,
  CatalogMenu,
  EmptyState,
  FILTERS,
  type GroupBlock,
  ItemCard,
  groupIdOf,
  itemKind,
  itemKindWithGroup,
  kindText,
  matches,
} from "./BusinessItemsParts";
import { QUEUE_DIRECTIONS } from "./business-profile-config";

type Props = SharedActions & {
  rows: BusinessOnlineRecord[];
  groups: BusinessOnlineRecord[];
  query: string;
  setQuery: (value: string) => void;
  kind: string;
  setKind: (value: string) => void;
  direction?: string;
  uploadItemImage?: (file: File) => Promise<string>;
};

export function ItemsEditorView({
  rows,
  groups,
  query,
  setQuery,
  kind,
  setKind,
  direction = "",
  uploadItemImage,
  ...actions
}: Props) {
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [validationError, setValidationError] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<{
    resource: "items" | "item_groups";
    id: number | string;
    title: string;
    text: string;
  } | null>(null);
  const normalizedQuery = query.trim().toLocaleLowerCase("uz");
  const searchActive = normalizedQuery.length > 0;
  const showAdd = !searchActive;
  const groupNew = "item_groups:new";
  const groupEdit = "item_groups:edit";
  const itemNew = "items:new";
  const itemEdit = "items:edit";

  const knownGroups = useMemo(
    () => new Set(groups.map((group, index) => String(recordId(group, index)))),
    [groups],
  );

  const blocks = useMemo<GroupBlock[]>(() => {
    const result: GroupBlock[] = [];
    groups.forEach((group, index) => {
      if (kind !== "all" && itemKind(group) !== kind) return;
      const id = recordId(group, index);
      let grouped = rows.filter((row) => groupIdOf(row) === String(id));
      if (searchActive) {
        grouped = grouped.filter((row) => matches(row, normalizedQuery));
        if (!grouped.length) return;
      }
      result.push({ group, id, rows: grouped });
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
    if (ungrouped.length || (!searchActive && kind === "all" && groups.length === 0)) {
      result.push({ group: null, id: null, rows: ungrouped });
    }
    return result;
  }, [groups, rows, kind, searchActive, normalizedQuery, knownGroups]);

  function editItem(row: BusinessOnlineRecord) {
    actions.setDraft({ ...row });
    actions.setForm(itemEdit);
    setOpenMenu(null);
  }

  async function saveGroup() {
    const name = recordText(actions.draft, "name").trim();
    if (!name) {
      setValidationError("Guruh nomi kiritilishi shart.");
      return;
    }
    setValidationError("");
    const payload = cleanItemDraft({
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
    if (!name) {
      setValidationError("Nomi kiritilishi shart.");
      return;
    }
    setValidationError("");
    const effectiveKind = itemKindWithGroup(actions.draft, groups);
    const payload = cleanItemDraft({
      ...actions.draft,
      name,
      kind: effectiveKind,
      queue_enabled:
        effectiveKind === "service" &&
        QUEUE_DIRECTIONS.some((value) => value === direction)
          ? Number(actions.draft.queue_enabled ?? 0)
          : 0,
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

  return (
    <section className="business-items">
      {validationError && (
        <div className="app-toast on" role="alert">
          {validationError}
        </div>
      )}
      <div className="elon-hint item-intro">
        Guruhlar pastga, tovarlar esa o'ng-chapga suriladigan kartochka ko'rinishida
        chiqadi.
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
            setValidationError("");
            actions.setDraft({ kind: "product" });
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
          direction={direction}
          setDraft={actions.setDraft}
          busy={actions.busy}
          editing={actions.form === itemEdit}
          uploadImage={uploadItemImage}
          onCancel={() => actions.setForm(null)}
          onSave={saveItem}
        />
      )}

      <div className="items-list">
        {blocks.map((block) => {
          const group = block.group;
          const groupName = group
            ? recordText(group, "name", "title") || "Guruh"
            : "Guruhsiz";
          const subtitle = group
            ? `${kindText(group.kind)} guruhi · ${block.rows.length} ta`
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
                {group && block.id !== null && (
                  <CatalogMenu
                    label={groupName}
                    open={openMenu === groupMenu}
                    onToggle={() =>
                      setOpenMenu(openMenu === groupMenu ? null : groupMenu)
                    }
                  >
                    <button
                      type="button"
                      onClick={() => {
                        setValidationError("");
                        actions.setDraft({ ...group });
                        actions.setForm(groupEdit);
                        setOpenMenu(null);
                      }}
                    >
                      Nomini o'zgartirish
                    </button>
                    <button
                      type="button"
                      className="danger"
                      disabled={actions.busy}
                      onClick={() => {
                        setOpenMenu(null);
                        setConfirmDelete({
                          resource: "item_groups",
                          id: block.id as number | string,
                          title: "Guruhni o'chirish",
                          text: `'${groupName}' guruhi o'chirilsinmi?\n\nIchidagi tovarlar o'chmaydi, Guruhsiz bo'limiga o'tadi.`,
                        });
                      }}
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
                      direction={direction}
                      id={id}
                      busy={actions.busy}
                      open={openMenu === menu}
                      onToggle={() => setOpenMenu(openMenu === menu ? null : menu)}
                      onEdit={() => editItem(row)}
                      onMove={() => editItem(row)}
                      onDelete={() => {
                        setOpenMenu(null);
                        setConfirmDelete({
                          resource: "items",
                          id,
                          title: "Tovarni o'chirish",
                          text: "Bu tovar o'chirilsinmi?",
                        });
                      }}
                    />
                  );
                })}
                {showAdd && (
                  <AddCard
                    onClick={() => {
                      actions.setDraft({
                        kind: group ? itemKind(group) : "product",
                        group_id: block.id,
                        unit: "dona",
                        track_stock: 0,
                        stock_type: "ready_food",
                        min_qty: 0,
                      });
                      actions.setForm(itemNew);
                    }}
                  />
                )}
              </div>
            </section>
          );
        })}
        {!blocks.length && <EmptyState query={query} kind={kind} />}
      </div>
      {confirmDelete && (
        <>
          <button
            type="button"
            className="app-modal-back on"
            aria-label="Bekor qilish"
            onClick={() => setConfirmDelete(null)}
          />
          <div className="app-confirm on" role="dialog" aria-modal="true">
            <div className="acf-title">{confirmDelete.title}</div>
            <p className="acf-text">{confirmDelete.text}</p>
            <div className="acf-btns">
              <button
                type="button"
                className="acf-cancel"
                onClick={() => setConfirmDelete(null)}
              >
                Bekor qilish
              </button>
              <button
                type="button"
                className="acf-ok danger"
                disabled={actions.busy}
                onClick={() => {
                  const pending = confirmDelete;
                  void actions
                    .remove(pending.resource, pending.id)
                    .then(() => setConfirmDelete(null));
                }}
              >
                O'chirish
              </button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
