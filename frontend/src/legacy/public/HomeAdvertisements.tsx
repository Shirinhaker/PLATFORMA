import { useEffect, useState } from "react";

import type { ApiClient } from "../../api/client";
import type { PublicAdvertisement } from "../../api/types";
import type { HomeLocation } from "./location-storage";


interface HomeAdvertisementsProps {
  getAdvertisements: ApiClient["getAdvertisements"];
  location: HomeLocation | null;
}


export function HomeAdvertisements({
  getAdvertisements,
  location,
}: HomeAdvertisementsProps) {
  const [items, setItems] = useState<PublicAdvertisement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    getAdvertisements({
      placement: "home",
      region: location?.region || "",
      district: location?.district || "",
    })
      .then((result) => {
        if (active) setItems(result);
      })
      .catch(() => {
        if (active) setError("Reklamalarni yuklab bo‘lmadi.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [
    attempt,
    getAdvertisements,
    location?.district,
    location?.region,
  ]);

  if (loading) {
    return <div className="public-ad-status" role="status">Yuklanmoqda…</div>;
  }
  if (error) {
    return (
      <div className="public-ad-status" role="alert">
        <span>{error}</span>
        <button type="button" onClick={() => setAttempt((value) => value + 1)}>
          Qayta urinish
        </button>
      </div>
    );
  }
  if (!items.length) {
    return (
      <div className="public-ad-status">
        Hozir faol reklama yo‘q
      </div>
    );
  }

  const mobile = window.innerWidth <= 640;
  return (
    <section className="public-home-ads" aria-label="Reklamalar">
      {items.map((item) => (
        <article className="public-home-ad" key={item.public_id}>
          <img
            src={(
              mobile && item.mobile_image_url
                ? item.mobile_image_url
                : item.desktop_image_url || "/assets/catalog-placeholder.svg"
            )}
            alt={item.title}
            style={{
              objectPosition: `${item.crop_x}% ${item.crop_y}%`,
              transform: `scale(${item.crop_zoom})`,
            }}
          />
          <div>
            <strong>{item.title}</strong>
            {item.caption ? <span>{item.caption}</span> : null}
          </div>
        </article>
      ))}
    </section>
  );
}

