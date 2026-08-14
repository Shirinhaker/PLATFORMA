import { useState } from "react";

import type { ListingMedia } from "../api/types";
import { ListingMediaViewerV1656 } from "./ListingMediaViewerV1656";


export function ListingMediaGridV1656({ media }: { media: ListingMedia[] }) {
  const [openedMedia, setOpenedMedia] = useState<ListingMedia | null>(null);

  if (!media.length) return null;

  return (
    <>
      <div className={`listing-media-grid${media.length === 1 ? " is-single" : ""}`}>
        {media.map((item, index) => (
          <button
            aria-label={item.type === "video" ? "Videoni katta ko‘rish" : "Rasmni katta ko‘rish"}
            className="listing-media-card"
            key={`${item.type}:${item.url}:${index}`}
            type="button"
            onClick={() => setOpenedMedia(item)}
          >
            {item.type === "video" ? (
              <video className="listing-media-visual" muted playsInline preload="metadata" src={item.url} />
            ) : (
              <img alt="E'lon rasmi" className="listing-media-visual" loading="lazy" src={item.url} />
            )}
            {item.type === "video" ? <span className="listing-media-play">▶</span> : null}
            <span className="listing-media-open">⛶ Kattalashtirish</span>
          </button>
        ))}
      </div>
      <ListingMediaViewerV1656
        media={openedMedia}
        onClose={() => setOpenedMedia(null)}
      />
    </>
  );
}
