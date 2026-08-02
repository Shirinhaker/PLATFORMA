import {
  type CSSProperties,
  useEffect,
  useMemo,
  useState,
} from "react";

import type { ApiClient } from "../../api/client";
import type {
  PublicCatalogItem,
  PublicSearchItem,
  PublicResultType,
} from "../../api/types";
import { searchCatalogDirections } from "./catalog-data";
import { CatalogItemCard } from "./CatalogItemCard";
import type { HomeLocation } from "./location-storage";
import { PublicSearchResults } from "./PublicSearchResults";

interface CatalogScreenProps {
  initialQuery: string;
  location?: HomeLocation | null;
  searchPublic?: ApiClient["searchPublic"];
  getCatalogItems?: ApiClient["getCatalogItems"];
  onOpenCategory(categoryId: string): void;
  onOpenOwner?(publicId: string): void;
}

const SEARCH_TYPES = [
  "Barchasi",
  "Mahsulot",
  "Xizmat",
  "Biznes",
  "Mutaxassis",
  "Foydalanuvchi",
] as const;

const SEARCH_SCOPES = ["Mahalla", "Tuman", "Viloyat", "Respublika"] as const;
function resultType(
  searchType: (typeof SEARCH_TYPES)[number],
): PublicResultType {
  if (searchType === "Biznes") return "business";
  if (searchType === "Mahsulot") return "product";
  if (searchType === "Xizmat") return "service";
  if (searchType === "Mutaxassis" || searchType === "Foydalanuvchi") {
    return "user";
  }
  return "all";
}

