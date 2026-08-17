import type { WarehouseItem, WarehouseStockType } from "../api/types";
import { money, quantity, type MoveMode } from "./WarehouseShared";

type WarehouseGroup = {
  id: string;
  name: string;
  items: WarehouseItem[];
};

export function WarehouseContent({
  onBack,
  loading,
  busy,
  onReload,
  error,
  dining,
  stockType,
  onStockTypeChange,
  onAddProduct,
  canManage,
  onOpenProduction,
  visibleItems,
  groups,
  canViewCosts,
  canProduce,
  onOpenMove,
  onOpenHistory,
}: {
  onBack(): void;
  loading: boolean;
  busy: boolean;
  onReload(): Promise<void>;
  error: string;
  dining: boolean;
  stockType: WarehouseStockType;
  onStockTypeChange(stockType: WarehouseStockType): void;
  onAddProduct?: (stockType: WarehouseStockType) => void;
  canManage: boolean;
  onOpenProduction(): Promise<void>;
  visibleItems: WarehouseItem[];
  groups: WarehouseGroup[];
  canViewCosts: boolean;
  canProduce: boolean;
  onOpenMove(item: WarehouseItem, mode: MoveMode): Promise<void>;
  onOpenHistory(item: WarehouseItem): Promise<void>;
}) {
  return (
    <>
      <header className="warehouse-v1656__heading">
        <button type="button" onClick={onBack}>
          ← Kabinetga qaytish
        </button>
        <div>
          <h1>Ombor</h1>
          <p>Qoldiq, kirim-chiqim va FIFO hisobi</p>
        </div>
        <button
          type="button"
          disabled={loading || busy}
          onClick={() => void onReload()}
        >
          Yangilash
        </button>
      </header>

      {error && (
        <p className="warehouse-v1656__error" role="alert">
          {error}
        </p>
      )}
      {dining && (
        <div className="warehouse-v1656__tabs" role="tablist" aria-label="Ombor turi">
          <button
            type="button"
            className={stockType === "ready_food" ? "on" : ""}
            onClick={() => onStockTypeChange("ready_food")}
          >
            Tayyor taomlar
          </button>
          <button
            type="button"
            className={stockType === "raw_material" ? "on" : ""}
            onClick={() => onStockTypeChange("raw_material")}
          >
            Xomashyolar
          </button>
        </div>
      )}

      <div className="warehouse-v1656__tools">
        {onAddProduct && canManage && (
          <button type="button" onClick={() => onAddProduct(stockType)}>
            + Mahsulot qo‘shish
          </button>
        )}
        {dining && stockType === "ready_food" && (
          <button type="button" onClick={() => void onOpenProduction()}>
            Ishlab chiqarish tarixi
          </button>
        )}
      </div>

      {loading ? <p className="warehouse-v1656__empty">Ombor yuklanmoqda…</p> : null}
      {!loading && !visibleItems.length ? (
        <p className="warehouse-v1656__empty">
          Omborda hisoblanadigan mahsulot yo‘q. Mahsulotda “Omborda hisoblash — Ha” ni
          tanlang.
        </p>
      ) : null}

      <div className="warehouse-v1656__groups">
        {groups.map((group) => (
          <section className="warehouse-v1656__group" key={group.id}>
            <h2>{group.name}</h2>
            <div className="warehouse-v1656__cards">
              {group.items.map((item) => (
                <article
                  className={
                    item.low_stock
                      ? "warehouse-v1656__card low"
                      : "warehouse-v1656__card"
                  }
                  key={item.id}
                >
                  <div className="warehouse-v1656__product">
                    <span className="warehouse-v1656__photo">
                      {item.image_url ? <img src={item.image_url} alt="" /> : "📦"}
                    </span>
                    <div>
                      <strong>{item.name}</strong>
                      <small>{item.unit}</small>
                    </div>
                  </div>
                  <div className="warehouse-v1656__stock">
                    <span>Qoldiq</span>
                    <strong>
                      {quantity(item.stock_qty)} {item.unit}
                    </strong>
                  </div>
                  {item.low_stock && (
                    <p className="warehouse-v1656__warning">
                      ⚠ Kam qoldi · minimum {quantity(item.min_qty)} {item.unit}
                    </p>
                  )}
                  {canViewCosts && (
                    <dl>
                      <div>
                        <dt>Tannarx</dt>
                        <dd>{money(item.cost_price)}</dd>
                      </div>
                      <div>
                        <dt>Keyingi FIFO</dt>
                        <dd>{money(item.fifo_next_cost)}</dd>
                      </div>
                      <div>
                        <dt>Ombor qiymati</dt>
                        <dd>{money(item.fifo_value)}</dd>
                      </div>
                      <div>
                        <dt>Sotuv narxi</dt>
                        <dd>{item.price || "Kelishiladi"}</dd>
                      </div>
                    </dl>
                  )}
                  <div className="warehouse-v1656__actions">
                    {(canManage ||
                      (canProduce && item.stock_type === "ready_food")) && (
                      <button
                        type="button"
                        onClick={() => void onOpenMove(item, "receipt")}
                      >
                        + Kirim
                      </button>
                    )}
                    {canManage && (
                      <button
                        type="button"
                        onClick={() => void onOpenMove(item, "outflow")}
                      >
                        − Chiqim
                      </button>
                    )}
                    <button type="button" onClick={() => void onOpenHistory(item)}>
                      Tarix
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
    </>
  );
}
