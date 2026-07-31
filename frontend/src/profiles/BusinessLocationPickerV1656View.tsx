import { useEffect, useRef, useState } from "react";
import type { Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";

import "./BusinessLocationPickerV1656View.css";


export type PicklocPrefix = "bp" | "be" | "ue";
export type PicklocReturnScreen = (
  "cab-profil" | "cab-elon-form" | "ucab-elon-form"
);
export type PicklocPoint = { latitude: number; longitude: number };

type Props = {
  prefix: PicklocPrefix;
  value?: PicklocPoint | null;
  fallback?: PicklocPoint | null;
  onCancel: (screen: PicklocReturnScreen) => void;
  onConfirm: (
    point: PicklocPoint,
    screen: PicklocReturnScreen,
  ) => void | Promise<void>;
};

const TASHKENT_CENTER: PicklocPoint = {
  latitude: 41.311,
  longitude: 69.28,
};
const BUSINESS_PICK_POINT_KEY = "business_pick_point";


function safeNumber(value: unknown): number | null {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}


export function normalizeLatLng(
  latitudeValue: unknown,
  longitudeValue: unknown,
): PicklocPoint | null {
  let latitude = safeNumber(latitudeValue);
  let longitude = safeNumber(longitudeValue);
  if (latitude === null || longitude === null) return null;

  if (Math.abs(latitude) > 90 && Math.abs(longitude) <= 90) {
    [latitude, longitude] = [longitude, latitude];
  }
  if (Math.abs(latitude) > 90 || Math.abs(longitude) > 180) return null;
  return { latitude, longitude };
}


export function pickReturnScreen(prefix: PicklocPrefix): PicklocReturnScreen {
  if (prefix === "be") return "cab-elon-form";
  if (prefix === "ue") return "ucab-elon-form";
  return "cab-profil";
}


export function buildAddrText(address: Record<string, unknown>): string {
  const district = String(
    address.city_district
      || address.county
      || address.suburb
      || address.town
      || address.village
      || "",
  );
  const region = String(address.state || address.region || "");
  const street = String(address.road || address.neighbourhood || "");
  const parts: string[] = [];
  if (street) parts.push(street);
  if (district) parts.push(district);
  if (region && region !== district) parts.push(region);
  return parts.join(", ");
}


function storedBusinessPoint(): PicklocPoint | null {
  try {
    const raw = localStorage.getItem(BUSINESS_PICK_POINT_KEY);
    if (!raw) return null;
    const point = JSON.parse(raw) as { lat?: unknown; lng?: unknown };
    return normalizeLatLng(point.lat, point.lng);
  } catch {
    return null;
  }
}


function saveBusinessPoint(point: PicklocPoint) {
  try {
    localStorage.setItem(BUSINESS_PICK_POINT_KEY, JSON.stringify({
      lat: point.latitude,
      lng: point.longitude,
    }));
  } catch {
    // Monolit kabi storage ishlamasa ham tanlash oqimi davom etadi.
  }
}


export function BusinessLocationPickerV1656View({
  prefix,
  value = null,
  fallback = null,
  onCancel,
  onConfirm,
}: Props) {
  const screenRef = useRef<HTMLElement | null>(null);
  const mapNodeRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const returnScreen = pickReturnScreen(prefix);
  const start = (
    normalizeLatLng(value?.latitude, value?.longitude)
    ?? (prefix === "bp"
      ? storedBusinessPoint()
      : normalizeLatLng(fallback?.latitude, fallback?.longitude))
    ?? TASHKENT_CENTER
  );
  const startLatitude = start.latitude;
  const startLongitude = start.longitude;

  useEffect(() => {
    const node = mapNodeRef.current;
    const screenNode = screenRef.current;
    if (!node || !screenNode) return;

    let disposed = false;
    let sizeTimer: number | undefined;
    let animationFallback: number | undefined;
    let observer: ResizeObserver | null = null;
    let map: LeafletMap | null = null;
    const syncMapSize = () => {
      window.clearTimeout(sizeTimer);
      sizeTimer = window.setTimeout(() => {
        const current = mapRef.current;
        if (!current) return;
        const center = current.getCenter();
        const zoom = current.getZoom();
        current.invalidateSize({ pan: false });
        current.setView(center, zoom, { animate: false });
      }, 40);
    };

    void import("leaflet").then(({ default: leaflet }) => {
      if (disposed) return;
      map = leaflet.map(node, {
        zoomControl: true,
        attributionControl: false,
      }).setView([startLatitude, startLongitude], 14);
      leaflet.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
      }).addTo(map);
      mapRef.current = map;

      screenNode.addEventListener("animationend", syncMapSize);
      window.addEventListener("resize", syncMapSize);
      window.addEventListener("orientationchange", syncMapSize);
      window.visualViewport?.addEventListener("resize", syncMapSize);
      observer = typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver(syncMapSize);
      observer?.observe(node);
      animationFallback = window.setTimeout(syncMapSize, 240);
    }).catch(() => {
      if (!disposed) {
        setError("Xarita hali yuklanmoqda, bir lahza kuting va qayta urinib ko'ring.");
      }
    });

    return () => {
      disposed = true;
      window.clearTimeout(sizeTimer);
      window.clearTimeout(animationFallback);
      observer?.disconnect();
      screenNode.removeEventListener("animationend", syncMapSize);
      window.removeEventListener("resize", syncMapSize);
      window.removeEventListener("orientationchange", syncMapSize);
      window.visualViewport?.removeEventListener("resize", syncMapSize);
      mapRef.current = null;
      map?.remove();
    };
  }, [startLatitude, startLongitude]);

  async function confirm() {
    const map = mapRef.current;
    if (!map) {
      onCancel(returnScreen);
      return;
    }
    const center = map.getCenter();
    const point = normalizeLatLng(center.lat, center.lng);
    if (!point) {
      setError("Xarita koordinatasi noto'g'ri. Iltimos, boshqa joyni tanlang.");
      return;
    }
    if (prefix === "bp") saveBusinessPoint(point);
    setBusy(true);
    setError("");
    try {
      await onConfirm(point, returnScreen);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section ref={screenRef} className="screen active" data-screen="pickloc">
      <div style={{ position: "relative" }}>
        <div
          id="pickMap"
          ref={mapNodeRef}
          style={{
            width: "100%",
            height: "calc(100dvh - 180px)",
            minHeight: 340,
            background: "var(--map-land)",
          }}
        />
        <div
          id="pickPin"
          style={{
            position: "absolute",
            left: "50%",
            top: "50%",
            transform: "translate(-50%,-100%)",
            zIndex: 500,
            fontSize: 40,
            filter: "drop-shadow(0 3px 5px rgba(0,0,0,.35))",
            pointerEvents: "none",
          }}
        >📍</div>
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 12,
            textAlign: "center",
            zIndex: 500,
            pointerEvents: "none",
          }}
        >
          <span
            style={{
              background: "var(--card)",
              color: "var(--ink)",
              padding: "8px 14px",
              borderRadius: 12,
              fontSize: 13,
              fontWeight: 600,
              boxShadow: "var(--shadow)",
            }}
          >Xaritani suring — markerni joyga to'g'rilang</span>
        </div>
      </div>
      <div style={{ padding: "14px 16px" }}>
        {error && <div className="app-toast on" role="alert">{error}</div>}
        <button
          className="btn btn-primary btn-block"
          id="pickConfirm"
          type="button"
          disabled={busy}
          onClick={() => void confirm()}
        >✅ Shu joyni tanlash</button>
        <button
          className="btn btn-soft btn-block"
          id="pickCancel"
          type="button"
          style={{ marginTop: 9 }}
          onClick={() => onCancel(returnScreen)}
        >Bekor qilish</button>
      </div>
    </section>
  );
}
