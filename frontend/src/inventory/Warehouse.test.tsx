import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { WarehouseItem } from "../api/types";
import { Warehouse, type WarehouseApi } from "./Warehouse";

const ready: WarehouseItem = {
  id: 10,
  catalog_item_id: 110,
  name: "Palov",
  price: "35000",
  unit: "porsiya",
  stock_qty: 8,
  cost_price: 18000,
  fifo_next_cost: 17500,
  fifo_value: 144000,
  min_qty: 3,
  image_url: "",
  group_id: 1,
  group_name: "Taomlar",
  stock_type: "ready_food",
  low_stock: false,
};

const raw: WarehouseItem = {
  ...ready,
  id: 20,
  catalog_item_id: 120,
  name: "Guruch",
  price: "",
  unit: "kg",
  stock_qty: 2,
  cost_price: 16000,
  fifo_next_cost: 16000,
  fifo_value: 32000,
  min_qty: 3,
  group_id: null,
  group_name: "",
  stock_type: "raw_material",
  low_stock: true,
};

function warehouseApi(overrides: Partial<WarehouseApi> = {}): WarehouseApi {
  return {
    getWarehouseItems: vi.fn().mockResolvedValue({ items: [ready, raw] }),
    createWarehouseMove: vi.fn().mockResolvedValue({
      ok: true,
      move_id: 1,
      stock_qty: 10,
      unit_cost: 16000,
      total_cost: 32000,
    }),
    deleteWarehouseMove: vi.fn().mockResolvedValue(undefined),
    getWarehouseMoves: vi.fn().mockResolvedValue([]),
    getWarehouseRecipe: vi.fn().mockResolvedValue([]),
    getWarehouseProduction: vi.fn().mockResolvedValue([]),
    ...overrides,
  };
}

describe("v1656 Ombor", () => {
  it("Savdoda guruh, qoldiq, FIFO va kam qoldiqni kartalarda ko‘rsatadi", async () => {
    render(
      <Warehouse
        api={warehouseApi()}
        direction="Savdo"
        canManage
        canProduce
        canViewCosts
        onBack={vi.fn()}
      />,
    );

    expect(await screen.findByRole("heading", { name: "Taomlar" })).toBeInTheDocument();
    expect(screen.getByText("8 porsiya")).toBeInTheDocument();
    expect(screen.getAllByText("Keyingi FIFO")).toHaveLength(2);
    expect(screen.getByText(/Kam qoldi · minimum 3 kg/)).toBeInTheDocument();
  });

  it("tayyor taom kirimida retseptni miqdorga ko‘paytirib yuboradi", async () => {
    const user = userEvent.setup();
    const createWarehouseMove = vi.fn().mockResolvedValue({
      ok: true,
      move_id: 5,
      stock_qty: 10,
      unit_cost: 16000,
      total_cost: 32000,
    });
    const api = warehouseApi({
      createWarehouseMove,
      getWarehouseRecipe: vi.fn().mockResolvedValue([
        {
          item_id: raw.id,
          qty_per_unit: 0.5,
          name: raw.name,
          unit: raw.unit,
          cost_price: raw.cost_price,
          cost_per_ready_unit: 8000,
        },
      ]),
    });
    render(
      <Warehouse
        api={api}
        direction="Umumiy ovqatlanish"
        canManage
        canProduce
        canViewCosts
        onBack={vi.fn()}
      />,
    );

    await screen.findByText("Palov");
    await user.click(screen.getByRole("button", { name: "+ Kirim" }));
    expect(await screen.findByDisplayValue("0.5")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Miqdor"), "2");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));

    await waitFor(() =>
      expect(createWarehouseMove).toHaveBeenCalledWith({
        item_id: ready.id,
        delta: 2,
        reason: "kirim",
        note: "",
        cost: 0,
        ingredients: [{ item_id: raw.id, qty: 1 }],
        save_recipe: true,
      }),
    );
  });

  it("chiqimni qoldiqdan oshirishga ruxsat bermaydi", async () => {
    const user = userEvent.setup();
    const createWarehouseMove = vi.fn();
    render(
      <Warehouse
        api={warehouseApi({ createWarehouseMove })}
        direction="Savdo"
        canManage
        canProduce
        canViewCosts
        onBack={vi.fn()}
      />,
    );
    await screen.findByText("Guruch");
    const cards = screen.getAllByRole("article");
    const guruchCard = cards.find((card) => card.textContent?.includes("Guruch"));
    expect(guruchCard).toBeDefined();
    await user.click(guruchCard!.querySelectorAll("button")[1]!);
    await user.type(screen.getByLabelText("Miqdor"), "3");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("faqat 2 kg bor");
    expect(createWarehouseMove).not.toHaveBeenCalled();
  });
});
