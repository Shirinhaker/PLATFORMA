import { useCallback, useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type { BusinessOnlineRecord } from "../api/business-online-types";
import type { Advertisement, AdvertisementTarget } from "../api/types";
import { CrudEditorView } from "../profiles/BusinessOnlineCrudEditorView";
import type { PaymentTarget } from "../profiles/PaymentRequestModal";


export type BusinessAdvertisementsApi = Pick<
  ApiClient,
  | "getMyAdvertisements"
  | "createAdvertisement"
  | "deleteAdvertisement"
  | "quoteAdvertisement"
  | "createUploadGrant"
  | "uploadGrantedFile"
>;

const METHODS: ReadonlyArray<keyof BusinessAdvertisementsApi> = [
  "getMyAdvertisements",
  "createAdvertisement",
  "deleteAdvertisement",
  "quoteAdvertisement",
  "createUploadGrant",
  "uploadGrantedFile",
];

export function supportsAdvertisementApi(
  api: object,
): api is BusinessAdvertisementsApi {
  return METHODS.every((method) => (
    typeof (api as Partial<BusinessAdvertisementsApi>)[method] === "function"
  ));
}

type Props = {
  api: BusinessAdvertisementsApi;
  /** To'lov oynasini ochadi; reklama tasdiqlangach faol bo'ladi. */
  openPayment: (target: PaymentTarget) => void;
};


function text(value: unknown, fallback = "") {
  return typeof value === "string" && value ? value : fallback;
}

function number(value: unknown, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function targetsOf(raw: unknown): AdvertisementTarget[] {
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((item) => {
    const value = item as Record<string, unknown>;
    const level = text(value.level);
    if (level !== "district" && level !== "region" && level !== "republic") {
      return [];
    }
    return [{
      level,
      region: text(value.region),
      district: text(value.district),
    }];
  });
}

/** Serverdagi reklamani eski ekran kutgan yozuv shakliga o'giradi. */
function record(row: Advertisement): BusinessOnlineRecord {
  return {
    id: row.id,
    title: row.title,
    caption: row.caption,
    targets: row.targets,
    status: row.status,
    placement: row.placement,
    daily_all_day: row.daily_all_day ? 1 : 0,
    daily_start: row.daily_start,
    daily_end: row.daily_end,
    duration_days: row.duration_days,
    district_count: row.district_count,
    hours_per_day: row.hours_per_day,
    district_hour_rate: row.district_hour_rate,
    billable_district_hours: row.billable_district_hours,
    price: row.price,
    price_code: row.price_code,
    start_at: row.start_at,
    end_at: row.end_at,
    views: row.views,
    clicks: row.clicks,
    image_url: row.desktop_image_url,
    image_file: row.desktop_image_url,
    mobile_image_file: row.mobile_image_url,
  } as unknown as BusinessOnlineRecord;
}


export function BusinessAdvertisementsV1656({ api, openPayment }: Props) {
  const [rows, setRows] = useState<Advertisement[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setRows(await api.getMyAdvertisements());
      setError("");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Reklamalar yuklanmadi.",
      );
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!error) return;
    const timeout = window.setTimeout(() => setError(""), 3000);
    return () => window.clearTimeout(timeout);
  }, [error]);

  async function uploadImage(file: File) {
    const grant = await api.createUploadGrant({
      purpose: "advertisement_image",
      filename: file.name,
      content_type: file.type,
      size_bytes: file.size,
    });
    await api.uploadGrantedFile(grant, file);
    return grant.object_key;
  }

  async function create(
    _resource: unknown,
    draft: BusinessOnlineRecord,
  ): Promise<void> {
    setBusy(true);
    setError("");
    try {
      const created = await api.createAdvertisement({
        title: text(draft.title).trim(),
        caption: text(draft.caption).trim(),
        targets: targetsOf(draft.targets),
        duration_days: Math.max(1, Math.trunc(number(draft.duration_days, 1))),
        daily_all_day: Boolean(number(draft.daily_all_day, 1)),
        daily_start: text(draft.daily_start, "00:00"),
        daily_end: text(draft.daily_end, "00:00"),
        start_date: text(draft.start_date),
        desktop_image_object_key: text(draft.image_file_key),
        mobile_image_object_key: text(draft.mobile_image_file_key),
        crop_x: number(draft.crop_x, 50),
        crop_y: number(draft.crop_y, 50),
        crop_zoom: number(draft.crop_zoom, 1),
        placement: text(draft.placement, "home"),
      });
      setRows((current) => [created, ...current]);
      // v1656: reklama to'lovsiz ko'rinmaydi, shuning uchun darhol
      // to'lov oynasi ochiladi.
      openPayment(paymentTarget(created));
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Reklama saqlanmadi.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function remove(
    _resource: unknown,
    id: number | string,
  ): Promise<void> {
    setBusy(true);
    try {
      await api.deleteAdvertisement(Number(id));
      setRows((current) => current.filter(
        (row) => String(row.id) !== String(id),
      ));
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Reklama o‘chirilmadi.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function quote(request: BusinessOnlineRecord) {
    const value = await api.quoteAdvertisement({
      targets: targetsOf(request.targets),
      duration_days: Math.max(1, Math.trunc(number(request.duration_days, 1))),
      daily_all_day: Boolean(number(request.daily_all_day, 1)),
      daily_start: text(request.daily_start, "00:00"),
      daily_end: text(request.daily_end, "00:00"),
    });
    return value as unknown as BusinessOnlineRecord;
  }

  return (
    <>
      {error ? (
        <div className="advertisement-load-error" role="status">{error}</div>
      ) : null}
      <CrudEditorView
        resource="advertisements"
        rows={rows.map(record)}
        addLabel="+ Reklama"
        empty="Hozircha reklama yo‘q."
        fields={[
          "title", "caption", "placement",
          "region", "district", "start_at", "end_at",
        ]}
        busy={busy}
        form=""
        draft={{}}
        setForm={() => undefined}
        setDraft={() => undefined}
        create={create}
        patch={async () => undefined}
        remove={remove}
        action={async () => undefined}
        quoteAdvertisement={quote}
        uploadImage={uploadImage}
        rowAction={(row) => (
          text(row.status) === "payment_pending" ? (
            <button
              type="button"
              className="mini-btn advertisement-pay"
              onClick={() => {
                const found = rows.find(
                  (item) => String(item.id) === String(row.id),
                );
                if (found) openPayment(paymentTarget(found));
              }}
            >
              To‘lov qilish
            </button>
          ) : null
        )}
      />
    </>
  );
}


export function paymentTarget(row: Advertisement): PaymentTarget {
  return {
    serviceType: "advertisement",
    priceCode: row.price_code || "advertisement_district_hour",
    label: `Reklama · ${row.district_count} tuman · ${row.duration_days} kun`,
    quantity: row.billable_district_hours,
    targetId: row.id,
  };
}
