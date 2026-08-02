import {
  type CSSProperties,
  useEffect,
  useState,
} from "react";

import type { ApiClient } from "../../api/client";
import type { PublicCatalogItem, PublicSearchItem } from "../../api/types";
import { CatalogItemCard } from "./CatalogItemCard";
import { findCatalogDirection } from "./catalog-data";
import { PublicSearchResults } from "./PublicSearchResults";
import type { QueueBookingTarget } from "../../queues/QueueBookingV1656";

interface CategoryScreenProps {
  categoryId: string;
  searchPublic?: ApiClient["searchPublic"];
  getCatalogItems?: ApiClient["getCatalogItems"];
  authenticated?: boolean;
  onOpenOwner?(publicId: string): void;
  onNeedQueueLogin?(): void;
  onBookQueue?(target: QueueBookingTarget): void;
  onQueueMessage?(message: string): void;
}

export function CategoryScreen({
  categoryId,
  searchPublic,
  getCatalogItems,
  authenticated = false,
  onOpenOwner,
  onNeedQueueLogin,
  onBookQueue,
  onQueueMessage,
}: CategoryScreenProps) {
  const direction = findCatalogDirection(categoryId);
  const [selectedActivity, setSelectedActivity] = useState<string | null>(null);
  const [items, setItems] = useState<PublicSearchItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [catalogItems, setCatalogItems] = useState<PublicCatalogItem[]>([]);

  useEffect(() => {
    if (!direction || !selectedActivity) return;
    if (!searchPublic && !getCatalogItems) {
      setError("Qidiruv xizmati hozircha ulanmagan.");
      return;
    }

    let active = true;
    setItems([]);
    setLoading(true);
    setError("");
    const profiles = searchPublic
      ? searchPublic({
        result_type: "business",
        direction: direction.name,
        activity_type: selectedActivity,
        page: 1,
        page_size: 20,
      })
      : Promise.resolve(null);
    const catalog = getCatalogItems
      ? getCatalogItems({
        direction: direction.name,
        activity_type: selectedActivity,
        page: 1,
        page_size: 20,
      })
      : Promise.resolve(null);
    Promise.all([profiles, catalog])
      .then(([profileResponse, catalogResponse]) => {
        if (!active) return;
        setItems(profileResponse?.items ?? []);
        setCatalogItems(catalogResponse?.items ?? []);
      })
      .catch(() => {
        if (active) {
          setError("Server bilan bog‘lanib bo‘lmadi. Qayta urinib ko‘ring.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [direction, getCatalogItems, searchPublic, selectedActivity]);

  if (!direction) {
    return (
      <main className="public-category">
        <div className="public-empty-state">
          <strong>Yo‘nalish topilmadi</strong>
          <span>Katalogga qaytib, mavjud yo‘nalishni tanlang.</span>
        </div>
      </main>
    );
  }

  return (
    <main className="public-category">
      <section className="public-category__heading">
        <span
          className="public-category__icon"
          style={{ "--direction-color": direction.color } as CSSProperties}
          aria-hidden="true"
        >
          {direction.icon}
        </span>
        <div>
          <p className="public-section-eyebrow">Faoliyat turi</p>
          <h1>{direction.name}</h1>
          <p>{direction.activityTypes.length} ta faoliyat turidan birini tanlang.</p>
        </div>
      </section>

      <section className="public-category__types" aria-label="Faoliyat turlari">
        {direction.activityTypes.map((activityType) => (
          <button
            key={activityType}
            type="button"
            onClick={() => setSelectedActivity(activityType)}
          >
            <span>{activityType}</span>
            <span aria-hidden="true">→</span>
          </button>
        ))}
      </section>

      {selectedActivity ? (
        <section className="public-category__matches" aria-live="polite">
          <div className="public-catalog__result-heading">
            <h2>{selectedActivity}</h2>
            <span>Ochiq biznes profillari</span>
          </div>
          <PublicSearchResults
            items={items}
            loading={loading}
            error={error}
            emptyLabel="Bu faoliyat turi bo‘yicha ochiq profil topilmadi."
          />
          {catalogItems.length ? (
            <div className="public-catalog-items-grid">
              {catalogItems.map((item) => (
                <CatalogItemCard
                  authenticated={authenticated}
                  item={item}
                  key={item.public_id}
                  onBookQueue={onBookQueue}
                  onNeedQueueLogin={onNeedQueueLogin}
                  onOpenOwner={onOpenOwner}
                  onQueueMessage={onQueueMessage}
                />
              ))}
            </div>
          ) : null}
        </section>
      ) : null}
    </main>
  );
}
