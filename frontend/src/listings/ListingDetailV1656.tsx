import type { ListingRead } from "../api/types";
import { ListingMediaGridV1656 } from "./ListingMediaGridV1656";


type Props = {
  listing: ListingRead;
  onContact(): void;
  onSave(): void;
  saving?: boolean;
};


export function ListingDetailV1656({
  listing,
  onContact,
  onSave,
  saving = false,
}: Props) {
  return (
    <div className="el-detail">
      <ListingMediaGridV1656 media={listing.media} />
      <div className="el-price">{listing.price || "Narx kelishilgan"}</div>
      {listing.address ? <div className="el-addr">📍 {listing.address}</div> : null}
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
  );
}
