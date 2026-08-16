// `api/types.ts` dan ajratildi — domen bo'yicha.

export type WarehouseStockType = "ready_food" | "raw_material";

export type WarehouseItem = {
  id: number;
  catalog_item_id: number;
  name: string;
  price: string;
  unit: string;
  stock_qty: number;
  cost_price: number;
  fifo_next_cost: number;
  fifo_value: number;
  min_qty: number;
  image_url: string;
  group_id: number | null;
  group_name: string;
  stock_type: WarehouseStockType;
  low_stock: boolean;
};

export type WarehouseList = { items: WarehouseItem[] };

export type WarehouseIngredientWrite = {
  item_id: number;
  qty: number;
};

export type WarehouseMoveCreate = {
  item_id: number;
  delta: number;
  reason?: "" | "kirim" | "chiqim" | "sotuv" | "tuzatish";
  note: string;
  cost?: number;
  ingredients?: WarehouseIngredientWrite[];
  save_recipe?: boolean;
};

export type WarehouseMoveResult = {
  ok: true;
  move_id: number;
  stock_qty: number;
  unit_cost: number;
  total_cost: number;
};

export type WarehouseMove = {
  id: number;
  delta: number;
  reason: string;
  reason_text: string;
  note: string;
  who: string;
  cost: number;
  can_delete: boolean;
  order_id: number | null;
  created_at: number;
  unit: string;
};

export type WarehouseRecipeIngredient = {
  item_id: number;
  qty_per_unit: number;
  name: string;
  unit: string;
  cost_price: number;
  cost_per_ready_unit: number;
};

export type WarehouseProductionInput = {
  item_id: number;
  qty: number;
  unit_cost: number;
  total_cost: number;
  name: string;
  unit: string;
};

export type WarehouseProductionBatch = {
  id: number;
  ready_item_id: number;
  ready_name: string;
  ready_unit: string;
  qty: number;
  total_cost: number;
  unit_cost: number;
  note: string;
  who: string;
  created_at: number;
  inputs: WarehouseProductionInput[];
};
