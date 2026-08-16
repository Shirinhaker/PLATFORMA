// `BusinessOnlineCrudEditorView.tsx` dan ajratildi.
import { useEffect, useRef, useState, type ReactNode } from "react";

import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../../api/business-online-types";
import { UZBEKISTAN_REGIONS } from "../../legacy/public/location-data";
import { readHomeLocation } from "../../legacy/public/location-storage";
import {
  BusinessLocationPickerView,
  normalizeLatLng,
} from "../BusinessLocationPickerView";
import {
  recordId,
  recordNumber,
  recordText,
  type SharedActions,
} from "../BusinessOnlineViews";
import { v1656Money } from "./shared";

export function AdvertisementForm({
  draft,
  setDraft,
  busy,
  error,
  quoteAdvertisement,
  uploadImage,
  save,
  cancel,
}: {
  draft: BusinessOnlineRecord;
  setDraft: (row: BusinessOnlineRecord) => void;
  busy: boolean;
  error: string;
  quoteAdvertisement?: (
    request: BusinessOnlineRecord,
  ) => Promise<BusinessOnlineRecord | null | void>;
  /** Berilsa rasm R2'ga yuklanib, obyekt kaliti draftga yoziladi. */
  uploadImage?: (file: File) => Promise<string>;
  save: () => Promise<void>;
  cancel: () => void;
}) {
  const desktopInput = useRef<HTMLInputElement | null>(null);
  const mobileInput = useRef<HTMLInputElement | null>(null);
  const [fileError, setFileError] = useState("");
  const [quoteError, setQuoteError] = useState("");
  const [quote, setQuote] = useState<BusinessOnlineRecord | null>(null);
  const quoteAdvertisementRef = useRef(quoteAdvertisement);
  quoteAdvertisementRef.current = quoteAdvertisement;
  const targets = Array.isArray(draft.targets)
    ? draft.targets.filter((target): target is BusinessOnlineRecord =>
        Boolean(target && typeof target === "object"),
      )
    : [];
  const level = recordText(draft, "target_level") || "district";
  const selectedRegion =
    recordText(draft, "target_region") || UZBEKISTAN_REGIONS[0]?.name || "";
  const districts =
    UZBEKISTAN_REGIONS.find((region) => region.name === selectedRegion)?.districts ??
    [];
  const selectedDistrict = districts.includes(recordText(draft, "target_district"))
    ? recordText(draft, "target_district")
    : (districts[0] ?? "");
  const hours = Array.from(
    { length: 24 },
    (_, hour) => String(hour).padStart(2, "0") + ":00",
  );
  const targetsKey = JSON.stringify(targets);
  const durationDays = Number(draft.duration_days ?? 1);
  const dailyAllDay = Boolean(draft.daily_all_day);
  const dailyStart = recordText(draft, "daily_start");
  const dailyEnd = recordText(draft, "daily_end");

  useEffect(() => {
    let current = true;
    if (
      !targets.length ||
      !quoteAdvertisementRef.current ||
      (!dailyAllDay && (!dailyStart || !dailyEnd))
    ) {
      setQuote(null);
      setQuoteError("");
      return () => {
        current = false;
      };
    }
    setQuoteError("");
    void quoteAdvertisementRef
      .current({
        targets,
        duration_days: durationDays,
        daily_all_day: dailyAllDay,
        daily_start: dailyAllDay ? "00:00" : dailyStart,
        daily_end: dailyAllDay ? "00:00" : dailyEnd,
      })
      .then((value) => {
        if (current && value) setQuote(value);
      })
      .catch((reason: unknown) => {
        if (!current) return;
        setQuote(null);
        setQuoteError(
          reason instanceof Error ? reason.message : "Reklama narxi hisoblanmadi.",
        );
      });
    return () => {
      current = false;
    };
  }, [targetsKey, durationDays, dailyAllDay, dailyStart, dailyEnd]);

  async function selectImage(
    file: File | undefined,
    key: "image_file" | "mobile_image_file",
  ) {
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      setFileError("Faqat JPG, PNG yoki WEBP rasm tanlang.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setFileError("Rasm hajmi 5 MB dan oshmasin.");
      return;
    }
    setFileError("");
    if (!uploadImage) {
      // Eski JSON yo'li: faqat nom saqlanadi.
      setDraft({ ...draft, [key]: file.name });
      return;
    }
    setFileError("Rasm yuklanmoqda...");
    try {
      const objectKey = await uploadImage(file);
      setFileError("");
      setDraft({ ...draft, [key]: file.name, [`${key}_key`]: objectKey });
    } catch (reason) {
      setFileError(reason instanceof Error ? reason.message : "Rasm yuklanmadi.");
    }
  }

  function targetLabel(target: BusinessOnlineRecord) {
    if (target.level === "republic") return "🇺🇿 Respublika";
    if (target.level === "region") return `Viloyat: ${recordText(target, "region")}`;
    return `${recordText(target, "region")} · ${recordText(target, "district")}`;
  }

  return (
    <div className="form-wrap advertisement-form-v1656">
      <div className="ad-quality">
        <b>Rasm talabi:</b> kompyuter uchun 2744 × 368 px (7.46:1), telefon uchun 800 ×
        250 px (3.2:1) tavsiya etiladi. JPG, PNG yoki WEBP; har biri 5 MB gacha.
      </div>
      <div className="field">
        <label>Kompyuter uchun rasm — majburiy</label>
        <input
          ref={desktopInput}
          type="file"
          hidden
          accept="image/jpeg,image/png,image/webp"
          aria-label="Kompyuter uchun rasm"
          onChange={(event) =>
            void selectImage(event.currentTarget.files?.[0], "image_file")
          }
        />
        <button
          type="button"
          className="upload"
          onClick={() => desktopInput.current?.click()}
        >
          {recordText(draft, "image_file")
            ? "Rasm tanlandi ✅"
            : "🖼 Galereyadan rasm tanlash"}
        </button>
      </div>
      <div className="field">
        <label>Telefon uchun rasm — ixtiyoriy</label>
        <input
          ref={mobileInput}
          type="file"
          hidden
          accept="image/jpeg,image/png,image/webp"
          aria-label="Telefon uchun rasm"
          onChange={(event) =>
            void selectImage(event.currentTarget.files?.[0], "mobile_image_file")
          }
        />
        <button
          type="button"
          className="upload"
          onClick={() => mobileInput.current?.click()}
        >
          {recordText(draft, "mobile_image_file")
            ? "Telefon rasmi tanlandi ✅"
            : "📱 Telefon rasmini tanlash"}
        </button>
        <div className="idesc">Yuklanmasa, telefonda kompyuter rasmi ko‘rsatiladi.</div>
      </div>
      <label className="field">
        Reklama sarlavhasi
        <input
          className="input"
          value={recordText(draft, "title")}
          placeholder="Masalan: Bugun 20% chegirma"
          onChange={(event) => setDraft({ ...draft, title: event.currentTarget.value })}
        />
      </label>
      <label className="field">
        Qisqa matn
        <textarea
          className="textarea"
          value={recordText(draft, "caption")}
          placeholder="Reklama haqida qisqa va aniq ma'lumot"
          onChange={(event) =>
            setDraft({ ...draft, caption: event.currentTarget.value })
          }
        />
      </label>
      <div className="field">
        <label>Qayerda ko'rinsin?</label>
        <select
          className="input full"
          aria-label="Hudud darajasi"
          value={level}
          onChange={(event) =>
            setDraft({
              ...draft,
              target_level: event.currentTarget.value,
              target_region: selectedRegion,
              target_district: selectedDistrict,
            })
          }
        >
          <option value="district">Tuman kesimida</option>
          <option value="region">Viloyat kesimida</option>
          <option value="republic">Respublika bo'ylab</option>
        </select>
        {level !== "republic" && (
          <select
            className="input"
            aria-label="Reklama viloyati"
            value={selectedRegion}
            onChange={(event) => {
              const region = event.currentTarget.value;
              const district =
                UZBEKISTAN_REGIONS.find((item) => item.name === region)?.districts[0] ??
                "";
              setDraft({
                ...draft,
                target_region: region,
                target_district: district,
              });
            }}
          >
            {UZBEKISTAN_REGIONS.map((region) => (
              <option value={region.name} key={region.name}>
                {region.name}
              </option>
            ))}
          </select>
        )}
        {level === "district" && (
          <select
            className="input"
            aria-label="Reklama tumani"
            value={selectedDistrict}
            onChange={(event) =>
              setDraft({ ...draft, target_district: event.currentTarget.value })
            }
          >
            {districts.map((district) => (
              <option value={district} key={district}>
                {district}
              </option>
            ))}
          </select>
        )}
        <button
          type="button"
          className="mini-btn"
          onClick={() => {
            const target = {
              level,
              region: level === "republic" ? "" : selectedRegion,
              district: level === "district" ? selectedDistrict : "",
            };
            if (level !== "republic" && !target.region) return;
            if (level === "district" && !target.district) return;
            const next =
              level === "republic"
                ? [target]
                : [
                    ...targets.filter((value) => value.level !== "republic"),
                    target,
                  ].filter(
                    (value, index, all) =>
                      all.findIndex(
                        (candidate) =>
                          JSON.stringify(candidate) === JSON.stringify(value),
                      ) === index,
                  );
            setDraft({ ...draft, targets: next });
          }}
        >
          + Hududni qo'shish
        </button>
        <div className="ad-targets">
          {targets.map((target, index) => (
            <span className="ad-target-chip" key={`${targetLabel(target)}-${index}`}>
              {targetLabel(target)}
              <button
                type="button"
                aria-label="Hududni o'chirish"
                onClick={() =>
                  setDraft({
                    ...draft,
                    targets: targets.filter((_, targetIndex) => targetIndex !== index),
                  })
                }
              >
                ×
              </button>
            </span>
          ))}
        </div>
      </div>
      <label className="field">
        Qachondan ko'rinsin?
        <input
          className="input"
          type="date"
          value={recordText(draft, "start_date")}
          onChange={(event) =>
            setDraft({ ...draft, start_date: event.currentTarget.value })
          }
        />
      </label>
      <div className="field">
        <label>Har kuni qaysi vaqtda ko'rinsin?</label>
        <label className="ad-all-day">
          <input
            type="checkbox"
            checked={Boolean(draft.daily_all_day)}
            onChange={(event) =>
              setDraft({ ...draft, daily_all_day: event.currentTarget.checked ? 1 : 0 })
            }
          />{" "}
          Kun bo'yi ko'rinsin
        </label>
        {!draft.daily_all_day && (
          <div className="ad-daily-times">
            <select
              className="input"
              aria-label="Kunlik boshlanish"
              value={dailyStart}
              onChange={(event) =>
                setDraft({ ...draft, daily_start: event.currentTarget.value })
              }
            >
              <option value="" disabled>
                Boshlanishni tanlang
              </option>
              {hours.map((hour) => (
                <option value={hour} key={hour}>
                  {hour}
                </option>
              ))}
            </select>
            <span>—</span>
            <select
              className="input"
              aria-label="Kunlik tugash"
              value={dailyEnd}
              onChange={(event) =>
                setDraft({ ...draft, daily_end: event.currentTarget.value })
              }
            >
              <option value="" disabled>
                Tugashni tanlang
              </option>
              {hours.map((hour) => (
                <option value={hour} key={hour}>
                  {hour}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="idesc">
          {draft.daily_all_day
            ? "Reklama kun davomida uzluksiz ko'rinadi."
            : dailyStart && dailyEnd
              ? `Har kuni ${dailyStart} dan ${dailyEnd} gacha ko'rinadi.`
              : "Boshlanish va tugash vaqtini alohida tanlang."}
        </div>
      </div>
      <label className="field">
        Qancha vaqt?
        <select
          className="input"
          value={Number(draft.duration_days ?? 1)}
          onChange={(event) =>
            setDraft({ ...draft, duration_days: Number(event.currentTarget.value) })
          }
        >
          {[1, 3, 7, 14, 30].map((days) => (
            <option value={days} key={days}>
              {days} kun
            </option>
          ))}
        </select>
      </label>
      <div className="ad-price-box">
        <div className="idesc">Hisoblangan reklama narxi</div>
        <div className="price">
          {v1656Money(recordNumber(quote ?? draft, "total", "price"))}
        </div>
        <div className="idesc">
          {quoteError ||
            (quote
              ? `${Number(quote.district_count ?? 0)} tuman × ${Number(quote.hours_per_day ?? 0)} soat × ${Number(quote.duration_days ?? 1)} kun × ${v1656Money(Number(quote.district_hour_rate ?? 0))}`
              : targets.length
                ? `${targets.length} ta hudud · ${Number(draft.duration_days ?? 1)} kun`
                : "Hududni tanlang.")}
        </div>
      </div>
      <div className="ad-info">
        Kvitansiya yuborilgach to'lov administrator tomonidan tekshiriladi. Reklama
        tasdiqlangandan keyin jadval bo'yicha ko'rinadi.
      </div>
      {fileError && (
        <div className="app-toast on" role="alert">
          {fileError}
        </div>
      )}
      {error && (
        <div className="app-toast on" role="alert">
          {error}
        </div>
      )}
      <button
        type="button"
        className="btn btn-primary btn-block"
        disabled={busy}
        onClick={() => void save()}
      >
        Reklamani joylashtirish
      </button>
      <button type="button" className="btn btn-soft btn-block" onClick={cancel}>
        Bekor qilish
      </button>
    </div>
  );
}
