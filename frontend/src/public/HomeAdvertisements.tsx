import { useCallback, useEffect, useRef, useState } from "react";

import type { ApiClient } from "../api/client";
import type { PublicAdvertisement } from "../api/types";
import type { HomeLocation } from "./location-storage";


interface HomeAdvertisementsProps {
  getAdvertisements: ApiClient["getAdvertisements"];
  location: HomeLocation | null;
  onOpenOwner?: (kind: "user" | "business", publicId: string) => void;
  recordAdvertisementClick?: ApiClient["recordAdvertisementClick"];
  recordAdvertisementViews?: ApiClient["recordAdvertisementViews"];
}

export function HomeAdvertisements({
  getAdvertisements,
  location,
  onOpenOwner,
  recordAdvertisementClick,
  recordAdvertisementViews,
}: HomeAdvertisementsProps) {
  const [items, setItems] = useState<PublicAdvertisement[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [transitioning, setTransitioning] = useState(false);
  const [visible, setVisible] = useState(() => !document.hidden);
  const activeIndexRef = useRef(0);
  const itemsRef = useRef<PublicAdvertisement[]>([]);
  const seen = useRef<string[]>([]);
  const switching = useRef(false);
  const switchTimer = useRef<number | null>(null);
  const unlockTimer = useRef<number | null>(null);
  const animationFrame = useRef<number | null>(null);

  const fetchAdvertisements = useCallback(async () => {
    try {
      const result = await getAdvertisements({
        placement: "home",
        region: location?.region || "",
        district: location?.district || "",
      });
      return result;
    } catch {
      return [];
    }
  }, [getAdvertisements, location?.district, location?.region]);

  const flushViews = useCallback(async () => {
    if (!recordAdvertisementViews || !seen.current.length) return;
    const publicIds = seen.current.slice(0, 5);
    try {
      await recordAdvertisementViews(publicIds);
      seen.current = seen.current.filter(
        (publicId) => !publicIds.includes(publicId),
      );
    } catch {
      // modular ko‘rilish xatosini foydalanuvchiga ko‘rsatmaydi.
    }
  }, [recordAdvertisementViews]);

  const transitionTo = useCallback((
    nextIndex: number,
    nextItems?: PublicAdvertisement[],
  ) => {
    if (switching.current) return;
    switching.current = true;
    setTransitioning(true);
    switchTimer.current = window.setTimeout(() => {
      const targetItems = nextItems ?? itemsRef.current;
      if (nextItems) {
        itemsRef.current = nextItems;
        setItems(nextItems);
      }
      const normalizedIndex = Math.max(
        0,
        Math.min(nextIndex, targetItems.length - 1),
      );
      activeIndexRef.current = normalizedIndex;
      setActiveIndex(normalizedIndex);
      animationFrame.current = window.requestAnimationFrame(() => {
        setTransitioning(false);
        unlockTimer.current = window.setTimeout(() => {
          switching.current = false;
        }, 1_000);
      });
    }, 1_000);
  }, []);

  useEffect(() => {
    let active = true;
    fetchAdvertisements()
      .then((result) => {
        if (!active) return;
        itemsRef.current = result;
        activeIndexRef.current = 0;
        setItems(result);
        setActiveIndex(0);
      });
    return () => {
      active = false;
    };
  }, [fetchAdvertisements]);

  useEffect(() => {
    if (!visible || items.length < 2) return undefined;
    const timer = window.setInterval(() => {
      if (switching.current) return;
      const currentItems = itemsRef.current;
      const index = activeIndexRef.current;
      if (index >= currentItems.length - 1) {
        void flushViews().then(fetchAdvertisements).then((nextItems) => {
          transitionTo(0, nextItems);
        });
        return;
      }
      transitionTo(index + 1);
    }, 10_000);
    return () => window.clearInterval(timer);
  }, [fetchAdvertisements, flushViews, items, transitionTo, visible]);

  useEffect(() => {
    const item = items[activeIndex];
    if (!visible || !item) return undefined;
    const publicId = item.public_id;
    const timer = window.setTimeout(() => {
      if (
        !document.hidden
        && itemsRef.current[activeIndexRef.current]?.public_id === publicId
        && !seen.current.includes(publicId)
      ) {
        seen.current.push(publicId);
      }
    }, 2_000);
    return () => window.clearTimeout(timer);
  }, [activeIndex, items, visible]);

  useEffect(() => {
    function visibilityChanged() {
      const pageVisible = !document.hidden;
      setVisible(pageVisible);
      if (!pageVisible) void flushViews();
    }
    document.addEventListener("visibilitychange", visibilityChanged);
    return () => {
      document.removeEventListener("visibilitychange", visibilityChanged);
    };
  }, [flushViews]);

  useEffect(() => () => {
    if (switchTimer.current !== null) window.clearTimeout(switchTimer.current);
    if (unlockTimer.current !== null) window.clearTimeout(unlockTimer.current);
    if (animationFrame.current !== null) {
      window.cancelAnimationFrame(animationFrame.current);
    }
  }, []);

  const item = items[activeIndex];

  if (!item) return null;

  function openAdvertisement(activeItem: PublicAdvertisement) {
    if (recordAdvertisementClick) {
      void recordAdvertisementClick(activeItem.public_id);
    }
    if (activeItem.owner_public_id && activeItem.owner_kind && onOpenOwner) {
      onOpenOwner(activeItem.owner_kind, activeItem.owner_public_id);
    }
  }

  return (
    <>
      <div
        className={`ad has-image${transitioning ? " ad-transitioning" : ""}`}
        id="adBox"
        onClick={() => openAdvertisement(item)}
      >
        <picture className="ad-picture">
          <source
            media="(max-width: 1079px)"
            srcSet={item.mobile_image_url || item.desktop_image_url}
          />
          <img
            alt="Reklama"
            className="ad-photo"
            src={item.desktop_image_url}
            style={{
              objectPosition: item.mobile_image_url
                ? "50% 50%"
                : `${item.crop_x}% ${item.crop_y}%`,
              transform: item.mobile_image_url
                ? "none"
                : `scale(${item.crop_zoom})`,
              transformOrigin: item.mobile_image_url
                ? "50% 50%"
                : `${item.crop_x}% ${item.crop_y}%`,
            }}
          />
        </picture>
        <div className="ad-overlay" />
        <div className="ad-copy">
          <h3>{item.title || "Taklif bilan tanishing"}</h3>
          <p>{item.caption || "Batafsil ko'rish uchun bosing."}</p>
          <span className="ad-cta">Ko‘rish</span>
        </div>
        <div className="blob" />
      </div>
      <div className="dots-row" id="adDots">
        {items.map((ad, index) => (
          <span
            className={index === activeIndex ? "on" : ""}
            data-home-ad-dot={index}
            key={ad.public_id}
            onClick={() => transitionTo(index)}
          />
        ))}
      </div>
    </>
  );
}
