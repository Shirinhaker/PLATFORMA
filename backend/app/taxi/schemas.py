from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


DriverService = Literal["taxi", "dostavka", "both"]
RideKind = Literal["taxi", "dostavka"]
RideStatus = Literal[
    "pending", "accepted", "arrived", "ongoing", "arrived_store",
    "pickup_requested", "in_delivery", "arrived_customer",
    "delivered_waiting_customer", "completed", "canceled",
]


class PricingBand(BaseModel):
    base: int
    per_km: int
    min: int


class PricingRead(BaseModel):
    pricing: dict[RideKind, PricingBand]
    commission: int


class DriverWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone: str = Field(min_length=1, max_length=80)
    car_model: str = Field(default="", max_length=120)
    car_color: str = Field(default="", max_length=80)
    car_plate: str = Field(default="", max_length=40)
    service: DriverService = "taxi"


class AvailabilityWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    available: bool


class DriverRead(BaseModel):
    exists: bool
    id: int | None = None
    name: str = ""
    phone: str = ""
    car_model: str = ""
    car_color: str = ""
    car_plate: str = ""
    service: DriverService = "taxi"
    available: bool = True
    busy: bool = False
    rating_sum: int = 0
    rating_count: int = 0
    balance: int = 0
    commission: int = 1000
    status: str = "active"


class RideCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: RideKind = "taxi"
    from_addr: str = Field(default="", max_length=500)
    to_addr: str = Field(default="", max_length=500)
    from_lat: float | None = Field(default=None, ge=-90, le=90)
    from_lng: float | None = Field(default=None, ge=-180, le=180)
    to_lat: float | None = Field(default=None, ge=-90, le=90)
    to_lng: float | None = Field(default=None, ge=-180, le=180)
    dist_km: float | None = Field(default=None, ge=0, le=10000)
    dur_min: int | None = Field(default=None, ge=0, le=100000)
    ozim: bool = False
    cargo: str = Field(default="", max_length=500)
    car_type: str = Field(default="", max_length=80)
    note: str = Field(default="", max_length=2000)
class RidePerson(BaseModel):
    name: str = ""
    phone: str = ""


class RideDriver(RidePerson):
    car_model: str = ""
    car_color: str = ""
    car_plate: str = ""


class RideRead(BaseModel):
    id: int
    kind: RideKind
    from_addr: str
    to_addr: str
    from_lat: float | None
    from_lng: float | None
    to_lat: float | None
    to_lng: float | None
    dist_km: float | None
    dur_min: int | None
    price: int | None
    meter_km: float | None
    final_price: int | None
    ozim: bool
    cargo: str
    car_type: str
    note: str
    status: RideStatus
    source_order_id: int | None
    created_at: datetime
    accepted_at: datetime | None
    driver: RideDriver | None = None
    customer: RidePerson | None = None
    customer_name: str = ""


class MyRidesRead(BaseModel):
    ride: RideRead | None
    rides: list[RideRead]


class DriverRidesRead(BaseModel):
    available: bool
    current: RideRead | None
    pending: list[RideRead]


class RideAccepted(BaseModel):
    ride: RideRead
    commission: int
    balance: int
    available: bool


class RideStatusWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: RideStatus


class RideProgressWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    km: float = Field(ge=0, le=100000)


class RideMutationRead(BaseModel):
    status: RideStatus
    available: bool


class AdminDriverRead(BaseModel):
    id: int
    name: str
    phone: str
    balance: int
    service: DriverService
    available: bool


class DriverTopupWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: int = Field(gt=0, le=10_000_000)
    reason: str = Field(min_length=3, max_length=2000)


class DriverTopupRead(BaseModel):
    id: int
    balance: int
