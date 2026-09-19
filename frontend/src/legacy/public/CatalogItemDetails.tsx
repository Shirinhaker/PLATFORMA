import { CatalogItemActions, type CatalogItemCardProps } from "./CatalogItemActions";
import { ItemDetailsDialog } from "./ItemDetailsDialog";

export function CatalogItemDetails({
  onClose,
  ...props
}: CatalogItemCardProps & { onClose(): void }) {
  const { item, onOpenOwner } = props;
  const linked = item.owner_state === "linked" && item.owner_public_id;
  return (
    <ItemDetailsDialog item={item} onClose={onClose}>
      {linked ? (
        <button
          className="btn btn-soft"
          type="button"
          onClick={() => {
            onClose();
            onOpenOwner?.(item.owner_public_id);
          }}
        >
          {item.owner_label || item.owner_name || "Biznes profilini ochish"}
        </button>
      ) : (
        <p>{item.owner_label}</p>
      )}
      <div
        onClickCapture={(event) => {
          const target = event.target as HTMLElement;
          if (target.closest("button:not(:disabled)")) onClose();
        }}
      >
        <CatalogItemActions {...props} showChat={false} />
      </div>
    </ItemDetailsDialog>
  );
}
