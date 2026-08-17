import { useEffect, useRef } from "react";

import type {
  TaxiDriver,
  TaxiDriverRides,
  TaxiDriverService,
  TaxiRide,
  TaxiRideStatus,
} from "../api/types";

export function money(value: number) {
  return value.toLocaleString("uz-UZ").replace(/,/g, " ");
}

function actionFor(ride: TaxiRide): { label: string; status: TaxiRideStatus } | null {
  if (ride.kind === "dostavka") {
    if (ride.status === "accepted")
      return { label: "📍 Sotuvchiga yetib keldim", status: "arrived_store" };
    if (ride.status === "arrived_store")
      return { label: "📦 Dostavkani oldim", status: "pickup_requested" };
    if (ride.status === "in_delivery")
      return { label: "📍 Buyurtmachiga yetib keldim", status: "arrived_customer" };
    if (ride.status === "arrived_customer")
      return {
        label: "✅ Buyurtmani topshirdim",
        status: "delivered_waiting_customer",
      };
    return null;
  }
  if (ride.status === "accepted")
    return { label: "🚗 Yetib keldim", status: "arrived" };
  if (ride.status === "arrived")
    return { label: "▶️ Safarni boshlash", status: "ongoing" };
  if (ride.status === "ongoing") return { label: "✓ Yakunlash", status: "completed" };
  return null;
}

export function DriverProfileForm({
  driver,
  onBack,
  phone,
  setPhone,
  service,
  setService,
  model,
  setModel,
  plate,
  setPlate,
  color,
  setColor,
  error,
  busy,
  onSave,
}: {
  driver: TaxiDriver;
  onBack?: () => void;
  phone: string;
  setPhone(value: string): void;
  service: TaxiDriverService;
  setService(value: TaxiDriverService): void;
  model: string;
  setModel(value: string): void;
  plate: string;
  setPlate(value: string): void;
  color: string;
  setColor(value: string): void;
  error: string;
  busy: boolean;
  onSave(): Promise<void>;
}) {
  const carRequired = ["taxi", "both"].includes(service);
  return (
    <main className="screen active taxi-driver-v1656" data-screen="taxidrv">
      {onBack ? (
        <header className="profile-heading">
          <h1>Haydovchi kabineti</h1>
          <button className="button-secondary" type="button" onClick={onBack}>
            Kabinetga qaytish
          </button>
        </header>
      ) : null}
      <div className="biz-desc taxi-driver-v1656__intro">
        Ma'lumotlaringizni to'ldiring. Tasdiqlangach, yaqin zakazlar sizga ko'rinadi.
        To'lov mijoz bilan naqd.
      </div>
      <div className="taxi-driver-v1656__account">
        <div className="cab-logo">👤</div>
        <div>
          <b>{driver.name}</b>
          <div className="list-sub">Akkaunt ismingiz — shu ishlatiladi</div>
        </div>
      </div>
      <div className="field">
        <label htmlFor="driver-phone">Telefon</label>
        <input
          id="driver-phone"
          className="input"
          value={phone}
          onChange={(event) => setPhone(event.currentTarget.value)}
          placeholder="+998 ..."
        />
      </div>
      <div className="field">
        <label>Nima bilan ishlaysiz</label>
        <div className="sort-row taxi-driver-v1656__service-row">
          <button
            className={`sort-chip${service === "taxi" ? " on" : ""}`}
            type="button"
            onClick={() => setService("taxi")}
          >
            🚖 Taxi
          </button>
          <button
            className={`sort-chip${service === "dostavka" ? " on" : ""}`}
            type="button"
            onClick={() => setService("dostavka")}
          >
            📦 Dostavka
          </button>
          <button
            className={`sort-chip${service === "both" ? " on" : ""}`}
            type="button"
            onClick={() => setService("both")}
          >
            Ikkalasi
          </button>
        </div>
      </div>
      <div className="field">
        <label htmlFor="driver-model">
          Mashina rusumi {carRequired ? <span className="dreq">*</span> : null}
        </label>
        <input
          id="driver-model"
          className="input"
          value={model}
          onChange={(event) => setModel(event.currentTarget.value)}
          placeholder="Masalan: Cobalt"
        />
      </div>
      <div className="field">
        <label htmlFor="driver-plate">
          Davlat raqami {carRequired ? <span className="dreq">*</span> : null}
        </label>
        <input
          id="driver-plate"
          className="input"
          value={plate}
          onChange={(event) => setPlate(event.currentTarget.value)}
          placeholder="01 A 123 BC"
        />
      </div>
      <div className="field">
        <label htmlFor="driver-color">
          Rangi {carRequired ? <span className="dreq">*</span> : null}
        </label>
        <input
          id="driver-color"
          className="input"
          value={color}
          onChange={(event) => setColor(event.currentTarget.value)}
          placeholder="Masalan: oq"
        />
      </div>
      <div className="elon-hint taxi-driver-v1656__car-note">
        {carRequired
          ? "Taxi uchun mashina rusumi, raqami va rangi majburiy."
          : "Faqat dostavka — mashina ma'lumoti ixtiyoriy."}
      </div>
      {error ? (
        <p role="alert" className="elon-hint taxi-v1656__error">
          {error}
        </p>
      ) : null}
      <button
        disabled={busy}
        className="btn btn-primary btn-block"
        type="button"
        onClick={() => void onSave()}
      >
        {driver.exists ? "Saqlash" : "Ro'yxatdan o'tish"}
      </button>
    </main>
  );
}

