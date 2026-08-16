import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { ApiClient } from "../api/client";
import type { TaxiKind, TaxiPricing, TaxiRide, TaxiRideCreate } from "../api/types";
import "./taxi.css";

export type TaxiApi = Partial<
  Pick<
    ApiClient,
    | "getTaxiPricing"
    | "createTaxiRide"
    | "getMyTaxiRides"
    | "cancelTaxiRide"
    | "reverseGeocode"
  >
>;

type Props = {
  api: TaxiApi;
  authenticated: boolean;
  center: { latitude: number; longitude: number };
  district?: string;
  onBack(): void;
  onNeedLogin(reason: string): void;
};

type Point = { latitude: number; longitude: number };
type Phase = "form" | "search" | "found";

const DEFAULT_PRICING: TaxiPricing = {
  pricing: {
    taxi: { base: 5000, per_km: 2000, min: 9000 },
    dostavka: { base: 10000, per_km: 2500, min: 15000 },
  },
  commission: 1000,
};

function money(value: number) {
  return Math.round(value).toLocaleString("uz-UZ").replace(/,/g, " ");
}

function price(kind: TaxiKind, km: number | null, pricing: TaxiPricing) {
  if (!km || km <= 0) return null;
  const band = pricing.pricing[kind];
  return Math.round(Math.max(band.min, band.base + band.per_km * km) / 500) * 500;
}

