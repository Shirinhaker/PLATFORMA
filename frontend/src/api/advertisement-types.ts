/** Reklama joylash tiplari — reklama egasining kabineti uchun.
 *
 * `types.ts` oxiri public kontrakt sifatida tekshiriladi
 * (`test_phase3c_content_migration_contract`) va unda saqlash
 * kalitlari bo'lmasligi shart. Bu yerdagi maydonlar esa faqat egasiga
 * ko'rinadi — rasm grant orqali yuklanib, kaliti shu yerda uzatiladi.
 *
 * Backendda ham xuddi shunday ajratilgan: `authoring_schemas.py`.
 */

export type AdvertisementTarget = {
  level: "district" | "region" | "republic";
  region: string;
  district: string;
};

export type AdvertisementQuoteRequest = {
  targets: AdvertisementTarget[];
  duration_days: number;
  daily_all_day: boolean;
  daily_start: string;
  daily_end: string;
};

export type AdvertisementQuote = {
  district_count: number;
  hours_per_day: number;
  duration_days: number;
  district_hour_rate: number;
  billable_district_hours: number;
  total: number;
  currency: string;
};

export type AdvertisementRates = {
  price_code: string;
  district_hour_rate: number;
  duration_days: number[];
  currency: string;
  note: string;
};

export type AdvertisementCreate = AdvertisementQuoteRequest & {
  title: string;
  caption: string;
  desktop_image_object_key: string;
  mobile_image_object_key: string;
  crop_x: number;
  crop_y: number;
  crop_zoom: number;
  start_date: string;
  placement: string;
};

export type Advertisement = {
  id: number;
  title: string;
  caption: string;
  targets: AdvertisementTarget[];
  placement: string;
  status: string;
  daily_all_day: boolean;
  daily_start: string;
  daily_end: string;
  duration_days: number;
  district_count: number;
  hours_per_day: number;
  district_hour_rate: number;
  billable_district_hours: number;
  price: number;
  price_code: string;
  start_at: number;
  end_at: number;
  views: number;
  clicks: number;
  desktop_image_url: string;
  mobile_image_url: string;
  created_at: number;
};