export function DriverOrders({
  orders,
  meterKm,
  meterPrice,
  onAccept,
  onAdvance,
}: {
  orders: TaxiDriverRides;
  meterKm: number;
  meterPrice: number;
  onAccept(id: number): Promise<void>;
  onAdvance(ride: TaxiRide, status: TaxiRideStatus): Promise<void>;
}) {
  if (orders.current) {
    const ride = orders.current;
    const action = actionFor(ride);
    const navigation =
      ride.to_lat != null && ride.to_lng != null && !ride.ozim
        ? `https://www.google.com/maps/dir/?api=1&travelmode=driving&origin=${ride.from_lat},${ride.from_lng}&destination=${ride.to_lat},${ride.to_lng}`
        : `https://www.google.com/maps/dir/?api=1&travelmode=driving&destination=${ride.from_lat},${ride.from_lng}`;
    return (
      <div className="panel-card taxi-driver-v1656__current">
        <RideLines ride={ride} />
        {ride.status === "ongoing" && ride.ozim ? (
          <div className="taxi-driver-v1656__meter">
            📟 Bosib o'tilgan: <b>{meterKm.toFixed(1)} km</b> · ~{money(meterPrice)}{" "}
            so'm
          </div>
        ) : null}
        <div className="list-sub">Mijoz: {ride.customer?.name || "—"}</div>
        <div className="taxi-call-v1656__actions">
          {ride.customer?.phone ? (
            <a className="btn btn-soft" href={`tel:${ride.customer.phone}`}>
              📞
            </a>
          ) : null}
          {action ? (
            <button
              className="btn btn-primary"
              type="button"
              onClick={() => void onAdvance(ride, action.status)}
            >
              {action.label}
            </button>
          ) : null}
        </div>
        {ride.from_lat != null ? (
          <>
            <DriverRideMap ride={ride} />
            <a
              className="btn btn-soft btn-block"
              href={navigation}
              target="_blank"
              rel="noreferrer"
            >
              🧭 Yo'lni ochish (Google Maps)
            </a>
          </>
        ) : null}
      </div>
    );
  }
  if (!orders.available)
    return (
      <div className="empty">
        <h3>Siz «Bandman»siz</h3>
        <p>Zakaz olish uchun yuqorida «Bo'shman»ni tanlang.</p>
      </div>
    );
  if (!orders.pending.length)
    return (
      <div className="empty">
        <h3>Hozircha zakaz yo'q</h3>
        <p>Yangi zakaz chiqsa, shu yerda darhol ko'rinadi.</p>
      </div>
    );
  return (
    <>
      {orders.pending.map((ride) => (
        <div className="panel-card" key={ride.id}>
          <b>{ride.kind === "dostavka" ? "📦 Dostavka" : "🚖 Taxi"}</b>
          <RideLines ride={ride} />
          <div className="list-sub">Mijoz: {ride.customer_name || "—"}</div>
          <button
            className="btn btn-primary btn-block"
            type="button"
            onClick={() => void onAccept(ride.id)}
          >
            Qabul qilish
          </button>
        </div>
      ))}
    </>
  );
}

