import type { PublicCatalogItem } from "../../api/types";
import type { QueueBookingTarget } from "../../queues/QueueBookingV1656";


interface CatalogItemCardProps {
  item: PublicCatalogItem;
  authenticated?: boolean;
  onOpenOwner?(publicId: string): void;
  onNeedQueueLogin?(): void;
  onBookQueue?(target: QueueBookingTarget): void;
  onQueueMessage?(message: string): void;
}


export function CatalogItemCard({
  item,
  authenticated = false,
  onOpenOwner,
  onNeedQueueLogin,
  onBookQueue,
  onQueueMessage,
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
            onClick={() => {
              if (item.kind === "service" && item.queue_enabled) {
                if (Math.max(0, Number(item.queue_provider_count) || 0) < 1) {
                  onQueueMessage?.(item.direction === "Tibbiy xizmatlar"
                    ? "Shifokor hali biriktirilmagan."
                    : "Xizmat ko'rsatuvchi hali biriktirilmagan.");
                  return;
                }
                if (!authenticated) {
                  onNeedQueueLogin?.();
                  return;
                }
                onBookQueue?.({
                  businessPublicId: item.owner_public_id,
                  itemPublicId: item.public_id,
                  serviceName: item.name || "Xizmat",
                  direction: item.direction,
                });
                return;
              }
              onOpenOwner?.(item.owner_public_id);
            }}
          >
            {orderLabel}
          </button>
          <button type="button" disabled={!item.can_chat}>Chat</button>
        </div>
      </div>
    </article>
  );
}
