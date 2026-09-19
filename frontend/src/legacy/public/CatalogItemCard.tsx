import { useState } from "react";
import { CatalogItemActions, type CatalogItemCardProps } from "./CatalogItemActions";
import { CatalogItemDetails } from "./CatalogItemDetails";

export function CatalogItemCard(props: CatalogItemCardProps) {
  const { item, onOpenOwner } = props;
  const [opened, setOpened] = useState(false);
  const image = item.image_url || "/assets/catalog-placeholder.svg";
  const linkedOwner = item.owner_state === "linked" && item.owner_public_id;
  return (
    <>
      <article className="public-catalog-item">
        <button
          className="item-details-trigger"
          type="button"
          aria-label={`${item.name} haqida ma’lumot`}
          aria-haspopup="dialog"
          onClick={() => setOpened(true)}
        >
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
          </div>
        </button>
        <div className="public-catalog-item__body">
          {linkedOwner ? (
            <button
              className="public-catalog-item__owner"
              type="button"
              onClick={() => onOpenOwner?.(item.owner_public_id)}
            >
              {item.owner_label || item.owner_name}
            </button>
          ) : (
            <p className="public-catalog-item__warning">{item.owner_label}</p>
          )}
          <CatalogItemActions {...props} />
        </div>
      </article>
      {opened ? (
        <CatalogItemDetails {...props} onClose={() => setOpened(false)} />
      ) : null}
    </>
  );
}