function RideLines({ ride }: { ride: TaxiRide }) {
  return (
    <div className="taxi-driver-v1656__ride-lines">
      <div className="list-sub">🟢 {ride.from_addr || "Boshlanish"}</div>
      <div className="list-sub">
        {ride.ozim ? "🗣 Manzilni og'zaki aytadi" : `🔴 ${ride.to_addr || "Manzil"}`}
      </div>
      {ride.dist_km ? (
        <div className="list-sub">
          ~{ride.dist_km.toFixed(1)} km{ride.dur_min ? ` · ~${ride.dur_min} daq` : ""}
        </div>
      ) : null}
      {ride.price ? (
        <div className="list-sub taxi-call-v1656__price">
          💰 ~{money(ride.price)} so'm (naqd)
        </div>
      ) : ride.ozim ? (
        <div className="list-sub">Narx masofa bo'yicha</div>
      ) : null}
    </div>
  );
}

function DriverRideMap({ ride }: { ride: TaxiRide }) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!host.current || ride.from_lat == null || ride.from_lng == null)
      return undefined;
    let disposed = false;
    const controller = new AbortController();
    let instance: import("leaflet").Map | null = null;
    void import("leaflet")
      .then(async (module) => {
        if (disposed || !host.current) return;
        const L = module.default;
        instance = L.map(host.current, {
          attributionControl: false,
          zoomControl: true,
        }).setView([ride.from_lat!, ride.from_lng!], 15);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
        }).addTo(instance);
        L.marker([ride.from_lat!, ride.from_lng!], {
          icon: L.divIcon({ className: "taxi-route-pin", html: "<span>🟢</span>" }),
        }).addTo(instance);
        if (!ride.ozim && ride.to_lat != null && ride.to_lng != null) {
          L.marker([ride.to_lat, ride.to_lng], {
            icon: L.divIcon({ className: "taxi-route-pin", html: "<span>🔴</span>" }),
          }).addTo(instance);
          instance.fitBounds(
            [
              [ride.from_lat!, ride.from_lng!],
              [ride.to_lat, ride.to_lng],
            ],
            { padding: [45, 45] },
          );
          const url =
            "https://router.project-osrm.org/route/v1/driving/" +
            `${ride.from_lng},${ride.from_lat};${ride.to_lng},${ride.to_lat}` +
            "?overview=full&geometries=geojson";
          const payload = (await fetch(url, { signal: controller.signal })
            .then((response) => response.json())
            .catch(() => null)) as {
            routes?: Array<{ geometry: GeoJSON.GeoJsonObject }>;
          } | null;
          if (!disposed && instance && payload?.routes?.[0]) {
            L.geoJSON(payload.routes[0].geometry, {
              style: { color: "#2563EB", weight: 5, opacity: 0.85 },
            }).addTo(instance);
          }
        }
        window.setTimeout(() => instance?.invalidateSize(), 150);
      })
      .catch(() => undefined);
    return () => {
      disposed = true;
      controller.abort();
      instance?.remove();
    };
  }, [ride.from_lat, ride.from_lng, ride.id, ride.ozim, ride.to_lat, ride.to_lng]);
  return <div className="taxi-driver-v1656__map" ref={host} />;
}
