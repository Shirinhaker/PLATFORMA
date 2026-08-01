import { useCallback, useEffect, useRef, useState } from "react";

import type { ApiClient } from "../../api/client";
import type { PublicAdvertisement } from "../../api/types";
import { AppToastV1656 } from "./AppToastV1656";
import type { HomeLocation } from "./location-storage";


type HomeAd = PublicAdvertisement & { is_demo?: boolean };

interface HomeAdvertisementsProps {
  getAdvertisements: ApiClient["getAdvertisements"];
  location: HomeLocation | null;
  onOpenOwner?: (kind: "user" | "business", publicId: string) => void;
  recordAdvertisementClick?: ApiClient["recordAdvertisementClick"];
  recordAdvertisementViews?: ApiClient["recordAdvertisementViews"];
}


const DEMO_HOME_ADS: HomeAd[] = [
  { public_id: "demo-1", title: "Orzu Mebel", caption: "Uyingiz uchun eng yaxshi tanlovlar", owner_public_id: "", desktop_image_url: "/demo_ads/demo_sofa.svg", mobile_image_url: "", crop_x: 62, crop_y: 50, crop_zoom: 1, is_demo: true },
  { public_id: "demo-2", title: "Samarqand Coffee", caption: "Issiq qahva va yangi desertlar", owner_public_id: "", desktop_image_url: "/demo_ads/demo_cafe.svg", mobile_image_url: "", crop_x: 72, crop_y: 52, crop_zoom: 1.12, is_demo: true },
  { public_id: "demo-3", title: "Smart Texnika", caption: "Telefon va aksessuarlarga foydali taklif", owner_public_id: "", desktop_image_url: "/demo_ads/demo_tech.svg", mobile_image_url: "", crop_x: 77, crop_y: 48, crop_zoom: 1.05, is_demo: true },
  { public_id: "demo-4", title: "Mahalla Market", caption: "Bugungi mahsulotlarga maxsus chegirma", owner_public_id: "", desktop_image_url: "/demo_ads/demo_market.svg", mobile_image_url: "", crop_x: 38, crop_y: 50, crop_zoom: 1.08, is_demo: true },
  { public_id: "demo-5", title: "Nafis Beauty", caption: "Go'zalligingiz uchun yangi xizmatlar", owner_public_id: "", desktop_image_url: "/demo_ads/demo_beauty.svg", mobile_image_url: "", crop_x: 76, crop_y: 50, crop_zoom: 1.1, is_demo: true },
];


export function HomeAdvertisements({
  getAdvertisements,
  location,
  onOpenOwner,
  recordAdvertisementClick,
  recordAdvertisementViews,
}: HomeAdvertisementsProps) {
  const [items, setItems] = useState<HomeAd[]>(DEMO_HOME_ADS);
  const [activeIndex, setActiveIndex] = useState(0);
  const [message, setMessage] = useState("");
  const [transitioning, setTransitioning] = useState(false);
  const [visible, setVisible] = useState(() => !document.hidden);
  const activeIndexRef = useRef(0);
  const itemsRef = useRef<HomeAd[]>(DEMO_HOME_ADS);
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
      return result.length ? result : DEMO_HOME_ADS;
    } catch {
      return DEMO_HOME_ADS;
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
      // v1656 ko‘rilish xatosini foydalanuvchiga ko‘rsatmaydi.
    }
  }, [recordAdvertisementViews]);

  const transitionTo = useCallback((nextIndex: number, nextItems?: HomeAd[]) => {
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
    if (!visible || !item || item.is_demo) return undefined;
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

  const item = items[activeIndex] ?? DEMO_HOME_ADS[0]!;

  function openAdvertisement() {
    if (item.is_demo) {
      setMessage("Bu namoyish uchun joylangan demo reklama.");
      return;
    }
    if (recordAdvertisementClick) {
      void recordAdvertisementClick(item.public_id);
    }
    if (item.owner_public_id && item.owner_kind && onOpenOwner) {
      onOpenOwner(item.owner_kind, item.owner_public_id);
    }
  }

  return (
    <>
      <div
        className={`ad has-image${transitioning ? " ad-transitioning" : ""}`}
        id="adBox"
        onClick={openAdvertisement}
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
      <AppToastV1656 message={message} />
    </>
  );
}
