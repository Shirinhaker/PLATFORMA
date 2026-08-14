import { useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  WarehouseItem,
  WarehouseMove,
  WarehouseProductionBatch,
  WarehouseStockType,
} from "../api/types";
import "./Warehouse.css";


export type WarehouseApi = Pick<
  ApiClient,
  | "getWarehouseItems"
  | "createWarehouseMove"
  | "deleteWarehouseMove"
  | "getWarehouseMoves"
  | "getWarehouseRecipe"
  | "getWarehouseProduction"
>;

type MoveMode = "receipt" | "outflow";
type IngredientDraft = {
  item_id: number;
  name: string;
  unit: string;
  qty: string;
};

function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

function money(value: number) {
  return `${Number(value || 0).toLocaleString("uz-UZ")} so‘m`;
}

function quantity(value: number) {
  return Number(value || 0).toLocaleString("uz-UZ", {
    maximumFractionDigits: 3,
  });
}

function dateTime(value: number) {
  return value
    ? new Date(value * 1000).toLocaleString("uz-UZ")
    : "—";
}

function numberValue(value: string) {
  const normalized = value.trim().replace(",", ".");
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : 0;
}

function groupItems(items: WarehouseItem[]) {
  const groups = new Map<string, { name: string; items: WarehouseItem[] }>();
  for (const item of items) {
    const key = item.group_id === null ? "none" : String(item.group_id);
    const current = groups.get(key) ?? {
      name: item.group_name || "Guruhsiz",
      items: [],
    };
    current.items.push(item);
    groups.set(key, current);
  }
  return [...groups.entries()].map(([id, value]) => ({ id, ...value }));
}