export function CatalogScreen({
  initialQuery,
  location = null,
  searchPublic,
  getCatalogItems,
  onOpenCategory,
  onOpenOwner,
}: CatalogScreenProps) {
  const [query, setQuery] = useState(initialQuery);
  const [searchType, setSearchType] = useState<(typeof SEARCH_TYPES)[number]>(
    "Barchasi",
  );
  const [scope, setScope] = useState<(typeof SEARCH_SCOPES)[number]>("Tuman");
  const [items, setItems] = useState<PublicSearchItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(Boolean(searchPublic));
  const [error, setError] = useState(searchPublic
    ? ""
    : "Qidiruv xizmati hozircha ulanmagan.");
  const directions = useMemo(() => searchCatalogDirections(query), [query]);
  const [catalogItems, setCatalogItems] = useState<PublicCatalogItem[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(Boolean(getCatalogItems));
  const [catalogError, setCatalogError] = useState("");

  useEffect(() => {
    if (!searchPublic) {
      setItems([]);
      setTotal(0);
      setLoading(false);
      setError("Qidiruv xizmati hozircha ulanmagan.");
      return;
    }

    let active = true;
    setLoading(true);
    setError("");
    const timer = window.setTimeout(() => {
      const filters = {
        q: query.trim(),
        result_type: resultType(searchType),
        page: 1,
        page_size: 20,
        ...(scope === "Mahalla" && location?.neighborhood
          ? { mahalla: location.neighborhood }
          : {}),
        ...(scope === "Tuman" && location?.district
          ? { district: location.district }
          : {}),
        ...(scope === "Viloyat" && location?.region
          ? { region: location.region }
          : {}),
      };
      searchPublic(filters)
        .then((response) => {
          if (!active) return;
          setItems(response.items);
          setTotal(response.total);
        })
        .catch(() => {
          if (!active) return;
          setItems([]);
          setTotal(0);
          setError("Server bilan bog‘lanib bo‘lmadi. Qayta urinib ko‘ring.");
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }, 250);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [location, query, scope, searchPublic, searchType]);

  useEffect(() => {
    if (!getCatalogItems) {
      setCatalogLoading(false);
      return;
    }
    let active = true;
    setCatalogLoading(true);
    setCatalogError("");
    getCatalogItems({
      q: query.trim(),
      ...(searchType === "Mahsulot" ? { kind: "product" as const } : {}),
      ...(searchType === "Xizmat" ? { kind: "service" as const } : {}),
      ...(scope === "Mahalla" && location?.neighborhood
        ? { mahalla: location.neighborhood }
        : {}),
      ...(scope === "Tuman" && location?.district
        ? { district: location.district }
        : {}),
      ...(scope === "Viloyat" && location?.region
        ? { region: location.region }
        : {}),
      page: 1,
      page_size: 20,
    })
      .then((response) => {
        if (active) setCatalogItems(response.items);
      })
      .catch(() => {
        if (active) setCatalogError("Katalogni yuklab bo‘lmadi.");
      })
      .finally(() => {
        if (active) setCatalogLoading(false);
      });
    return () => {
      active = false;
    };
  }, [getCatalogItems, location, query, scope, searchType]);

  return (
    <main className="public-catalog">
      <section className="public-catalog__heading">
        <p className="public-section-eyebrow">Koprik katalogi</p>
        <h1>Faoliyat yo‘nalishlari</h1>
        <p>
          Mahsulot, xizmat, biznes yoki mutaxassisni yo‘nalish bo‘yicha toping.
        </p>
      </section>

      <section className="public-catalog__filters" aria-label="Qidiruv filtrlari">
        <label htmlFor="catalog-query">Qidiruv</label>
        <input
          id="catalog-query"
          type="search"
          value={query}
          placeholder="Nima qidiryapsiz?"
          onChange={(event) => setQuery(event.currentTarget.value)}
        />

        <div className="public-catalog__filter-group">
          <span>Qidiruv turi</span>
          <div>
            {SEARCH_TYPES.map((label) => (
              <button
                aria-pressed={searchType === label}
                key={label}
                type="button"
                onClick={() => setSearchType(label)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="public-catalog__filter-group">
          <span>Qidiruv hududi</span>
          <div>
            {SEARCH_SCOPES.map((label) => (
              <button
                aria-pressed={scope === label}
                key={label}
                type="button"
                onClick={() => setScope(label)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </section>

      {getCatalogItems ? (
        <section className="public-catalog__items" aria-live="polite">
          <div className="public-catalog__result-heading">
            <h2>Mahsulot va xizmatlar</h2>
            <span>{catalogLoading ? "Yuklanmoqda" : `${catalogItems.length} ta`}</span>
          </div>
          {catalogError ? (
            <div className="public-search-status" role="alert">
              {catalogError}
            </div>
          ) : (
            <div className="public-catalog-items-grid">
              {catalogItems.map((item) => (
                <CatalogItemCard item={item} key={item.public_id} onOpenOwner={onOpenOwner} />
              ))}
            </div>
          )}
        </section>
      ) : null}

      <section className="public-catalog__profiles" aria-live="polite">
        <div className="public-catalog__result-heading">
          <h2>Ochiq profillar</h2>
          <span>{loading ? "Yuklanmoqda" : `${total} ta natija`}</span>
        </div>
        <PublicSearchResults
          items={items}
          loading={loading}
          error={error}
          emptyLabel="Qidiruv yoki hudud filtrini o‘zgartirib ko‘ring."
        />
      </section>

      <section className="public-catalog__results" aria-live="polite">
        <div className="public-catalog__result-heading">
          <h2>{directions.length} ta yo‘nalish</h2>
          <span>
            {searchType} · {scope}
          </span>
        </div>

        {directions.length ? (
          <div className="public-catalog__grid">
            {directions.map((direction) => (
              <button
                aria-label={`${direction.name} — ${direction.activityTypes
                  .slice(0, 3)
                  .join(", ")}`}
                className="public-catalog__card"
                key={direction.id}
                style={{ "--direction-color": direction.color } as CSSProperties}
                type="button"
                onClick={() => onOpenCategory(direction.id)}
              >
                <span className="public-catalog__icon" aria-hidden="true">
                  {direction.icon}
                </span>
                <span>
                  <strong>{direction.name}</strong>
                  <small>{direction.activityTypes.length} ta faoliyat turi</small>
                </span>
                <span aria-hidden="true">→</span>
              </button>
            ))}
          </div>
        ) : (
          <div className="public-empty-state">
            <strong>Yo‘nalish topilmadi</strong>
            <span>Boshqa so‘z bilan qayta qidiring.</span>
          </div>
        )}
      </section>
    </main>
  );
}
