import type { Dispatch, SetStateAction } from "react";

import type {
  WarehouseItem,
  WarehouseMove,
  WarehouseProductionBatch,
} from "../api/types";
import {
  dateTime,
  money,
  quantity,
  type IngredientDraft,
  type MoveMode,
} from "./WarehouseShared";

export function WarehouseDialogs({
  moveMode,
  selected,
  dining,
  canViewCosts,
  qty,
  changeQty,
  cost,
  changeCost,
  total,
  changeTotal,
  ingredients,
  rawItems,
  addIngredient,
  setIngredients,
  saveRecipe,
  setSaveRecipe,
  note,
  setNote,
  busy,
  saveMove,
  onCloseMove,
  historyItem,
  moves,
  canManage,
  deleteMove,
  onCloseHistory,
  productionOpen,
  production,
  onCloseProduction,
}: {
  moveMode: MoveMode | null;
  selected: WarehouseItem | null;
  dining: boolean;
  canViewCosts: boolean;
  qty: string;
  changeQty(value: string): void;
  cost: string;
  changeCost(value: string): void;
  total: string;
  changeTotal(value: string): void;
  ingredients: IngredientDraft[];
  rawItems: WarehouseItem[];
  addIngredient(): void;
  setIngredients: Dispatch<SetStateAction<IngredientDraft[]>>;
  saveRecipe: boolean;
  setSaveRecipe(value: boolean): void;
  note: string;
  setNote(value: string): void;
  busy: boolean;
  saveMove(): Promise<void>;
  onCloseMove(): void;
  historyItem: WarehouseItem | null;
  moves: WarehouseMove[];
  canManage: boolean;
  deleteMove(moveId: number): Promise<void>;
  onCloseHistory(): void;
  productionOpen: boolean;
  production: WarehouseProductionBatch[];
  onCloseProduction(): void;
}) {
  return (
    <>
      {moveMode && selected && (
        <div className="warehouse-v1656__modal-back" role="presentation">
          <section className="warehouse-v1656__modal" role="dialog" aria-modal="true">
            <h2>
              {moveMode === "receipt" ? "Kirim" : "Chiqim"} · {selected.name}
            </h2>
            <label>
              Miqdor ({selected.unit})
              <input
                aria-label="Miqdor"
                inputMode="decimal"
                value={qty}
                onChange={(event) => changeQty(event.currentTarget.value)}
              />
            </label>
            {moveMode === "receipt" &&
              !(dining && selected.stock_type === "ready_food") &&
              canViewCosts && (
                <div className="warehouse-v1656__cost-row">
                  <label>
                    1 {selected.unit} tannarxi
                    <input
                      aria-label="Tannarx"
                      inputMode="numeric"
                      value={cost}
                      onChange={(event) => changeCost(event.currentTarget.value)}
                    />
                  </label>
                  <label>
                    Jami
                    <input
                      aria-label="Jami"
                      inputMode="numeric"
                      value={total}
                      onChange={(event) => changeTotal(event.currentTarget.value)}
                    />
                  </label>
                </div>
              )}
            {moveMode === "receipt" &&
              dining &&
              selected.stock_type === "ready_food" && (
                <div className="warehouse-v1656__recipe">
                  <div className="warehouse-v1656__recipe-title">
                    <strong>Retsept / sarflanadigan xomashyo</strong>
                    <button type="button" onClick={addIngredient}>
                      + Xomashyo
                    </button>
                  </div>
                  {!ingredients.length && <p>Xomashyo tanlanmagan.</p>}
                  {ingredients.map((row, index) => (
                    <div
                      className="warehouse-v1656__ingredient"
                      key={`${row.item_id}:${index}`}
                    >
                      <select
                        aria-label={`Xomashyo ${index + 1}`}
                        value={row.item_id}
                        onChange={(event) => {
                          const item = rawItems.find(
                            (candidate) =>
                              candidate.id === Number(event.currentTarget.value),
                          );
                          if (!item) return;
                          setIngredients((current) =>
                            current.map((candidate, candidateIndex) =>
                              candidateIndex === index
                                ? {
                                    ...candidate,
                                    item_id: item.id,
                                    name: item.name,
                                    unit: item.unit,
                                  }
                                : candidate,
                            ),
                          );
                        }}
                      >
                        {rawItems
                          .filter(
                            (item) =>
                              item.id === row.item_id ||
                              !ingredients.some(
                                (candidate) => candidate.item_id === item.id,
                              ),
                          )
                          .map((item) => (
                            <option key={item.id} value={item.id}>
                              {item.name}
                            </option>
                          ))}
                      </select>
                      <input
                        aria-label={`${row.name} bir dona uchun`}
                        inputMode="decimal"
                        placeholder={`1 ${selected.unit} uchun, ${row.unit}`}
                        value={row.qty}
                        onChange={(event) =>
                          setIngredients((current) =>
                            current.map((candidate, candidateIndex) =>
                              candidateIndex === index
                                ? { ...candidate, qty: event.currentTarget.value }
                                : candidate,
                            ),
                          )
                        }
                      />
                      <button
                        type="button"
                        aria-label={`${row.name}ni olib tashlash`}
                        onClick={() =>
                          setIngredients((current) =>
                            current.filter(
                              (_, candidateIndex) => candidateIndex !== index,
                            ),
                          )
                        }
                      >
                        ×
                      </button>
                    </div>
                  ))}
                  <label className="warehouse-v1656__check">
                    <input
                      type="checkbox"
                      checked={saveRecipe}
                      onChange={(event) => setSaveRecipe(event.currentTarget.checked)}
                    />
                    Retseptni keyingi kirim uchun saqlash
                  </label>
                </div>
              )}
            <label>
              Izoh
              <input
                aria-label="Izoh"
                value={note}
                maxLength={200}
                onChange={(event) => setNote(event.currentTarget.value)}
              />
            </label>
            <div className="warehouse-v1656__modal-actions">
              <button type="button" onClick={onCloseMove}>
                Bekor qilish
              </button>
              <button type="button" disabled={busy} onClick={() => void saveMove()}>
                Saqlash
              </button>
            </div>
          </section>
        </div>
      )}

      {historyItem && (
        <div className="warehouse-v1656__modal-back" role="presentation">
          <section
            className="warehouse-v1656__modal warehouse-v1656__modal--wide"
            role="dialog"
            aria-modal="true"
          >
            <h2>Harakatlar · {historyItem.name}</h2>
            {!moves.length && !busy ? <p>Harakatlar yo‘q.</p> : null}
            <div className="warehouse-v1656__history">
              {moves.map((move) => (
                <article key={move.id}>
                  <div>
                    <strong className={move.delta > 0 ? "plus" : "minus"}>
                      {move.delta > 0 ? "+" : ""}
                      {quantity(move.delta)} {move.unit}
                    </strong>
                    <span>
                      {move.reason_text} · {dateTime(move.created_at)}
                    </span>
                    <small>
                      {move.note || "Izohsiz"} · {move.who}
                    </small>
                  </div>
                  {canViewCosts && move.cost > 0 ? (
                    <b>
                      {money(move.cost)} / {move.unit}
                    </b>
                  ) : null}
                  {move.can_delete && canManage ? (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void deleteMove(move.id)}
                    >
                      O‘chirish
                    </button>
                  ) : null}
                </article>
              ))}
            </div>
            <div className="warehouse-v1656__modal-actions">
              <button type="button" onClick={onCloseHistory}>
                Yopish
              </button>
            </div>
          </section>
        </div>
      )}

      {productionOpen && (
        <div className="warehouse-v1656__modal-back" role="presentation">
          <section
            className="warehouse-v1656__modal warehouse-v1656__modal--wide"
            role="dialog"
            aria-modal="true"
          >
            <h2>Ishlab chiqarish tarixi</h2>
            {!production.length && !busy ? (
              <p>Ishlab chiqarish yozuvlari yo‘q.</p>
            ) : null}
            <div className="warehouse-v1656__production">
              {production.map((batch) => (
                <ProductionRow
                  key={batch.id}
                  batch={batch}
                  canViewCosts={canViewCosts}
                />
              ))}
            </div>
            <div className="warehouse-v1656__modal-actions">
              <button type="button" onClick={onCloseProduction}>
                Yopish
              </button>
            </div>
          </section>
        </div>
      )}
    </>
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
      <div className="warehouse-v1656__production-head">
        <strong>
          #{batch.id} · {batch.ready_name}
        </strong>
        <span>
          +{quantity(batch.qty)} {batch.ready_unit}
        </span>
      </div>
      <small>
        {dateTime(batch.created_at)} · {batch.who}
        {batch.note ? ` · ${batch.note}` : ""}
      </small>
      {canViewCosts && (
        <p>
          Jami tannarx: {money(batch.total_cost)} · 1 {batch.ready_unit}:{" "}
          {money(batch.unit_cost)}
        </p>
      )}
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
