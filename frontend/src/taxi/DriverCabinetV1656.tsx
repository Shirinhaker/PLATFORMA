import { useCallback, useEffect, useRef, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  TaxiDriver,
  TaxiDriverRides,
  TaxiDriverService,
  TaxiPricing,
  TaxiRide,
  TaxiRideStatus,
} from "../api/types";
import "./taxi-v1656.css";

export type DriverCabinetApi = Partial<
  Pick<
    ApiClient,
    | "getTaxiDriver"
    | "getTaxiPricing"
    | "saveTaxiDriver"
    | "setTaxiDriverAvailable"
    | "getPendingTaxiRides"
    | "acceptTaxiRide"
    | "setTaxiRideStatus"
    | "updateTaxiRideProgress"
  >
>;

type Props = { api: DriverCabinetApi; onBack?: () => void };

const EMPTY_ORDERS: TaxiDriverRides = { available: false, current: null, pending: [] };
const DEFAULT_PRICING: TaxiPricing = {
  pricing: {
    taxi: { base: 5000, per_km: 2000, min: 9000 },
    dostavka: { base: 10000, per_km: 2500, min: 15000 },
  },
  commission: 1000,
};

function errorText(reason: unknown) {
  return reason instanceof Error ? reason.message : "So'rov bajarilmadi.";
}

function money(value: number) {
  return value.toLocaleString("uz-UZ").replace(/,/g, " ");
}

function metersBetween(lat1: number, lng1: number, lat2: number, lng2: number) {
  const radians = Math.PI / 180;
  const dLat = (lat2 - lat1) * radians;
  const dLng = (lng2 - lng1) * radians;
  const value =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * radians) * Math.cos(lat2 * radians) * Math.sin(dLng / 2) ** 2;
  return 6_371_000 * 2 * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value));
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

