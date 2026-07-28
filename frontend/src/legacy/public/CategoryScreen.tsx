import { type CSSProperties, useState } from "react";

import { findCatalogDirection } from "./catalog-data";

interface CategoryScreenProps {
  categoryId: string;
}

export function CategoryScreen({ categoryId }: CategoryScreenProps) {
  const direction = findCatalogDirection(categoryId);
  const [selectedActivity, setSelectedActivity] = useState<string | null>(null);

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
        <p className="public-category__notice" role="status">
          {selectedActivity} natijalari keyingi migratsiya bosqichida ulanadi.
        </p>
      ) : null}
    </main>
  );
}
