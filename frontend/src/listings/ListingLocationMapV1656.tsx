import type { Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";
import markerIcon2xUrl from "leaflet/dist/images/marker-icon-2x.png";
import markerIconUrl from "leaflet/dist/images/marker-icon.png";
import markerShadowUrl from "leaflet/dist/images/marker-shadow.png";
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

    void import("leaflet")
      .then(({ default: leaflet }) => {
        if (disposed || !node.current) return;
        map = leaflet
          .map(node.current, {
            attributionControl: false,
            scrollWheelZoom: false,
            zoomControl: false,
          })
          .setView([latitude, longitude], 16);
        leaflet
          .tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
          })
          .addTo(map);
        const icon = leaflet.icon({
          iconAnchor: [12, 41],
          iconRetinaUrl: markerIcon2xUrl,
          iconSize: [25, 41],
          iconUrl: markerIconUrl,
          shadowSize: [41, 41],
          shadowUrl: markerShadowUrl,
        });
        leaflet.marker([latitude, longitude], { icon }).addTo(map);
        resizeTimer = window.setTimeout(() => map?.invalidateSize(), 180);
      })
      .catch(() => undefined);

    return () => {
      disposed = true;
      if (resizeTimer != null) window.clearTimeout(resizeTimer);
      map?.remove();
    };
  }, [latitude, longitude]);

  return <div aria-label="E'lon xaritasi" className="listing-detail-map" ref={node} />;
}
