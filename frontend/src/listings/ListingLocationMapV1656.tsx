import type { Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";


type Props = {
  latitude: number;
  longitude: number;
};


export function ListingLocationMapV1656({ latitude, longitude }: Props) {
  const node = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!node.current) return undefined;
    let disposed = false;
    let map: LeafletMap | null = null;
    let resizeTimer: number | null = null;

    void import("leaflet").then(({ default: leaflet }) => {
      if (disposed || !node.current) return;
      map = leaflet.map(node.current, {
        attributionControl: false,
        scrollWheelZoom: false,
      }).setView([latitude, longitude], 16);
      leaflet.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
      }).addTo(map);
      leaflet.marker([latitude, longitude]).addTo(map);
      resizeTimer = window.setTimeout(() => map?.invalidateSize(), 180);
    }).catch(() => undefined);

    return () => {
      disposed = true;
      if (resizeTimer != null) window.clearTimeout(resizeTimer);
      map?.remove();
    };
  }, [latitude, longitude]);

  return (
    <div
      aria-label="E'lon xaritasi"
      className="listing-detail-map"
      ref={node}
    />
  );
}
