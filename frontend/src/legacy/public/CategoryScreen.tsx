import {
  type CSSProperties,
  useEffect,
  useState,
} from "react";

import type { ApiClient } from "../../api/client";
import type { PublicSearchItem } from "../../api/types";
import { findCatalogDirection } from "./catalog-data";
import { PublicSearchResults } from "./PublicSearchResults";

interface CategoryScreenProps {
  categoryId: string;
  searchPublic?: ApiClient["searchPublic"];
}

export function CategoryScreen({
  categoryId,
  searchPublic,
}: CategoryScreenProps) {
  const direction = findCatalogDirection(categoryId);
  const [selectedActivity, setSelectedActivity] = useState<string | null>(null);
  const [items, setItems] = useState<PublicSearchItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!direction || !selectedActivity) return;
    if (!searchPublic) {
      setError("Qidiruv xizmati hozircha ulanmagan.");
      return;
    }

    let active = true;
    setItems([]);
    setLoading(true);
    setError("");
    searchPublic({
      result_type: "business",
      direction: direction.name,
      activity_type: selectedActivity,
      page: 1,
      page_size: 20,
    })
      .then((response) => {
        if (active) setItems(response.items);
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
  }, [direction, searchPublic, selectedActivity]);

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
        </section>
      ) : null}
    </main>
  );
}
