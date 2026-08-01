import { type FocusEvent, useState } from "react";

import type { PublicDistrictOffer } from "../../../api/types";


interface HomeDistrictOffersV1656Props {
  items: PublicDistrictOffer[];
  needsDistrict: boolean;
  onOpenLocation(): void;
  onOpenOffer(item: PublicDistrictOffer): void;
}


function kindLabel(kind: PublicDistrictOffer["kind"]) {
  if (kind === "listing") return "E’lon";
  if (kind === "service") return "Xizmat";
  return "Mahsulot";
}


function fallback(kind: PublicDistrictOffer["kind"]) {
  if (kind === "listing") return "📣";
  if (kind === "service") return "🧰";
  return "🛍️";
}


function OfferCard({
  duplicate = false,
  item,
  onOpenOffer,
}: {
  duplicate?: boolean;
  item: PublicDistrictOffer;
  onOpenOffer(item: PublicDistrictOffer): void;
}) {
  const image = item.image || item.business_logo;
  return (
    <button
      aria-hidden={duplicate || undefined}
      className="district-offer-card"
      tabIndex={duplicate ? -1 : undefined}
      type="button"
      onClick={() => onOpenOffer(item)}
    >
      <span className="district-offer-media">
        {image ? <img alt="" loading="lazy" src={image} /> : fallback(item.kind)}
      </span>
      <span className="district-offer-body">
        <span className="district-offer-title">{item.title || "Taklif"}</span>
        <span className="district-offer-business">{item.business_name}</span>
        <span
          className="district-offer-kind"
          data-district-kind-badge
        >
          {kindLabel(item.kind)}
        </span>
        {item.price ? (
          <span className="district-offer-price">
            {item.price}{item.unit ? ` / ${item.unit}` : ""}
          </span>
        ) : null}
      </span>
    </button>
  );
}


export function HomeDistrictOffersV1656({
  items,
  needsDistrict,
  onOpenLocation,
  onOpenOffer,
}: HomeDistrictOffersV1656Props) {
  const [paused, setPaused] = useState(false);
  const pauseProps = {
    className: `district-offers${paused ? " is-paused" : ""}`,
    onFocus: () => setPaused(true),
    onBlur: (event: FocusEvent<HTMLDivElement>) => {
      if (!event.relatedTarget || !event.currentTarget.contains(event.relatedTarget)) {
        setPaused(false);
      }
    },
    onPointerEnter: () => setPaused(true),
    onPointerLeave: () => setPaused(false),
    onTouchStart: () => setPaused(true),
    onTouchEnd: () => setPaused(false),
    onTouchCancel: () => setPaused(false),
  };
  if (needsDistrict) {
    return (
      <div
        {...pauseProps}
        id="districtOffersMount"
        aria-label="Hududiy takliflar"
      >
        <button
          className="district-select-btn"
          type="button"
          onClick={onOpenLocation}
        >
          Tumanni tanlang
        </button>
      </div>
    );
  }
  if (!items.length) {
    return (
      <div
        hidden
        id="districtOffersMount"
        aria-label="Hududiy takliflar"
      />
    );
  }

  const duplicate = items.length > 1;
  return (
    <div
      {...pauseProps}
      id="districtOffersMount"
      aria-label="Hududiy takliflar"
    >
      <div className="district-offers-viewport">
        <div className={`district-offers-track${duplicate ? "" : " is-static"}`}>
          {items.map((item) => (
            <OfferCard
              item={item}
              key={`${item.kind}:${item.content_public_id}`}
              onOpenOffer={onOpenOffer}
            />
          ))}
          {duplicate ? items.map((item) => (
            <OfferCard
              duplicate
              item={item}
              key={`duplicate:${item.kind}:${item.content_public_id}`}
              onOpenOffer={onOpenOffer}
            />
          )) : null}
        </div>
      </div>
    </div>
  );
}
