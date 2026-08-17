import { useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  WarehouseItem,
  WarehouseMove,
  WarehouseProductionBatch,
  WarehouseStockType,
} from "../api/types";
import { WarehouseContent } from "./WarehouseContent";
import { WarehouseDialogs } from "./WarehouseDialogs";
import { quantity, type IngredientDraft, type MoveMode } from "./WarehouseShared";
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

function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
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
    api
      .getWarehouseItems()
      .then((value) => {
        if (active) setItems(value.items);
      })
      .catch((reason) => {
        if (active) setError(message(reason));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
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
        setIngredients(
          recipe.map((row) => ({
            item_id: row.item_id,
            name: row.name,
            unit: row.unit,
            qty: String(row.qty_per_unit),
          })),
        );
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
    const productionReceipt =
      dining && selected.stock_type === "ready_food" && moveMode === "receipt";
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
    setIngredients((current) => [
      ...current,
      {
        item_id: item.id,
        name: item.name,
        unit: item.unit,
        qty: "",
      },
    ]);
  }

  return (
    <main className="warehouse-v1656">
      <WarehouseContent
        busy={busy}
        canManage={canManage}
        canProduce={canProduce}
        canViewCosts={canViewCosts}
        dining={dining}
        error={error}
        groups={groups}
        loading={loading}
        stockType={stockType}
        visibleItems={visibleItems}
        onAddProduct={onAddProduct}
        onBack={onBack}
        onOpenHistory={openHistory}
        onOpenMove={openMove}
        onOpenProduction={openProduction}
        onReload={reload}
        onStockTypeChange={setStockType}
      />

      <WarehouseDialogs
        addIngredient={addIngredient}
        busy={busy}
        canManage={canManage}
        canViewCosts={canViewCosts}
        changeCost={changeCost}
        changeQty={changeQty}
        changeTotal={changeTotal}
        cost={cost}
        deleteMove={deleteMove}
        dining={dining}
        historyItem={historyItem}
        ingredients={ingredients}
        moveMode={moveMode}
        moves={moves}
        note={note}
        production={production}
        productionOpen={productionOpen}
        qty={qty}
        rawItems={rawItems}
        saveMove={saveMove}
        saveRecipe={saveRecipe}
        selected={selected}
        setIngredients={setIngredients}
        setNote={setNote}
        setSaveRecipe={setSaveRecipe}
        total={total}
        onCloseHistory={() => setHistoryItem(null)}
        onCloseMove={() => {
          setMoveMode(null);
          setSelected(null);
        }}
        onCloseProduction={() => setProductionOpen(false)}
      />
    </main>
  );
}
