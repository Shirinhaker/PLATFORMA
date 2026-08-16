import { useEffect, useRef } from "react";
import type { Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";

export function OrderLocationMap({
  latitude,
  longitude,
}: {
  latitude: number;
  longitude: number;
}) {
  const node = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!node.current) return undefined;
    let disposed = false;
    let map: LeafletMap | null = null;
    void import("leaflet")
      .then(({ default: leaflet }) => {
        if (disposed || !node.current) return;
        map = leaflet
          .map(node.current, { attributionControl: false })
          .setView([latitude, longitude], 16);
        leaflet
          .tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
          })
          .addTo(map);
        leaflet.marker([latitude, longitude]).addTo(map);
        window.setTimeout(() => map?.invalidateSize(), 240);
      })
      .catch(() => undefined);
    return () => {
      disposed = true;
      map?.remove();
    };
  }, [latitude, longitude]);

  return <div className="order-detail-map" ref={node} />;
}
