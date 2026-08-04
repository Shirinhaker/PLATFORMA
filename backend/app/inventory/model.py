from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    __table_args__ = (
        CheckConstraint(
            "stock_type IN ('ready_food', 'raw_material')",
            name="ck_inventory_items_stock_type",
        ),
        CheckConstraint("cost_price >= 0", name="ck_inventory_items_cost_price"),
        CheckConstraint("min_qty >= 0", name="ck_inventory_items_min_qty"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    catalog_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("catalog_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    track_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    stock_type: Mapped[str] = mapped_column(
        String(24), nullable=False, default="ready_food"
    )
    stock_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, default=0
    )
    cost_price: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    min_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, default=0
    )
    fifo_initialized: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class StockMove(Base):
    __tablename__ = "inventory_stock_moves"
    __table_args__ = (
        CheckConstraint("delta <> 0", name="ck_inventory_stock_moves_delta"),
        CheckConstraint("cost >= 0", name="ck_inventory_stock_moves_cost"),
        CheckConstraint(
            "reason IN ('kirim', 'chiqim', 'sotuv', 'tuzatish')",
            name="ck_inventory_stock_moves_reason",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    inventory_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("inventory_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    delta: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    reason: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    cost: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    legacy_order_source_id: Mapped[int | None] = mapped_column(BigInteger)
    cash_sale_line_id: Mapped[int | None] = mapped_column(
        BigInteger,
    )
    performed_by_staff_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("staff_members.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class StockBatch(Base):
    __tablename__ = "inventory_stock_batches"
    __table_args__ = (
        CheckConstraint("qty_in > 0", name="ck_inventory_stock_batches_qty_in"),
        CheckConstraint(
            "qty_remaining >= 0 AND qty_remaining <= qty_in",
            name="ck_inventory_stock_batches_remaining",
        ),
        CheckConstraint(
            "unit_cost >= 0", name="ck_inventory_stock_batches_unit_cost"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    inventory_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("inventory_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    qty_in: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    qty_remaining: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit_cost: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    source_move_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("inventory_stock_moves.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class StockBatchConsumption(Base):
    __tablename__ = "inventory_batch_consumptions"
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_inventory_consumptions_qty"),
        CheckConstraint("unit_cost >= 0", name="ck_inventory_consumptions_unit_cost"),
        CheckConstraint("total_cost >= 0", name="ck_inventory_consumptions_total_cost"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("inventory_stock_batches.id", ondelete="RESTRICT"),
        nullable=False,
    )
    inventory_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("inventory_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit_cost: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_cost: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    source_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class RecipeIngredient(Base):
    __tablename__ = "inventory_recipe_ingredients"
    __table_args__ = (
        CheckConstraint("qty_per_unit > 0", name="ck_inventory_recipes_qty"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    ready_inventory_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    ingredient_inventory_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("inventory_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    qty_per_unit: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ProductionBatch(Base):
    __tablename__ = "inventory_production_batches"
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_inventory_production_qty"),
        CheckConstraint("total_cost >= 0", name="ck_inventory_production_total_cost"),
        CheckConstraint("unit_cost >= 0", name="ck_inventory_production_unit_cost"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    ready_inventory_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("inventory_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    total_cost: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    unit_cost: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    note: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    performed_by_staff_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("staff_members.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ProductionInput(Base):
    __tablename__ = "inventory_production_inputs"
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_inventory_production_inputs_qty"),
        CheckConstraint("unit_cost >= 0", name="ck_inventory_production_inputs_unit_cost"),
        CheckConstraint("total_cost >= 0", name="ck_inventory_production_inputs_total_cost"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    production_batch_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("inventory_production_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    inventory_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("inventory_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit_cost: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_cost: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


Index("uq_inventory_items_catalog", InventoryItem.catalog_item_id, unique=True)
Index(
    "uq_inventory_items_business_legacy",
    InventoryItem.business_account_id,
    InventoryItem.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "ix_inventory_items_business_tracked",
    InventoryItem.business_account_id,
    InventoryItem.track_stock,
    InventoryItem.stock_type,
)
Index(
    "ix_inventory_items_business_stock_qty",
    InventoryItem.business_account_id,
    InventoryItem.stock_qty,
    InventoryItem.id,
    postgresql_where=text("track_stock IS true"),
    sqlite_where=text("track_stock = 1"),
)
Index(
    "uq_inventory_stock_moves_business_legacy",
    StockMove.business_account_id,
    StockMove.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "ix_inventory_stock_moves_item_created",
    StockMove.business_account_id,
    StockMove.inventory_item_id,
    StockMove.created_at,
    StockMove.id,
)
Index("ix_inventory_stock_moves_cash_line", StockMove.cash_sale_line_id)
Index(
    "uq_inventory_stock_batches_business_legacy",
    StockBatch.business_account_id,
    StockBatch.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "ix_inventory_stock_batches_fifo",
    StockBatch.business_account_id,
    StockBatch.inventory_item_id,
    StockBatch.created_at,
    StockBatch.id,
)
Index(
    "uq_inventory_consumptions_batch_legacy",
    StockBatchConsumption.batch_id,
    StockBatchConsumption.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "ix_inventory_consumptions_source",
    StockBatchConsumption.source_type,
    StockBatchConsumption.source_id,
    StockBatchConsumption.id,
)
Index(
    "uq_inventory_recipes_items",
    RecipeIngredient.business_account_id,
    RecipeIngredient.ready_inventory_item_id,
    RecipeIngredient.ingredient_inventory_item_id,
    unique=True,
)
Index(
    "uq_inventory_recipes_business_legacy",
    RecipeIngredient.business_account_id,
    RecipeIngredient.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "uq_inventory_production_business_legacy",
    ProductionBatch.business_account_id,
    ProductionBatch.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "ix_inventory_production_business_created",
    ProductionBatch.business_account_id,
    ProductionBatch.created_at,
    ProductionBatch.id,
)
Index(
    "uq_inventory_production_inputs_legacy",
    ProductionInput.production_batch_id,
    ProductionInput.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
