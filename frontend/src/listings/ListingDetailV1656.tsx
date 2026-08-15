import type { ListingRead } from "../api/types";
import { ListingMediaGridV1656 } from "./ListingMediaGridV1656";


type Props = {
  listing: ListingRead;
  onContact(): void;
  onSave(): void;
  saving?: boolean;
  compactMedia?: boolean;
};


export function ListingDetailV1656({
  listing,
  onContact,
  onSave,
  saving = false,
  compactMedia = false,
}: Props) {
  const hasLocation = Boolean(listing.address) || (listing.lat != null && listing.lng != null);

  return (
    <div className="el-detail">
      <ListingMediaGridV1656 compact={compactMedia} media={listing.media} />
      <div className="el-detail-info">
        <div className="el-price">{listing.price || "Narx kelishilgan"}</div>
        {hasLocation ? (
          <div className="el-location" aria-label="Xarita manzili">
            <span className="el-location-icon" aria-hidden="true">📍</span>
            <span>
              <strong>Xarita manzili</strong>
              {listing.address ? <span className="el-addr">{listing.address}</span> : null}
              {listing.lat != null && listing.lng != null ? (
                <span className="el-coordinates">
                  {listing.lat.toFixed(5)}, {listing.lng.toFixed(5)}
                </span>
              ) : null}
            </span>
          </div>
        ) : null}
        {listing.descr ? <div className="el-desc">{listing.descr}</div> : null}
        <div className="el-actions">
          <button className="btn btn-primary" type="button" onClick={onContact}>
            Bog&apos;lanish
          </button>
          <button
            className={`btn ${listing.is_saved ? "btn-soft" : "btn-outline"}`}
            disabled={saving}
            type="button"
            onClick={onSave}
          >
            {listing.is_saved ? "✓ Saqlangan" : "🔖 Saqlash"}
          </button>
        </div>
      </div>
    </div>
  );
}