function distanceKm(from: Point, to: Point) {
  const radians = Math.PI / 180;
  const dLat = (to.latitude - from.latitude) * radians;
  const dLng = (to.longitude - from.longitude) * radians;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(from.latitude * radians) *
      Math.cos(to.latitude * radians) *
      Math.sin(dLng / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function statusLabel(ride: TaxiRide) {
  if (ride.kind === "dostavka") {
    if (
      [
        "arrived",
        "ongoing",
        "in_delivery",
        "arrived_customer",
        "delivered_waiting_customer",
      ].includes(ride.status)
    ) {
      return "📦 Dostavka olindi — yetkazilmoqda";
    }
    return "🚚 Dostavkachi buyurtmani olish uchun yo'lda";
  }
  if (ride.status === "arrived") return "📍 Haydovchi yetib keldi!";
  if (ride.status === "ongoing") return "🛣️ Safardasiz";
  return "🚗 Haydovchi yo'lda kelmoqda";
}

export function TaxiCall({
  api,
  authenticated,
  center,
  district = "",
  onBack,
  onNeedLogin,
}: Props) {
  const [kind, setKind] = useState<TaxiKind>("taxi");
  const [phase, setPhase] = useState<Phase>("form");
  const [pickMode, setPickMode] = useState<"from" | "to">("to");
  const [from, setFrom] = useState<Point>(center);
  const [to, setTo] = useState<Point | null>(null);
  const [fromAddr, setFromAddr] = useState("📍 Xaritadagi joy");
  const [toAddr, setToAddr] = useState("");
  const [ozim, setOzim] = useState(false);
  const [carType, setCarType] = useState("Yengil yuk");
  const [cargo, setCargo] = useState("");
  const [routeDistance, setRouteDistance] = useState<number | null>(null);
  const [routeDuration, setRouteDuration] = useState<number | null>(null);
  const [pricing, setPricing] = useState(DEFAULT_PRICING);
  const [ride, setRide] = useState<TaxiRide | null>(null);
  const [error, setError] = useState("");
  const [mapReady, setMapReady] = useState(false);
  const mapHost = useRef<HTMLDivElement>(null);
  const map = useRef<import("leaflet").Map | null>(null);
  const leaflet = useRef<typeof import("leaflet") | null>(null);
  const routeLayer = useRef<import("leaflet").Layer | null>(null);
  const fromMarker = useRef<import("leaflet").Layer | null>(null);
  const skipMove = useRef(false);
  const userMovedMap = useRef(false);
  const geolocationRequestId = useRef(0);
  const pickRef = useRef(pickMode);
  const ozimRef = useRef(ozim);
  const reverseGeocode = api.reverseGeocode;
  pickRef.current = pickMode;
  ozimRef.current = ozim;

  const distance = useMemo(
    () => (!ozim && to ? (routeDistance ?? distanceKm(from, to)) : null),
    [from, ozim, routeDistance, to],
  );
  const estimatedPrice = price(kind, distance, pricing);

  const requestCurrentLocation = useCallback(
    (force: boolean) => {
      if (typeof navigator === "undefined" || !navigator.geolocation) return;
      const requestId = geolocationRequestId.current + 1;
      geolocationRequestId.current = requestId;
      navigator.geolocation.getCurrentPosition(
        (position) => {
          if (
            requestId !== geolocationRequestId.current ||
            (!force && userMovedMap.current)
          )
            return;
          const point = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
          };
          setFrom(point);
          setFromAddr("📍 Joriy manzilim");
          if (map.current) {
            skipMove.current = true;
            map.current.setView([point.latitude, point.longitude]);
            window.setTimeout(() => {
              skipMove.current = false;
            }, 800);
          }
          if (reverseGeocode) {
            void reverseGeocode(point.latitude, point.longitude)
              .then((value) => {
                if (requestId !== geolocationRequestId.current) return;
                setFromAddr(
                  value.address || value.district || value.region || "Joriy manzilim",
                );
              })
              .catch(() => undefined);
          }
        },
        () => undefined,
        {
          enableHighAccuracy: true,
          timeout: 8000,
          maximumAge: 60000,
        },
      );
    },
    [reverseGeocode],
  );

  useEffect(() => {
    let active = true;
    if (api.getTaxiPricing) {
      void api
        .getTaxiPricing()
        .then((value) => {
          if (active) setPricing(value);
        })
        .catch(() => undefined);
    }
    if (authenticated && api.getMyTaxiRides) {
      void api
        .getMyTaxiRides()
        .then((value) => {
          if (!active || !value.ride) return;
          setRide(value.ride);
          setPhase(value.ride.status === "pending" ? "search" : "found");
        })
        .catch(() => undefined);
    }
    return () => {
      active = false;
    };
  }, [api, authenticated]);

  useEffect(() => {
    requestCurrentLocation(false);
    return () => {
      geolocationRequestId.current += 1;
    };
  }, [requestCurrentLocation]);

  useEffect(() => {
    if (!mapHost.current) return undefined;
    let disposed = false;
    void import("leaflet")
      .then((module) => {
        if (disposed || !mapHost.current) return;
        leaflet.current = module.default;
        const instance = module.default
          .map(mapHost.current, {
            attributionControl: true,
            zoomControl: false,
          })
          .setView([center.latitude, center.longitude], 14);
        module.default
          .tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: "© OpenStreetMap",
            maxZoom: 19,
          })
          .addTo(instance);
        instance.on("dragstart", () => {
          userMovedMap.current = true;
          geolocationRequestId.current += 1;
        });
        instance.on("moveend", () => {
          if (skipMove.current) {
            skipMove.current = false;
            return;
          }
          const current = instance.getCenter();
          const point = { latitude: current.lat, longitude: current.lng };
          if (pickRef.current === "from") {
            setFrom(point);
            setFromAddr("Manzil aniqlanmoqda...");
            if (reverseGeocode) {
              void reverseGeocode(current.lat, current.lng)
                .then((value) => {
                  setFromAddr(
                    value.address ||
                      value.district ||
                      value.region ||
                      `${current.lat.toFixed(5)}, ${current.lng.toFixed(5)}`,
                  );
                })
                .catch(() =>
                  setFromAddr(`${current.lat.toFixed(5)}, ${current.lng.toFixed(5)}`),
                );
            }
          } else if (!ozimRef.current) {
            setTo(point);
            setToAddr("Manzil aniqlanmoqda...");
            if (reverseGeocode) {
              void reverseGeocode(current.lat, current.lng)
                .then((value) => {
                  setToAddr(
                    value.address ||
                      value.district ||
                      value.region ||
                      `${current.lat.toFixed(5)}, ${current.lng.toFixed(5)}`,
                  );
                })
                .catch(() =>
                  setToAddr(`${current.lat.toFixed(5)}, ${current.lng.toFixed(5)}`),
                );
            } else {
              setToAddr(`${current.lat.toFixed(5)}, ${current.lng.toFixed(5)}`);
            }
          }
        });
        map.current = instance;
        setMapReady(true);
        window.setTimeout(() => instance.invalidateSize(), 120);
      })
      .catch(() => undefined);
    return () => {
      disposed = true;
      setMapReady(false);
      map.current?.remove();
      map.current = null;
      leaflet.current = null;
      routeLayer.current = null;
      fromMarker.current = null;
    };
  }, [center.latitude, center.longitude, reverseGeocode]);

  useEffect(() => {
    const instance = map.current;
    const module = leaflet.current;
    if (!mapReady || !instance || !module) return;
    if (fromMarker.current) instance.removeLayer(fromMarker.current);
    const icon = module.divIcon({
      className: "taxi-call-v1656__origin-icon",
      html: '<span aria-hidden="true"></span>',
      iconAnchor: [20, 20],
      iconSize: [40, 40],
    });
    fromMarker.current = module
      .marker([from.latitude, from.longitude], { icon })
      .addTo(instance);
  }, [from.latitude, from.longitude, mapReady]);

  useEffect(() => {
    if (ozim || !to) {
      setRouteDistance(null);
      setRouteDuration(null);
      if (routeLayer.current && map.current)
        map.current.removeLayer(routeLayer.current);
      routeLayer.current = null;
      return undefined;
    }
    const controller = new AbortController();
    const url =
      "https://router.project-osrm.org/route/v1/driving/" +
      `${from.longitude},${from.latitude};${to.longitude},${to.latitude}` +
      "?overview=full&geometries=geojson";
    void fetch(url, { signal: controller.signal })
      .then((response) => response.json())
      .then(
        (payload: {
          routes?: Array<{
            distance: number;
            duration: number;
            geometry: GeoJSON.GeoJsonObject;
          }>;
        }) => {
          const route = payload.routes?.[0];
          if (!route) return;
          setRouteDistance(route.distance / 1000);
          setRouteDuration(Math.round(route.duration / 60));
          const instance = map.current;
          const module = leaflet.current;
          if (!instance || !module) return;
          if (routeLayer.current) instance.removeLayer(routeLayer.current);
          routeLayer.current = module
            .geoJSON(route.geometry, {
              style: { color: "#2563EB", weight: 5, opacity: 0.85 },
            })
            .addTo(instance);
        },
      )
      .catch(() => undefined);
    return () => controller.abort();
  }, [from.latitude, from.longitude, ozim, to]);

  useEffect(() => {
    if (!ride || phase === "form" || !api.getMyTaxiRides) return undefined;
    const timer = window.setInterval(() => {
      void api
        .getMyTaxiRides?.()
        .then((value) => {
          if (!value.ride) {
            setRide(null);
            setPhase("form");
            return;
          }
          setRide(value.ride);
          setPhase(value.ride.status === "pending" ? "search" : "found");
        })
        .catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [api, phase, ride?.id]);

  function choosePick(mode: "from" | "to") {
    if (mode === "to" && ozim) return;
    userMovedMap.current = true;
    geolocationRequestId.current += 1;
    setPickMode(mode);
    const point = mode === "from" ? from : to;
    if (point && map.current) {
      skipMove.current = true;
      map.current.setView([point.latitude, point.longitude]);
      window.setTimeout(() => {
        skipMove.current = false;
      }, 800);
    }
  }

  async function submit() {
    if (!authenticated) {
      onNeedLogin("Zakaz qilish");
      return;
    }
    if (!api.createTaxiRide) {
      setError("Taxi xizmati hozircha ulanmagan.");
      return;
    }
    if (!from) {
      setError("Boshlanish joyini belgilang (GPS yoki xaritadan).");
      return;
    }
    if (!ozim && !to) {
      setError(
        "Boradigan joyni xaritada belgilang yoki O'zim aytaman tugmasini bosing.",
      );
      return;
    }
    const body: TaxiRideCreate = {
      kind,
      from_addr: fromAddr,
      to_addr: ozim ? "" : toAddr,
      from_lat: from.latitude,
      from_lng: from.longitude,
      to_lat: ozim ? null : (to?.latitude ?? null),
      to_lng: ozim ? null : (to?.longitude ?? null),
      dist_km: ozim ? null : distance,
      dur_min:
        routeDuration ?? (distance ? Math.max(1, Math.round(distance * 2)) : null),
      ozim,
      cargo: kind === "dostavka" ? cargo.trim() : "",
      car_type: kind === "dostavka" ? carType : "",
      note: "",
    };
    setError("");
    setPhase("search");
    try {
      const created = await api.createTaxiRide(body);
      setRide(created);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Zakaz yuborilmadi. Internetni tekshiring.",
      );
      setPhase("form");
    }
  }

  async function cancel() {
    if (ride && api.cancelTaxiRide) {
      await api.cancelTaxiRide(ride.id).catch(() => undefined);
    }
    setRide(null);
    setPhase("form");
    onBack();
  }

  return (
    <main className="screen active taxi-call-v1656" data-screen="taxi-call">
      <div className="taxi-call-v1656__shell">
        <section className="call-panel" id="callPanel">
          {phase === "search" ? (
            <div className="panel-card taxi-call-v1656__centered">
              <div className="spinner" />
              <b>Haydovchi qidirilmoqda...</b>
              <div className="list-sub">
                Yaqin atrofdagi bo'sh haydovchilarga yuborildi
              </div>
              <button
                className="btn btn-outline btn-block"
                type="button"
                onClick={cancel}
              >
                Bekor qilish
              </button>
            </div>
          ) : phase === "found" && ride ? (
            <>
              <div className="panel-card taxi-call-v1656__centered">
                <b>{statusLabel(ride)}</b>
                <button
                  aria-label="Bekor qilish"
                  className="panel-x"
                  type="button"
                  onClick={cancel}
                >
                  ✕
                </button>
              </div>
              <DriverCard ride={ride} onCancel={cancel} />
            </>
          ) : (
            <div className="panel-card">
              <button
                aria-label="Yopish"
                className="panel-x"
                type="button"
                onClick={onBack}
              >
                ✕
              </button>
              <div className="call-price">
                {ozim ? (
                  "Manzil og'zaki aytiladi — narx bosib o'tilgan masofa bo'yicha, safar oxirida 🧭"
                ) : estimatedPrice ? (
                  <>
                    <strong>~{money(estimatedPrice)} so'm</strong>
                    <br />
                    <small>{distance?.toFixed(1)} km · naqd, haydovchiga</small>
                  </>
                ) : to ? (
                  "Narx hisoblanmoqda..."
                ) : (
                  "Boradigan joyni belgilang — narx shu yerda chiqadi"
                )}
              </div>
              <div className="sort-row taxi-call-v1656__tabs">
                <button
                  className={`sort-chip${kind === "taxi" ? " on" : ""}`}
                  type="button"
                  onClick={() => setKind("taxi")}
                >
                  🚖 Taxi
                </button>
                <button
                  className={`sort-chip${kind === "dostavka" ? " on" : ""}`}
                  type="button"
                  onClick={() => setKind("dostavka")}
                >
                  📦 Dostavka
                </button>
              </div>
              <div className="field">
                <span className="taxi-call-v1656__field-label">
                  Qayerdan{pickMode === "from" ? <em> — xaritani suring</em> : null}
                </span>
                <div className="taxi-call-v1656__from-row">
                  <button
                    className={`input taxi-call-v1656__input-button${pickMode === "from" ? " is-active" : ""}`}
                    type="button"
                    onClick={() => choosePick("from")}
                  >
                    {fromAddr}
                  </button>
                  <button
                    aria-label="Joriy joylashuvni olish"
                    className="taxi-call-v1656__gps"
                    type="button"
                    onClick={() => requestCurrentLocation(true)}
                  >
                    📍 GPS
                  </button>
                </div>
              </div>
              <div className="field">
                <span className="taxi-call-v1656__field-label">
                  Qayerga
                  {pickMode === "to" && !ozim ? <em> — xaritani suring</em> : null}
                </span>
                <button
                  disabled={ozim}
                  className={`input taxi-call-v1656__input-button${pickMode === "to" && !ozim ? " is-active" : ""}`}
                  type="button"
                  onClick={() => choosePick("to")}
                >
                  {toAddr || "Bu maydonni tanlab xaritani suring"}
                </button>
              </div>
              <button
                className={`sort-chip taxi-call-v1656__say-it${ozim ? " on" : ""}`}
                type="button"
                onClick={() => {
                  setOzim((current) => !current);
                  setTo(null);
                  setToAddr("");
                }}
              >
                🗣 O'zim aytaman
              </button>
              {kind === "dostavka" ? (
                <>
                  <fieldset className="field taxi-call-v1656__vehicle-field">
                    <legend>Mashina turi</legend>
                    <div className="taxi-call-v1656__vehicle-options">
                      {(["Yengil yuk", "Katta yuk"] as const).map((option) => (
                        <button
                          aria-pressed={carType === option}
                          className={`sort-chip${carType === option ? " on" : ""}`}
                          key={option}
                          type="button"
                          onClick={() => setCarType(option)}
                        >
                          {option}
                        </button>
                      ))}
                    </div>
                  </fieldset>
                  <label className="field taxi-call-v1656__cargo-field">
                    <span className="taxi-call-v1656__field-label">Yuk turi</span>
                    <input
                      aria-label="Yuk turi"
                      className="input"
                      placeholder="Masalan: mebel, quti, texnika"
                      value={cargo}
                      onChange={(event) => setCargo(event.currentTarget.value)}
                    />
                  </label>
                </>
              ) : null}
              {error ? (
                <p className="elon-hint" role="alert">
                  {error}
                </p>
              ) : null}
              <button
                className="btn btn-primary btn-block"
                type="button"
                onClick={() => void submit()}
              >
                Zakaz qilish
              </button>
            </div>
          )}
        </section>
        <div className="taxi-call-v1656__map-wrap">
          <div className="taxi-call-v1656__map" id="taxiCallMap" ref={mapHost} />
          {phase === "form" ? (
            <div className="taxi-call-v1656__center-pin">📍</div>
          ) : null}
          {district ? (
            <div className="taxi-call-v1656__map-chip">⌾ {district}</div>
          ) : null}
          <button
            aria-label="Taxi oynasidan chiqish"
            className="taxi-call-v1656__map-action"
            type="button"
            onClick={onBack}
          >
            🚖
          </button>
        </div>
      </div>
    </main>
  );
}

function DriverCard({ ride, onCancel }: { ride: TaxiRide; onCancel(): void }) {
  const driver = ride.driver;
  const canCancel =
    ride.kind === "dostavka"
      ? ride.status === "accepted"
      : ["accepted", "arrived"].includes(ride.status);
  const cost = ride.ozim ? ride.final_price : ride.price;
  return (
    <div className="panel-card taxi-call-v1656__driver-card" id="driverCard">
      <div className="taxi-call-v1656__driver-row">
        <div className="cab-logo">{ride.kind === "dostavka" ? "📦" : "🚖"}</div>
        <div>
          <b>{driver?.name || "Haydovchi"}</b>
          <div className="list-sub">
            {[driver?.car_color, driver?.car_model].filter(Boolean).join(" ") ||
              "Mashina"}
            {driver?.car_plate ? ` · ${driver.car_plate}` : ""}
          </div>
          {cost ? (
            <div className="list-sub taxi-call-v1656__price">
              💰 ~{money(cost)} so'm (naqd)
            </div>
          ) : null}
          {ride.ozim ? <div className="list-sub">Manzilni og'zaki aytasiz</div> : null}
        </div>
      </div>
      <div className="taxi-call-v1656__actions">
        {driver?.phone ? (
          <a className="btn btn-primary" href={`tel:${driver.phone}`}>
            📞 Qo'ng'iroq
          </a>
        ) : null}
        {canCancel ? (
          <button className="btn btn-outline" type="button" onClick={onCancel}>
            Bekor qilish
          </button>
        ) : null}
      </div>
    </div>
  );
}
