import type { PublicCatalogItem } from "../../api/types";
import type { QueueBookingTarget } from "../../queues/QueueBooking";

export interface CatalogItemCardProps {
  item: PublicCatalogItem;
  authenticated?: boolean;
  onOpenOwner?(publicId: string): void;
  onNeedQueueLogin?(): void;
  onBookQueue?(target: QueueBookingTarget): void;
  onQueueMessage?(message: string): void;
}

export function CatalogItemActions({
  item,
  authenticated = false,
  onOpenOwner,
  onNeedQueueLogin,
  onBookQueue,
  onQueueMessage,
  showChat = true,
}: CatalogItemCardProps & { showChat?: boolean }) {
  const orderLabel =
    item.direction === "Ta'lim faoliyati"
      ? "Kursga yozilish"
      : item.kind === "service" && item.queue_enabled
        ? "Navbat olish"
        : "Buyurtma berish";

  return (
    <div className="public-catalog-item__actions">
      <button
        type="button"
        disabled={!item.can_order}
        onClick={() => {
          if (item.kind === "service" && item.queue_enabled) {
            if (Math.max(0, Number(item.queue_provider_count) || 0) < 1) {
              onQueueMessage?.(
                item.direction === "Tibbiy xizmatlar"
                  ? "Shifokor hali biriktirilmagan."
                  : "Xizmat ko'rsatuvchi hali biriktirilmagan.",
              );
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
      {showChat ? (
        <button type="button" disabled={!item.can_chat}>
          Chat
        </button>
      ) : null}
    </div>
  );
}
