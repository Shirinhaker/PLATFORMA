// `api/types.ts` dan ajratildi — domen bo'yicha.

export type TaxiKind = "taxi" | "dostavka";

export type TaxiDriverService = TaxiKind | "both";

export type TaxiRideStatus =
  | "pending"
  | "accepted"
  | "arrived"
  | "ongoing"
  | "arrived_store"
  | "pickup_requested"
  | "in_delivery"
  | "arrived_customer"
  | "delivered_waiting_customer"
  | "completed"
  | "canceled";

export type TaxiPricing = {
  pricing: Record<TaxiKind, { base: number; per_km: number; min: number }>;
  commission: number;
};

export type TaxiDriverWrite = {
  phone: string;
  car_model: string;
  car_color: string;
  car_plate: string;
  service: TaxiDriverService;
};

export type TaxiDriver = TaxiDriverWrite & {
  exists: boolean;
  id: number | null;
  name: string;
  available: boolean;
  busy: boolean;
  rating_sum: number;
  rating_count: number;
  balance: number;
  commission: number;
  status: string;
};

export type TaxiRideCreate = {
  kind: TaxiKind;
  from_addr: string;
  to_addr: string;
  from_lat: number | null;
  from_lng: number | null;
  to_lat: number | null;
  to_lng: number | null;
  dist_km: number | null;
  dur_min: number | null;
  ozim: boolean;
  cargo: string;
  car_type: string;
  note: string;
};

export type TaxiRidePerson = { name: string; phone: string };

export type TaxiRideDriver = TaxiRidePerson & {
  car_model: string;
  car_color: string;
  car_plate: string;
};

export type TaxiRide = TaxiRideCreate & {
  id: number;
  price: number | null;
  meter_km: number | null;
  final_price: number | null;
  status: TaxiRideStatus;
  source_order_id: number | null;
  created_at: string;
  accepted_at: string | null;
  driver: TaxiRideDriver | null;
  customer: TaxiRidePerson | null;
  customer_name: string;
};

export type TaxiMyRides = { ride: TaxiRide | null; rides: TaxiRide[] };

export type TaxiDriverRides = {
  available: boolean;
  current: TaxiRide | null;
  pending: TaxiRide[];
};

export type TaxiRideAccepted = {
  ride: TaxiRide;
  commission: number;
  balance: number;
  available: boolean;
};

export type TaxiRideMutation = {
  status: TaxiRideStatus;
  available: boolean;
};
