// `api/types.ts` dan ajratildi — domen bo'yicha.

export type ListingCategory =
  "uy" | "ish" | "moshina" | "hayvon" | "texnika" | "boshqa";

export type ListingMedia = {
  type: "photo" | "video";
  url: string;
};

export type ListingMediaAttachment = {
  type: "photo" | "video";
  object_key: string;
};

export type ListingRead = {
  public_id: string;
  cat: ListingCategory;
  title: string;
  price: string;
  descr: string;
  address: string;
  lat: number | null;
  lng: number | null;
  visibility: "all" | "own";
  // `payment_pending` — to'lov tasdiqlanmaguncha faqat egasi ko'radi.
  status: "active" | "inactive" | "payment_pending";
  created_at: string;
  media: ListingMedia[];
  owner_kind: "user" | "business";
  owner_public_id: string;
  owner_name: string;
  is_saved: boolean;
};

export type ListingCreate = {
  cat: ListingCategory;
  title: string;
  price: string;
  descr: string;
  address: string;
  lat: number;
  lng: number;
  visibility: "all" | "own";
  media: ListingMediaAttachment[];
};

export type ListingPatch = Partial<ListingCreate> & {
  status?: "active" | "inactive";
};