export function Warehouse({
  api,
  direction,
  canManage,
  canProduce,
  canViewCosts,
  onAddProduct,
  onBack,
}: {
  api: WarehouseApi;
  direction: string;
  canManage: boolean;
  canProduce: boolean;
  canViewCosts: boolean;
  onAddProduct?: (stockType: WarehouseStockType) => void;
  onBack: () => void;
}) {
  const dining = direction === "Umumiy ovqatlanish";
  const [items, setItems] = useState<WarehouseItem[]>([]);
  const [stockType, setStockType] = useState<WarehouseStockType>("ready_food");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [moveMode, setMoveMode] = useState<MoveMode | null>(null);
  const [selected, setSelected] = useState<WarehouseItem | null>(null);
  const [qty, setQty] = useState("");
  const [cost, setCost] = useState("");
  const [total, setTotal] = useState("");
  const [note, setNote] = useState("");
  const [ingredients, setIngredients] = useState<IngredientDraft[]>([]);
  const [saveRecipe, setSaveRecipe] = useState(true);
  const [historyItem, setHistoryItem] = useState<WarehouseItem | null>(null);
  const [moves, setMoves] = useState<WarehouseMove[]>([]);
  const [productionOpen, setProductionOpen] = useState(false);
  const [production, setProduction] = useState<WarehouseProductionBatch[]>([]);

  async function reload() {
    const value = await api.getWarehouseItems();
    setItems(value.items);
  }

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    api.getWarehouseItems()
      .then((value) => { if (active) setItems(value.items); })
      .catch((reason) => { if (active) setError(message(reason)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [api]);

  const visibleItems = dining
    ? items.filter((item) => item.stock_type === stockType)
    : items;
  const rawItems = items.filter((item) => item.stock_type === "raw_material");
  const groups = groupItems(visibleItems);

  async function openMove(item: WarehouseItem, mode: MoveMode) {
    setSelected(item);
    setMoveMode(mode);
    setQty("");
    setCost(item.cost_price ? String(item.cost_price) : "");
    setTotal("");
    setNote("");
    setIngredients([]);
    setSaveRecipe(true);
    setError("");
    if (mode === "receipt" && dining && item.stock_type === "ready_food") {
      setBusy(true);
      try {
        const recipe = await api.getWarehouseRecipe(item.id);
        setIngredients(recipe.map((row) => ({
          item_id: row.item_id,
          name: row.name,
          unit: row.unit,
          qty: String(row.qty_per_unit),
        })));
      } catch (reason) {
        setError(message(reason));
      } finally {
        setBusy(false);
      }
    }
  }

  function changeQty(value: string) {
    setQty(value);
    const numericQty = numberValue(value);
    const numericCost = numberValue(cost);
    if (numericQty > 0 && numericCost >= 0) {
      setTotal(String(Math.round(numericQty * numericCost)));
    }
  }

  function changeCost(value: string) {
    setCost(value.replace(/[^0-9]/g, ""));
    const numericQty = numberValue(qty);
    const numericCost = numberValue(value.replace(/[^0-9]/g, ""));
    if (numericQty > 0) setTotal(String(Math.round(numericQty * numericCost)));
  }

  function changeTotal(value: string) {
    const clean = value.replace(/[^0-9]/g, "");
    setTotal(clean);
    const numericQty = numberValue(qty);
    if (numericQty > 0) setCost(String(Math.round(numberValue(clean) / numericQty)));
  }

  async function saveMove() {
    if (!selected || !moveMode) return;
    const numericQty = numberValue(qty);
    if (numericQty <= 0) {
      setError("Miqdor kiritilmadi.");
      return;
    }
    if (moveMode === "outflow" && numericQty > selected.stock_qty) {
      setError(`Omborda faqat ${quantity(selected.stock_qty)} ${selected.unit} bor.`);
      return;
    }
    const productionReceipt = (
      dining && selected.stock_type === "ready_food" && moveMode === "receipt"
    );
    const ingredientRows = ingredients
      .map((row) => ({
        item_id: row.item_id,
        qty: numberValue(row.qty) * numericQty,
      }))
      .filter((row) => row.item_id > 0 && row.qty > 0);
    if (productionReceipt && ingredientRows.length === 0) {
      setError("Tayyor taom uchun sarflanadigan xomashyoni kiriting.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.createWarehouseMove({
        item_id: selected.id,
        delta: moveMode === "receipt" ? numericQty : -numericQty,
        reason: moveMode === "receipt" ? "kirim" : "chiqim",
        note: note.trim(),
        cost: productionReceipt ? 0 : numberValue(cost),
        ingredients: productionReceipt ? ingredientRows : [],
        save_recipe: productionReceipt && saveRecipe,
      });
      setMoveMode(null);
      setSelected(null);
      await reload();
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  async function openHistory(item: WarehouseItem) {
    setHistoryItem(item);
    setMoves([]);
    setBusy(true);
    setError("");
    try {
      setMoves(await api.getWarehouseMoves(item.id));
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  async function deleteMove(moveId: number) {
    if (!historyItem || !window.confirm("Bu Ombor harakati o‘chirilsinmi?")) return;
    setBusy(true);
    setError("");
    try {
      await api.deleteWarehouseMove(moveId);
      const [nextMoves] = await Promise.all([
        api.getWarehouseMoves(historyItem.id),
        reload(),
      ]);
      setMoves(nextMoves);
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  async function openProduction() {
    setProductionOpen(true);
    setProduction([]);
    setBusy(true);
    setError("");
    try {
      setProduction(await api.getWarehouseProduction());
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  function addIngredient() {
    const used = new Set(ingredients.map((row) => row.item_id));
    const item = rawItems.find((candidate) => !used.has(candidate.id));
    if (!item) {
      setError("Qo‘shish uchun boshqa xomashyo yo‘q.");
      return;
    }
    setIngredients((current) => [...current, {
      item_id: item.id,
      name: item.name,
      unit: item.unit,
      qty: "",
    }]);
  }

  return (
    <main className="warehouse-modular">
      <header className="warehouse-modular__heading">
        <button type="button" onClick={onBack}>← Kabinetga qaytish</button>
        <div>
          <h1>Ombor</h1>
          <p>Qoldiq, kirim-chiqim va FIFO hisobi</p>
        </div>
        <button type="button" disabled={loading || busy} onClick={() => void reload()}>
          Yangilash
        </button>
      </header>

      {error && <p className="warehouse-modular__error" role="alert">{error}</p>}
      {dining && (
        <div className="warehouse-modular__tabs" role="tablist" aria-label="Ombor turi">
          <button
            type="button"
            className={stockType === "ready_food" ? "on" : ""}
            onClick={() => setStockType("ready_food")}
          >
            Tayyor taomlar
          </button>
          <button
            type="button"
            className={stockType === "raw_material" ? "on" : ""}
            onClick={() => setStockType("raw_material")}
          >
            Xomashyolar
          </button>
        </div>
      )}

      <div className="warehouse-modular__tools">
        {onAddProduct && canManage && (
          <button type="button" onClick={() => onAddProduct(stockType)}>
            + Mahsulot qo‘shish
          </button>
        )}
        {dining && stockType === "ready_food" && (
          <button type="button" onClick={() => void openProduction()}>
            Ishlab chiqarish tarixi
          </button>
        )}
      </div>

      {loading ? <p className="warehouse-modular__empty">Ombor yuklanmoqda…</p> : null}
      {!loading && !visibleItems.length ? (
        <p className="warehouse-modular__empty">
          Omborda hisoblanadigan mahsulot yo‘q. Mahsulotda “Omborda hisoblash — Ha” ni tanlang.
        </p>
      ) : null}

      <div className="warehouse-modular__groups">
        {groups.map((group) => (
          <section className="warehouse-modular__group" key={group.id}>
            <h2>{group.name}</h2>
            <div className="warehouse-modular__cards">
              {group.items.map((item) => (
                <article className={item.low_stock ? "warehouse-modular__card low" : "warehouse-modular__card"} key={item.id}>
                  <div className="warehouse-modular__product">
                    <span className="warehouse-modular__photo">
                      {item.image_url ? <img src={item.image_url} alt="" /> : "📦"}
                    </span>
                    <div><strong>{item.name}</strong><small>{item.unit}</small></div>
                  </div>
                  <div className="warehouse-modular__stock">
                    <span>Qoldiq</span>
                    <strong>{quantity(item.stock_qty)} {item.unit}</strong>
                  </div>
                  {item.low_stock && (
                    <p className="warehouse-modular__warning">
                      ⚠ Kam qoldi · minimum {quantity(item.min_qty)} {item.unit}
                    </p>
                  )}
                  {canViewCosts && (
                    <dl>
                      <div><dt>Tannarx</dt><dd>{money(item.cost_price)}</dd></div>
                      <div><dt>Keyingi FIFO</dt><dd>{money(item.fifo_next_cost)}</dd></div>
                      <div><dt>Ombor qiymati</dt><dd>{money(item.fifo_value)}</dd></div>
                      <div><dt>Sotuv narxi</dt><dd>{item.price || "Kelishiladi"}</dd></div>
                    </dl>
                  )}
                  <div className="warehouse-modular__actions">
                    {(canManage || (canProduce && item.stock_type === "ready_food")) && (
                      <button type="button" onClick={() => void openMove(item, "receipt")}>+ Kirim</button>
                    )}
                    {canManage && (
                      <button type="button" onClick={() => void openMove(item, "outflow")}>− Chiqim</button>
                    )}
                    <button type="button" onClick={() => void openHistory(item)}>Tarix</button>
                  </div>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>

      {moveMode && selected && (
        <div className="warehouse-modular__modal-back" role="presentation">
          <section className="warehouse-modular__modal" role="dialog" aria-modal="true">
            <h2>{moveMode === "receipt" ? "Kirim" : "Chiqim"} · {selected.name}</h2>
            <label>
              Miqdor ({selected.unit})
              <input aria-label="Miqdor" inputMode="decimal" value={qty} onChange={(event) => changeQty(event.currentTarget.value)} />
            </label>
            {moveMode === "receipt" && !(dining && selected.stock_type === "ready_food") && canViewCosts && (
              <div className="warehouse-modular__cost-row">
                <label>1 {selected.unit} tannarxi<input aria-label="Tannarx" inputMode="numeric" value={cost} onChange={(event) => changeCost(event.currentTarget.value)} /></label>
                <label>Jami<input aria-label="Jami" inputMode="numeric" value={total} onChange={(event) => changeTotal(event.currentTarget.value)} /></label>
              </div>
            )}
            {moveMode === "receipt" && dining && selected.stock_type === "ready_food" && (
              <div className="warehouse-modular__recipe">
                <div className="warehouse-modular__recipe-title">
                  <strong>Retsept / sarflanadigan xomashyo</strong>
                  <button type="button" onClick={addIngredient}>+ Xomashyo</button>
                </div>
                {!ingredients.length && <p>Xomashyo tanlanmagan.</p>}
                {ingredients.map((row, index) => (
                  <div className="warehouse-modular__ingredient" key={`${row.item_id}:${index}`}>
                    <select
                      aria-label={`Xomashyo ${index + 1}`}
                      value={row.item_id}
                      onChange={(event) => {
                        const item = rawItems.find((candidate) => candidate.id === Number(event.currentTarget.value));
                        if (!item) return;
                        setIngredients((current) => current.map((candidate, candidateIndex) => (
                          candidateIndex === index ? { ...candidate, item_id: item.id, name: item.name, unit: item.unit } : candidate
                        )));
                      }}
                    >
                      {rawItems.filter((item) => (
                        item.id === row.item_id
                        || !ingredients.some((candidate) => candidate.item_id === item.id)
                      )).map((item) => (
                        <option key={item.id} value={item.id}>{item.name}</option>
                      ))}
                    </select>
                    <input
                      aria-label={`${row.name} bir dona uchun`}
                      inputMode="decimal"
                      placeholder={`1 ${selected.unit} uchun, ${row.unit}`}
                      value={row.qty}
                      onChange={(event) => setIngredients((current) => current.map((candidate, candidateIndex) => (
                        candidateIndex === index ? { ...candidate, qty: event.currentTarget.value } : candidate
                      )))}
                    />
                    <button type="button" aria-label={`${row.name}ni olib tashlash`} onClick={() => setIngredients((current) => current.filter((_, candidateIndex) => candidateIndex !== index))}>×</button>
                  </div>
                ))}
                <label className="warehouse-modular__check">
                  <input type="checkbox" checked={saveRecipe} onChange={(event) => setSaveRecipe(event.currentTarget.checked)} />
                  Retseptni keyingi kirim uchun saqlash
                </label>
              </div>
            )}
            <label>
              Izoh
              <input aria-label="Izoh" value={note} maxLength={200} onChange={(event) => setNote(event.currentTarget.value)} />
            </label>
            <div className="warehouse-modular__modal-actions">
              <button type="button" onClick={() => { setMoveMode(null); setSelected(null); }}>Bekor qilish</button>
              <button type="button" disabled={busy} onClick={() => void saveMove()}>Saqlash</button>
            </div>
          </section>
        </div>
      )}

      {historyItem && (
        <div className="warehouse-modular__modal-back" role="presentation">
          <section className="warehouse-modular__modal warehouse-modular__modal--wide" role="dialog" aria-modal="true">
            <h2>Harakatlar · {historyItem.name}</h2>
            {!moves.length && !busy ? <p>Harakatlar yo‘q.</p> : null}
            <div className="warehouse-modular__history">
              {moves.map((move) => (
                <article key={move.id}>
                  <div>
                    <strong className={move.delta > 0 ? "plus" : "minus"}>
                      {move.delta > 0 ? "+" : ""}{quantity(move.delta)} {move.unit}
                    </strong>
                    <span>{move.reason_text} · {dateTime(move.created_at)}</span>
                    <small>{move.note || "Izohsiz"} · {move.who}</small>
                  </div>
                  {canViewCosts && move.cost > 0 ? <b>{money(move.cost)} / {move.unit}</b> : null}
                  {move.can_delete && canManage ? (
                    <button type="button" disabled={busy} onClick={() => void deleteMove(move.id)}>O‘chirish</button>
                  ) : null}
                </article>
              ))}
            </div>
            <div className="warehouse-modular__modal-actions">
              <button type="button" onClick={() => setHistoryItem(null)}>Yopish</button>
            </div>
          </section>
        </div>
      )}

      {productionOpen && (
        <div className="warehouse-modular__modal-back" role="presentation">
          <section className="warehouse-modular__modal warehouse-modular__modal--wide" role="dialog" aria-modal="true">
            <h2>Ishlab chiqarish tarixi</h2>
            {!production.length && !busy ? <p>Ishlab chiqarish yozuvlari yo‘q.</p> : null}
            <div className="warehouse-modular__production">
              {production.map((batch) => <ProductionRow key={batch.id} batch={batch} canViewCosts={canViewCosts} />)}
            </div>
            <div className="warehouse-modular__modal-actions">
              <button type="button" onClick={() => setProductionOpen(false)}>Yopish</button>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}

function ProductionRow({
  batch,
  canViewCosts,
}: {
  batch: WarehouseProductionBatch;
  canViewCosts: boolean;
}) {
  return (
    <article>
      <div className="warehouse-modular__production-head">
        <strong>#{batch.id} · {batch.ready_name}</strong>
        <span>+{quantity(batch.qty)} {batch.ready_unit}</span>
      </div>
      <small>{dateTime(batch.created_at)} · {batch.who}{batch.note ? ` · ${batch.note}` : ""}</small>
      {canViewCosts && <p>Jami tannarx: {money(batch.total_cost)} · 1 {batch.ready_unit}: {money(batch.unit_cost)}</p>}
      <ul>
        {batch.inputs.map((input) => (
          <li key={`${batch.id}:${input.item_id}`}>
            {input.name}: {quantity(input.qty)} {input.unit}
            {canViewCosts ? ` · ${money(input.total_cost)}` : ""}
          </li>
        ))}
      </ul>
    </article>
  );
}
