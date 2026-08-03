from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IngredientWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: int = Field(gt=0)
    qty: float = Field(gt=0, le=100_000)


class StockMoveCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: int = Field(gt=0)
    delta: float = Field(ge=-100_000, le=100_000)
    reason: Literal["", "kirim", "chiqim", "sotuv", "tuzatish"] = ""
    note: str = Field(default="", max_length=200)
    cost: int = Field(default=0, ge=0, le=10**12)
    ingredients: list[IngredientWrite] = Field(default_factory=list, max_length=100)
    save_recipe: bool = False

    @field_validator("note", mode="before")
    @classmethod
    def clean_note(cls, value):
        return value.strip() if isinstance(value, str) else value


class InventoryItemWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    track_stock: bool = True
    stock_type: Literal["ready_food", "raw_material"] = "ready_food"
    min_qty: float = Field(default=0, ge=0, le=100_000)


class InventoryItemRead(BaseModel):
    id: int
    catalog_item_id: int
    name: str
    price: str = ""
    unit: str = "dona"
    stock_qty: float
    cost_price: int
    fifo_next_cost: int
    fifo_value: int
    min_qty: float
    image_url: str = ""
    group_id: int | None = None
    group_name: str = ""
    stock_type: Literal["ready_food", "raw_material"]
    low_stock: bool


class InventoryListRead(BaseModel):
    items: list[InventoryItemRead]


class StockMoveResult(BaseModel):
    ok: bool = True
    move_id: int
    stock_qty: float
    unit_cost: int
    total_cost: int


class StockMoveRead(BaseModel):
    id: int
    delta: float
    reason: str
    reason_text: str
    note: str
    who: str
    cost: int
    can_delete: bool
    order_id: int | None = None
    created_at: int
    unit: str


class RecipeIngredientRead(BaseModel):
    item_id: int
    qty_per_unit: float
    name: str
    unit: str
    cost_price: int
    cost_per_ready_unit: int


class ProductionInputRead(BaseModel):
    item_id: int
    qty: float
    unit_cost: int
    total_cost: int
    name: str
    unit: str


class ProductionBatchRead(BaseModel):
    id: int
    ready_item_id: int
    ready_name: str
    ready_unit: str
    qty: float
    total_cost: int
    unit_cost: int
    note: str
    who: str
    created_at: int
    inputs: list[ProductionInputRead]
