import type { PublicSearchItem } from "../../api/types";


interface PublicSearchResultsProps {
  items: PublicSearchItem[];
  loading: boolean;
  error: string;
  emptyLabel?: string;
}

function resultLocation(item: PublicSearchItem) {
  return [item.mahalla, item.district, item.region]
    .filter(Boolean)
    .join(" · ");
}

export function PublicSearchResults({
  items,
  loading,
  error,
  emptyLabel = "Mos ochiq profil topilmadi.",
}: PublicSearchResultsProps) {
  if (loading) {
    return (
      <div className="public-search-status" role="status">
        Natijalar yuklanmoqda…
      </div>
    );
  }

  if (error) {
    return (
      <div className="public-search-status public-search-status--error" role="alert">
        <strong>Profil natijalarini yuklab bo‘lmadi</strong>
        <span>{error}</span>
      </div>
    );
  }

  if (!items.length) {
    return (
      <div className="public-empty-state">
        <strong>Natija topilmadi</strong>
        <span>{emptyLabel}</span>
      </div>
    );
  }

  return (
    <div className="public-search-grid">
      {items.map((item) => {
        const content = item.kind === "product" || item.kind === "service";
        const location = resultLocation(item);
        const secondary = item.kind === "business"
          ? [item.direction, item.activity_type].filter(Boolean).join(" · ")
          : content ? item.price_text || "" : location;

        return (
          <article className="public-search-card" key={item.public_id}>
            <div className="public-search-card__avatar" aria-hidden="true">
              {item.image_url ? (
                <img src={item.image_url} alt="" />
              ) : item.name.slice(0, 1).toLocaleUpperCase("uz")
              }
            </div>
            <div className="public-search-card__body">
              <div className="public-search-card__topline">
                <span>
                  {item.kind === "business"
                    ? "Biznes"
                    : item.kind === "product"
                      ? "Mahsulot"
                      : item.kind === "service"
                        ? "Xizmat"
                        : "Foydalanuvchi"}
                </span>
                {item.public_username ? (
                  <small>@{item.public_username}</small>
                ) : null}
              </div>
              <h3>{item.name}</h3>
              {secondary ? <p>{secondary}</p> : null}
              {item.kind === "business" && location ? (
                <p className="public-search-card__location">{location}</p>
              ) : null}
              {item.description ? (
                <p className="public-search-card__description">
                  {item.description}
                </p>
              ) : null}
              {content && item.owner_label ? (
                <p className={item.owner_state === "unlinked"
                  ? "public-search-card__warning"
                  : undefined}
                >
                  {item.owner_label}
                </p>
              ) : null}
            </div>
          </article>
        );
      })}
    </div>
  );
}
