// `api/types.ts` dan ajratildi — domen bo'yicha.

export type SpecialistCredential = {
  id: number;
  image_url: string;
  position: number;
  created_at: string;
};

export type SpecialistOffer = {
  id: number;
  kind: "service" | "product";
  name: string;
  price_text: string;
  note: string;
  image_url: string;
  image_object_key: string;
  created_at: string;
};

export type SpecialistPortfolio = {
  id: number;
  media_type: "photo" | "video";
  media_url: string;
  created_at: string;
};

export type SpecialistProfile = {
  exists: boolean;
  profession: string;
  description: string;
  visible: boolean;
  latitude: number | null;
  longitude: number | null;
  review_count: number;
  credentials: SpecialistCredential[];
  offers: SpecialistOffer[];
  portfolio: SpecialistPortfolio[];
};

export type SpecialistProfileWrite = Pick<
  SpecialistProfile,
  "profession" | "description" | "visible" | "latitude" | "longitude"
>;

export type SpecialistOfferWrite = {
  kind: "service" | "product";
  name: string;
  price_text: string;
  note: string;
  image_object_key: string;
  clear_image: boolean;
};
