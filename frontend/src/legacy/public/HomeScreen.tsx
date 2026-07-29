import { type FormEvent, useState } from "react";
import type { ApiClient } from "../../api/client";
import { HomeAdvertisements } from "./HomeAdvertisements";
import type { HomeLocation } from "./location-storage";

interface HomeScreenProps {
  currentDistrict?: string;
  getAdvertisements?: ApiClient["getAdvertisements"];
  location?: HomeLocation | null;
  onSearch(query: string): void;
  onOpenCatalog(): void;
  onOpenLocation(): void;
}

function SearchIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16 16 4 4" />
    </svg>
  );
}

function LocationArtwork() {
  return (
    <svg
      aria-hidden="true"
      className="public-home__location-art"
      viewBox="0 0 320 210"
    >
      <path d="M18 174 80 83l46 52 50-97 126 136Z" />
      <path d="M29 174h262" />
      <path d="M160 45c-27 0-49 22-49 49 0 35 49 86 49 86s49-51 49-86c0-27-22-49-49-49Z" />
      <circle cx="160" cy="94" r="17" />
    </svg>
  );
}

export function HomeScreen({
  currentDistrict,
  getAdvertisements,
  location = null,
  onSearch,
  onOpenCatalog,
  onOpenLocation,
}: HomeScreenProps) {
  const [query, setQuery] = useState("");
  const district = currentDistrict?.trim() || "Hudud tanlanmagan";

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedQuery = query.trim();

    if (normalizedQuery) {
      onSearch(normalizedQuery);
    }
  }

  return (
    <main className="public-home">
      <section className="public-home__hero" aria-labelledby="home-title">
        <div className="public-home__intro">
          <p className="public-home__eyebrow">Koprik — yaqin va ishonchli</p>
          <h1 id="home-title">
            Kerakli mahsulot va xizmatni yaqiningizdan toping
          </h1>
          <p className="public-home__lead">
            Mahalliy biznes, mutaxassis va xizmatlarni bitta joydan izlang.
          </p>

          <form className="public-home__search" onSubmit={submitSearch}>
            <label htmlFor="public-home-query">Qidiruv</label>
            <div className="public-home__search-row">
              <span className="public-home__search-icon">
                <SearchIcon />
              </span>
              <input
                id="public-home-query"
                type="search"
                value={query}
                placeholder="Nima qidiryapsiz?"
                onChange={(event) => setQuery(event.currentTarget.value)}
              />
              <button type="submit">Qidirish</button>
            </div>
          </form>

          <button
            className="public-home__catalog-link"
            type="button"
            onClick={onOpenCatalog}
          >
            <span>Katalog bo‘yicha</span>
            <span aria-hidden="true">→</span>
          </button>
        </div>

        <aside className="public-home__discovery" aria-label="Hudud bo‘yicha qidiruv">
          <LocationArtwork />
          <div>
            <p className="public-home__location-label">Hozirgi hudud</p>
            <h2>{district}</h2>
            <p>
              Yaqin natijalarni aniqroq ko‘rish uchun shahar yoki tumanni
              tanlang.
            </p>
            <button type="button" onClick={onOpenLocation}>
              Manzilni tanlash
            </button>
          </div>
        </aside>
      </section>

      {getAdvertisements ? (
        <HomeAdvertisements
          getAdvertisements={getAdvertisements}
          location={location}
        />
      ) : null}

      <section className="public-home__trust" aria-label="Koprik afzalliklari">
        <div>
          <strong>Mahalliy</strong>
          <span>Yaqiningizdagi takliflarni toping</span>
        </div>
        <div>
          <strong>Tartibli</strong>
          <span>Yo‘nalish va faoliyat turi bo‘yicha izlang</span>
        </div>
        <div>
          <strong>Ochiq</strong>
          <span>Profil ma’lumotlarini bir joyda ko‘ring</span>
        </div>
      </section>
    </main>
  );
}