export function DriverCabinetV1656({ api, onBack }: Props) {
  const [driver, setDriver] = useState<TaxiDriver | null>(null);
  const [orders, setOrders] = useState(EMPTY_ORDERS);
  const [editing, setEditing] = useState(false);
  const [phone, setPhone] = useState("");
  const [service, setService] = useState<TaxiDriverService>("taxi");
  const [model, setModel] = useState("");
  const [plate, setPlate] = useState("");
  const [color, setColor] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [meterKm, setMeterKm] = useState(0);
  const [pricing, setPricing] = useState(DEFAULT_PRICING);

  const applyDriver = useCallback((value: TaxiDriver) => {
    setDriver(value);
    setPhone(value.phone);
    setService(value.service);
    setModel(value.car_model);
    setPlate(value.car_plate);
    setColor(value.car_color);
    setEditing(!value.exists);
  }, []);

  const loadOrders = useCallback(async () => {
    if (!api.getPendingTaxiRides) return;
    try {
      setOrders(await api.getPendingTaxiRides());
    } catch (reason) {
      setError(errorText(reason));
    }
  }, [api]);

  const load = useCallback(async () => {
    if (!api.getTaxiDriver) {
      setError("Taxi xizmati hozircha ulanmagan.");
      return;
    }
    setError("");
    try {
      const [value, rates] = await Promise.all([
        api.getTaxiDriver(),
        api.getTaxiPricing?.().catch(() => undefined),
      ]);
      if (rates) setPricing(rates);
      applyDriver(value);
      if (value.exists) await loadOrders();
    } catch (reason) {
      setError(errorText(reason));
    }
  }, [api, applyDriver, loadOrders]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!driver?.exists || editing) return undefined;
    const timer = window.setInterval(() => {
      void loadOrders();
    }, 4000);
    return () => window.clearInterval(timer);
  }, [driver?.exists, editing, loadOrders]);

  useEffect(() => {
    const ride = orders.current;
    if (!ride || ride.status !== "ongoing" || !ride.ozim || !navigator.geolocation) {
      setMeterKm(0);
      return undefined;
    }
    let total = ride.meter_km ?? 0;
    let last: [number, number] | null = null;
    let lastSent = 0;
    setMeterKm(total);
    const watch = navigator.geolocation.watchPosition(
      (position) => {
        if ((position.coords.accuracy || 999) > 50) return;
        const point: [number, number] = [
          position.coords.latitude,
          position.coords.longitude,
        ];
        if (!last) {
          last = point;
          return;
        }
        const distance = metersBetween(last[0], last[1], point[0], point[1]);
        if (distance < 10) return;
        if (distance > 1000) {
          last = point;
          return;
        }
        total += distance / 1000;
        last = point;
        setMeterKm(total);
        const now = Date.now();
        if (now - lastSent > 10_000) {
          lastSent = now;
          void api.updateTaxiRideProgress?.(ride.id, total).catch(() => undefined);
        }
      },
      () => undefined,
      {
        enableHighAccuracy: true,
        maximumAge: 2000,
        timeout: 15000,
      },
    );
    return () => navigator.geolocation.clearWatch(watch);
  }, [api, orders.current?.id, orders.current?.ozim, orders.current?.status]);

  async function save() {
    if (!phone.trim()) {
      setError("Telefon raqamini kiriting.");
      return;
    }
    if (
      ["taxi", "both"].includes(service) &&
      ![model, plate, color].every((value) => value.trim())
    ) {
      setError("Taxi uchun mashina rusumi, raqami va rangini to'ldiring.");
      return;
    }
    if (!api.saveTaxiDriver) return;
    setBusy(true);
    setError("");
    try {
      const value = await api.saveTaxiDriver({
        phone: phone.trim(),
        service,
        car_model: model.trim(),
        car_plate: plate.trim(),
        car_color: color.trim(),
      });
      applyDriver(value);
      setEditing(false);
      setMessage("Saqlandi.");
      await loadOrders();
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function availability(available: boolean) {
    if (!api.setTaxiDriverAvailable) return;
    try {
      const value = await api.setTaxiDriverAvailable(available);
      applyDriver(value);
      setEditing(false);
      setMessage(available ? "Holatingiz: Bo'shman" : "Holatingiz: Bandman");
      await loadOrders();
    } catch (reason) {
      setError(errorText(reason));
    }
  }

  async function accept(rideId: number) {
    if (!api.acceptTaxiRide) return;
    try {
      const value = await api.acceptTaxiRide(rideId);
      setDriver((current) =>
        current
          ? {
              ...current,
              balance: value.balance,
              available: false,
              busy: true,
            }
          : current,
      );
      setMessage(
        `Zakaz qabul qilindi! Komissiya: ${money(value.commission)} so'm yechildi.`,
      );
      await loadOrders();
    } catch (reason) {
      setError(errorText(reason));
      await loadOrders();
    }
  }

  async function advance(ride: TaxiRide, status: TaxiRideStatus) {
    if (!api.setTaxiRideStatus) return;
    try {
      if (
        status === "completed" &&
        ride.status === "ongoing" &&
        ride.ozim &&
        api.updateTaxiRideProgress
      ) {
        await api.updateTaxiRideProgress(ride.id, meterKm).catch(() => undefined);
      }
      await api.setTaxiRideStatus(ride.id, status);
      if (status === "completed") {
        setMessage("Safar yakunlandi. Endi yana zakaz olishingiz mumkin.");
        await load();
      } else {
        await loadOrders();
      }
    } catch (reason) {
      setError(errorText(reason));
    }
  }

  if (!driver) {
    return (
      <main className="profile-shell">
        <p>{error || "Yuklanmoqda..."}</p>
      </main>
    );
  }

  if (editing) {
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
          onClick={() => void save()}
        >
          {driver.exists ? "Saqlash" : "Ro'yxatdan o'tish"}
        </button>
      </main>
    );
  }

  const available = driver.available && !driver.busy;
  const serviceLabel =
    driver.service === "both"
      ? "🚖 Taxi · 📦 Dostavka"
      : driver.service === "dostavka"
        ? "📦 Dostavka"
        : "🚖 Taxi";
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
      <div className="cab-head">
        <div className="cab-logo">🚖</div>
        <div>
          <div className="cab-name">{driver.name}</div>
          <div className="cab-status">
            {driver.car_model
              ? `${driver.car_model}, ${driver.car_color} · ${driver.car_plate} · `
              : ""}
            {serviceLabel}
          </div>
        </div>
      </div>
      <div
        className={`panel-card taxi-driver-v1656__balance${driver.balance < driver.commission ? " low" : ""}`}
      >
        <div>
          <small>💳 Balansingiz</small>
          <strong>{money(driver.balance)} so'm</strong>
        </div>
        <button
          className="sort-chip"
          type="button"
          onClick={() =>
            setMessage(
              "Balansni to'ldirish: firma hisobiga pul o'tkazing, admin tasdiqlagach balans qo'shiladi. Avtomatik to'lov tez orada ulanadi.",
            )
          }
        >
          ➕ To'ldirish
        </button>
        <p>Har qabul qilingan zakaz uchun {money(driver.commission)} so'm yechiladi.</p>
        {driver.balance < driver.commission ? (
          <p className="taxi-v1656__error">
            ⚠️ Balans yetarli emas — zakaz olish uchun to'ldiring.
          </p>
        ) : null}
      </div>
      <div className="field">
        <label>Holatim</label>
        <button
          disabled={driver.busy}
          className={`vis-card${available ? " on" : ""}`}
          type="button"
          onClick={() => void availability(true)}
        >
          <span className="v-ic">🟢</span>
          <div>
            <h5>Bo'shman</h5>
            <p>
              {driver.busy
                ? "Joriy zakaz yakunlangach avtomatik yoqiladi."
                : "Yangi zakazlar menga ko'rinadi."}
            </p>
          </div>
        </button>
        <button
          disabled={driver.busy}
          className={`vis-card${!available ? " on" : ""}`}
          type="button"
          onClick={() => void availability(false)}
        >
          <span className="v-ic">🔴</span>
          <div>
            <h5>Bandman</h5>
            <p>
              {driver.busy
                ? "Zakaz qabul qilingani uchun avtomatik band."
                : "Zakazlar kelmaydi."}
            </p>
          </div>
        </button>
      </div>
      <button
        className="btn btn-soft btn-block"
        type="button"
        onClick={() => setEditing(true)}
      >
        ✎ Ma'lumotlarni tahrirlash
      </button>
      {message ? (
        <p role="status" className="elon-hint">
          {message}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="elon-hint taxi-v1656__error">
          {error}
        </p>
      ) : null}
      <div className="taxi-driver-v1656__orders-head">
        <h2>Kelayotgan zakazlar</h2>
        <button className="sort-chip" type="button" onClick={() => void loadOrders()}>
          ↻ Yangilash
        </button>
      </div>
      <DriverOrders
        meterKm={meterKm}
        meterPrice={(() => {
          const kind = orders.current?.kind ?? "taxi";
          const band = pricing.pricing[kind];
          if (!meterKm) return 0;
          return (
            Math.round(Math.max(band.min, band.base + band.per_km * meterKm) / 500) *
            500
          );
        })()}
        orders={orders}
        onAccept={accept}
        onAdvance={advance}
      />
    </main>
  );
}

function DriverOrders({
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
