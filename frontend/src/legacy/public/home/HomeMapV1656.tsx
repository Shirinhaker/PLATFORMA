import { useEffect, useRef } from "react";

import type {
  PublicHomeBusinessPin,
  PublicHomeSpecialistPin,
  PublicSearchItem,
} from "../../../api/types";
import { CATALOG_DIRECTIONS } from "../catalog-data";


interface HomeMapV1656Props {
  businesses: PublicHomeBusinessPin[];
  center?: { latitude: number; longitude: number };
  district: string;
  resultItems: PublicSearchItem[] | null;
  specialists: PublicHomeSpecialistPin[];
  onCloseResults(): void;
  onOpenResult(
    kind: "user" | "business" | "product" | "service",
    publicId: string,
  ): void;
}

type MapPoint = {
  kind: "user" | "business" | "product" | "service";
  publicId: string;
  label: string;
  latitude: number;
  longitude: number;
  color: string;
  fallback: string;
  photo: string;
  photoX: number;
  photoY: number;
  photoZoom: number;
  small: boolean;
};


function escapeHtml(value: string) {
  return value.replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    "\"": "&quot;",
  })[character] ?? character);
}


function normalizeDirection(value: string) {
  return value.replace(/[‘’ʻʼ`]/g, "'").trim().toLocaleLowerCase("uz");
}


function directionMeta(direction: string) {
  const normalized = normalizeDirection(direction);
  return CATALOG_DIRECTIONS.find(
    (item) => normalizeDirection(item.name) === normalized,
  ) ?? { color: "#0E8C84", icon: "🏪" };
}


function avatarImageStyle(x: number, y: number, zoom: number) {
  const size = Number((zoom * 100).toFixed(4));
  const left = Number((50 - x * zoom).toFixed(4));
  const top = Number((50 - y * zoom).toFixed(4));
  return [
    "position:absolute",
    `width:${size}%`,
    `height:${size}%`,
    "max-width:none",
    "max-height:none",
    "object-fit:cover",
    `left:${left}%`,
    `top:${top}%`,
    "transform:none",
  ].join(";");
}


export function HomeMapV1656({
  businesses,
  center,
  district,
  resultItems,
  specialists,
  onCloseResults,
  onOpenResult,
}: HomeMapV1656Props) {
  const mapElement = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = mapElement.current;
    if (!host || typeof window === "undefined") return undefined;
    let disposed = false;
    let cleanup = () => undefined;
    const normalPoints: MapPoint[] = [
      ...businesses.map((item) => {
        const metadata = directionMeta(item.yon);
        return {
          kind: "business" as const,
          publicId: item.public_id,
          label: item.name,
          latitude: item.lat,
          longitude: item.lng,
          color: metadata.color,
          fallback: metadata.icon,
          photo: item.logo_file,
          photoX: item.logo_x,
          photoY: item.logo_y,
          photoZoom: item.logo_zoom,
          small: false,
        };
      }),
      ...specialists.map((item) => ({
        kind: "user" as const,
        publicId: item.public_id,
        label: item.name,
        latitude: item.lat,
        longitude: item.lng,
        color: item.is_gov ? "#2563EB" : "#16A34A",
        fallback: item.name.trim().charAt(0) || "?",
        photo: item.avatar_file,
        photoX: item.avatar_x,
        photoY: item.avatar_y,
        photoZoom: item.avatar_zoom,
        small: true,
      })),
    ];
    const points = resultItems ? [] : normalPoints;

    void import("leaflet").then((leafletModule) => {
      if (disposed || !mapElement.current) return;
      const L = leafletModule.default;
      const start = (
        center
        && Number.isFinite(center.latitude)
        && Number.isFinite(center.longitude)
      )
        ? [center.latitude, center.longitude] as [number, number]
        : [41.3111, 69.2797] as [number, number];
      const map = L.map(host, {
        attributionControl: true,
        zoomControl: false,
      }).setView(start, 14);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a>",
        maxZoom: 19,
      }).addTo(map);
      points.forEach((point) => {
        const fallback = `<span class="pin-fallback">${escapeHtml(point.fallback)}</span>`;
        const photo = point.photo
          ? `${fallback}<img src="${escapeHtml(point.photo)}" alt="" style="${avatarImageStyle(point.photoX, point.photoY, point.photoZoom)}" onerror="this.remove()">`
          : fallback;
        const smallStyle = point.small
          ? "font-size:12px;font-weight:800;color:#fff;"
          : "";
        const icon = L.divIcon({
          className: "leaflet-pin",
          html: `<div class="pin"><div class="plabel">${escapeHtml(point.label)}</div><div class="dot${point.photo ? " has-photo" : ""}" style="background:${point.color};${smallStyle}">${photo}</div><div class="tail"></div></div>`,
          iconAnchor: [23, 52],
          iconSize: [46, 54],
        });
        L.marker([point.latitude, point.longitude], { icon })
          .addTo(map)
          .on("click", () => onOpenResult(point.kind, point.publicId));
      });
      const invalidate = window.setTimeout(() => map.invalidateSize(), 240);
      cleanup = () => {
        window.clearTimeout(invalidate);
        map.remove();
      };
    }).catch(() => undefined);

    return () => {
      disposed = true;
      cleanup();
    };
  }, [
    businesses,
    center?.latitude,
    center?.longitude,
    onOpenResult,
    resultItems,
    specialists,
  ]);

  return (
    <div className="home-map-pane" id="homeMapPane">
      <div className="pin-eyebrow" id="pinEyebrow">
        <svg aria-hidden="true" viewBox="0 0 24 24">
          <path d="M12 21s-7-6.3-7-11a7 7 0 0 1 14 0c0 4.7-7 11-7 11z" />
          <circle cx="12" cy="10" r="2.4" />
        </svg>
        Yaqin atrofdagilar
      </div>
      <div className="map-wrap">
        <div id="leafletMap" ref={mapElement} />
        {resultItems ? (
          <button
            className="map-chip"
            id="mapChip"
            type="button"
            onClick={onCloseResults}
          >
            🔎 Qidiruv natijalari <span className="x">✕</span>
          </button>
        ) : (
          <div className="map-chip" id="mapChip">
            <svg aria-hidden="true" viewBox="0 0 24 24">
              <path d="M12 21s-7-6.3-7-11a7 7 0 0 1 14 0c0 4.7-7 11-7 11z" />
              <circle cx="12" cy="10" r="2.4" />
            </svg>{" "}
            {district || "Hudud tanlanmagan"}
          </div>
        )}
        <button
          hidden
          aria-label="Chaqiruv"
          className="icon-btn"
          data-feature="taxi"
          id="taxiBtn"
          style={{
            position: "absolute",
            top: 12,
            right: 12,
            zIndex: 500,
            fontSize: 19,
          }}
          type="button"
        >
          🚖
        </button>
        <div
          hidden
          id="centerPin"
          style={{
            position: "absolute",
            left: "50%",
            top: "50%",
            zIndex: 500,
            fontSize: 36,
            filter: "drop-shadow(0 3px 4px rgba(0,0,0,.3))",
            pointerEvents: "none",
            transform: "translate(-50%,-100%)",
          }}
        >
          📍
        </div>
      </div>
    </div>
  );
}
