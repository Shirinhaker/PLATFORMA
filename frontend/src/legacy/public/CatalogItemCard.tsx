import type { PublicCatalogItem } from "../../api/types";


interface CatalogItemCardProps {
  item: PublicCatalogItem;
  onOpenOwner?(publicId: string): void;
}


export function CatalogItemCard({
  item,
  onOpenOwner,
}: CatalogItemCardProps) {
  const image = item.image_url || "/assets/catalog-placeholder.svg";
  const linkedOwner = item.owner_state === "linked" && item.owner_public_id;
  const orderLabel = item.direction === "Ta'lim faoliyati"
    ? "Kursga yozilish"
    : item.kind === "service" && item.queue_enabled
      ? "Navbat olish"
      : "Buyurtma berish";

  return (
    <article className="public-catalog-item">
      <img
        className="public-catalog-item__image"
        src={image}
        alt={item.name}
        loading="lazy"
      />
      <div className="public-catalog-item__body">
        <span className="public-catalog-item__kind">
          {item.kind === "product" ? "Mahsulot" : "Xizmat"}
        </span>
        <h3>{item.name}</h3>
        {item.price_text ? <strong>{item.price_text}</strong> : null}
        {item.note ? <p>{item.note}</p> : null}
        {linkedOwner ? (
          <button
            className="public-catalog-item__owner"
            type="button"
            onClick={() => onOpenOwner?.(item.owner_public_id)}
          >
            {item.owner_label || item.owner_name}
          </button>
        ) : (
          <p className="public-catalog-item__warning">
            {item.owner_label}
          </p>
        )}
        <div className="public-catalog-item__actions">
          <button
            type="button"
            disabled={!item.can_order}
            onClick={() => onOpenOwner?.(item.owner_public_id)}
          >
            {orderLabel}
          </button>
          <button type="button" disabled={!item.can_chat}>Chat</button>
        </div>
      </div>
    </article>
  );
}
