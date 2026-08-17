import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { ApiClient } from "../api/client";
import type { TaxiKind, TaxiPricing, TaxiRide, TaxiRideCreate } from "../api/types";
import { TaxiCallView } from "./TaxiCallView";
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
    <TaxiCallView
      phase={phase}
      ride={ride}
      cancel={cancel}
      onBack={onBack}
      ozim={ozim}
      estimatedPrice={estimatedPrice}
      distance={distance}
      kind={kind}
      setKind={setKind}
      pickMode={pickMode}
      fromAddr={fromAddr}
      choosePick={choosePick}
      requestCurrentLocation={requestCurrentLocation}
      to={to}
      toAddr={toAddr}
      setOzim={setOzim}
      setTo={setTo}
      setToAddr={setToAddr}
      carType={carType}
      setCarType={setCarType}
      cargo={cargo}
      setCargo={setCargo}
      error={error}
      submit={submit}
      mapHost={mapHost}
      district={district}
    />
  );
}
