import { useEffect, useRef, useState } from "react";

import type { ApiClient } from "../../api/client";
import type { PublicProfileDetail, PublicProfileItem } from "../../api/types";
import {
  cartReceiptTotal,
  formatQuantity,
  moneyText,
  type CartReceipt,
} from "../../orders/order-store";
import type { QueueBookingTarget } from "../../queues/QueueBookingV1656";
import type { CourseEnrollmentTarget } from "../../education/CourseEnrollmentV1656";
import { PublicProfileStoriesV1656 } from "../../stories/PublicProfileStoriesV1656";
import type { StoryViewerApi } from "../../stories/StoryFeedV1656";
import {
  PublicReviewsV1656,
  type PublicReviewsApi,
} from "../../reviews/ReviewsV1656";


interface PublicProfileV1656Props {
  kind: "user" | "business";
  publicId: string;
  focusItemPublicId?: string;
  getPublicProfile: ApiClient["getPublicProfile"];
  authenticated?: boolean;
  cart?: CartReceipt;
  onAddCartItem?(
    item: PublicProfileItem,
    provider: { public_id: string; name: string },
  ): void;
  onNeedLogin?(): void;
  onMessage?(kind: "user" | "business", publicId: string, name: string): void;
  onNeedQueueLogin?(): void;
  onBookQueue?(target: QueueBookingTarget): void;
  onEnrollCourse?(target: CourseEnrollmentTarget): void;
  onNeedCourseLogin?(): void;
  onQueueMessage?(message: string): void;
  onOpenCart?(): void;
  onTitleChange?(title: string): void;
  onOpenListing?(publicId: string): void;
  storyApi?: StoryViewerApi & Pick<ApiClient, "getOwnerStories">;
  reviewApi?: PublicReviewsApi;
}

const QUEUE_DIRECTIONS = new Set([
  "Transport va logistika",
  "Xizmat ko'rsatish",
  "Maishiy xizmatlar",
  "Qurilish",
  "Tibbiy xizmatlar",
  "Ko'chmas mulk",
  "Axborot texnologiyalari",
  "Konsalting va professional",
  "Madaniyat, sport, ko'ngilochar",
  "Turizm va mehmonxona",
  "Reklama va marketing",
  "Poligrafiya va nashriyot",
  "Moliyaviy faoliyat",
  "Import-eksport",
]);


function cropStyle(profile: PublicProfileDetail) {
  const zoom = Number.isFinite(profile.crop_zoom) ? profile.crop_zoom : 1;
  const x = Number.isFinite(profile.crop_x) ? profile.crop_x : 50;
  const y = Number.isFinite(profile.crop_y) ? profile.crop_y : 50;
  return {
    width: `${zoom * 100}%`,
    height: `${zoom * 100}%`,
    left: `${50 - x * zoom}%`,
    top: `${50 - y * zoom}%`,
  };
}


function itemGroups(items: PublicProfileItem[]) {
  const groups = new Map<string, PublicProfileItem[]>();
  items.forEach((item) => {
    const key = item.group_name.trim();
    groups.set(key, [...(groups.get(key) ?? []), item]);
  });
  return Array.from(groups.entries());
}


export function PublicProfileV1656({
  kind,
  publicId,
  focusItemPublicId,
  getPublicProfile,
  authenticated = false,
  cart,
  onAddCartItem,
  onNeedLogin,
  onMessage,
  onNeedQueueLogin,
  onBookQueue,
  onEnrollCourse,
  onNeedCourseLogin,
  onQueueMessage,
  onOpenCart,
  onTitleChange,
  onOpenListing,
  storyApi,
  reviewApi,
}: PublicProfileV1656Props) {
  const [profile, setProfile] = useState<PublicProfileDetail | null>(null);
  const [error, setError] = useState("");
  const focusItemRef = useRef<HTMLElement>(null);

  useEffect(() => {
    let active = true;
    setProfile(null);
    setError("");
    getPublicProfile(kind, publicId)
      .then((payload) => {
        if (!active) return;
        setProfile(payload);
        onTitleChange?.(payload.name);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(
          reason instanceof Error ? reason.message : "Profil topilmadi.",
        );
      });
    return () => {
      active = false;
    };
  }, [getPublicProfile, kind, onTitleChange, publicId]);

  useEffect(() => {
    if (!profile || !focusItemPublicId) return undefined;
    const frame = window.requestAnimationFrame(() => {
      const element = focusItemRef.current;
      if (!element) return;
      element.focus({ preventScroll: true });
      element.scrollIntoView?.({
        behavior: "smooth",
        block: "center",
        inline: "center",
      });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [focusItemPublicId, profile]);

  if (error) {
    return (
      <main className="screen active public-profile-v1656" data-screen="business">
        <div className="empty">
          <h3>Topilmadi</h3>
          <p>{error}</p>
        </div>
      </main>
    );
  }
  if (!profile) {
    return (
      <main className="screen active public-profile-v1656" data-screen="business">
        <div className="idesc public-profile-loading">Yuklanmoqda...</div>
      </main>
    );
  }

  const initial = profile.name.trim().charAt(0).toUpperCase() || "K";
  const meta = [profile.direction, profile.activity_type]
    .filter(Boolean)
    .join(" · ");
  const groups = itemGroups(profile.items);
  const business = profile.kind === "business";
  const providerPublicId = profile.public_id;
  const providerName = profile.name;
  const profileDirection = profile.direction;
  const education = profileDirection === "Ta'lim faoliyati";
  const queueSupported = business && QUEUE_DIRECTIONS.has(profileDirection);
  const queueTotal = Math.max(0, Number(profile.queue_total) || 0);
  const hasQueueService = profile.items.some((item) => (
    item.kind === "service" && item.queue_enabled
  ));
  const cartLines = Object.keys(cart?.items ?? {}).length;
  const cartTotal = cart ? cartReceiptTotal(cart) : 0;

  function itemAction(item: PublicProfileItem) {
    if (education) {
      if (item.enrollment_status === "closed") return null;
      return (
        <button
          className="biz-add-btn"
          type="button"
          onClick={() => {
            if (!authenticated) {
              (onNeedCourseLogin ?? onNeedLogin)?.();
              return;
            }
            onEnrollCourse?.({
              itemPublicId: item.public_id,
              courseName: item.name || "Kurs",
            });
          }}
        >Kursga yozilish</button>
      );
    }
    if (
      QUEUE_DIRECTIONS.has(profileDirection)
      && item.kind === "service"
      && item.queue_enabled
    ) {
      return (
        <button
          className="biz-add-btn"
          type="button"
          onClick={() => {
            if (Math.max(0, Number(item.queue_provider_count) || 0) < 1) {
              onQueueMessage?.(profileDirection === "Tibbiy xizmatlar"
                ? "Shifokor hali biriktirilmagan."
                : "Xizmat ko'rsatuvchi hali biriktirilmagan.");
              return;
            }
            if (!authenticated) {
              (onNeedQueueLogin ?? onNeedLogin)?.();
              return;
            }
            onBookQueue?.({
              businessPublicId: providerPublicId,
              itemPublicId: item.public_id,
              serviceName: item.name || "Xizmat",
              direction: profileDirection,
            });
          }}
        >Navbat olish</button>
      );
    }
    const quantity = cart?.items[item.public_id]?.qty ?? 0;
    return (
      <div className="biz-item-ctrl">
        <button
          className={`biz-add-btn${quantity > 0 ? " in-cart" : ""}`}
          type="button"
          onClick={() => {
            if (!authenticated) {
              onNeedLogin?.();
              return;
            }
            onAddCartItem?.(item, {
              public_id: providerPublicId,
              name: providerName,
            });
          }}
        >{quantity > 0 ? `✓ Savatda: ${formatQuantity(quantity)}` : "+ Savatga"}</button>
      </div>
    );
  }

  return (
    <main
      className="screen active public-profile-v1656"
      data-screen={business ? "business" : "user-page"}
    >
      {business && cartLines > 0 ? (
        <div id="bizCartBar">
          <button className="btn btn-amber btn-block" id="bizCartBarBtn" type="button" onClick={onOpenCart}>
            <span>🛒 Savatcha: <b id="bizCartBarCount">{cartLines}</b> ta{cartTotal > 0 ? <> · <b id="bizCartBarTotal">{moneyText(cartTotal)}</b></> : null}</span>
            <span>Ko'rish →</span>
          </button>
        </div>
      ) : null}
      <section className="public-profile-hero koprik-profile-surface">
        <div className={`public-profile-avatar${profile.image_url ? " has-photo" : ""}`}>
          <span>{initial}</span>
          {profile.image_url ? (
            <img alt="" src={profile.image_url} style={cropStyle(profile)} />
          ) : null}
        </div>
        <div className="public-profile-name">{profile.name}</div>
        {profile.public_username ? (
          <div className="idesc">@{profile.public_username.replace(/^@/, "")}</div>
        ) : null}
        {meta ? <div className="idesc">{meta}</div> : null}
        {profile.address ? <div className="idesc">📍 {profile.address}</div> : null}
        {profile.phone ? (
          <a className="idesc public-profile-phone" href={`tel:${profile.phone}`}>
            📞 {profile.phone}
          </a>
        ) : null}
        {profile.followers_count ? (
          <div className="idesc">{profile.followers_count} obunachi</div>
        ) : null}
        {profile.description ? (
          <div className="biz-desc">{profile.description}</div>
        ) : null}
        {onMessage ? (
          <button
            type="button"
            className="btn btn-block public-profile-message"
            onClick={() => {
              if (!authenticated) {
                onNeedLogin?.();
                return;
              }
              onMessage(kind, publicId, profile.name);
            }}
          >✍️ Xabar yozish</button>
        ) : null}
        {queueSupported && (queueTotal > 0 || hasQueueService) ? (
          <div
            className="idesc"
            data-biz-queue-total
            style={{ marginTop: 10, color: "var(--primary)", fontWeight: 800 }}
          >👥 Bugungi jami navbat: {queueTotal} ta</div>
        ) : null}
      </section>

      {storyApi ? (
        <PublicProfileStoriesV1656
          avatarUrl={profile.image_url}
          deleteStory={storyApi.deleteStory}
          getOwnerStories={storyApi.getOwnerStories}
          getStoryViewers={storyApi.getStoryViewers}
          kind={kind}
          name={profile.name}
          publicId={publicId}
          recordStoryView={storyApi.recordStoryView}
          reportStory={storyApi.reportStory}
        />
      ) : null}

      {profile.specialist ? (
        <>
          <section className="specialist-card">
            <b>{profile.specialist.profession || "Mutaxasis"}</b>
            {profile.specialist.description ? (
              <div className="idesc">{profile.specialist.description}</div>
            ) : null}
          </section>
          {(profile.specialist.credentials ?? []).length ? (
            <section className="public-profile-section public-specialist-section">
              <div className="sec-head">
                <h2>Tasdiqlovchi hujjatlar</h2>
                <span className="link">{profile.specialist.credentials?.length} ta</span>
              </div>
              <div className="public-specialist-rail">
                {profile.specialist.credentials?.map((item) => (
                  <div className="sp-media-card" key={item.id}>
                    <img alt="Tasdiqlovchi hujjat" loading="lazy" src={item.image_url} />
                  </div>
                ))}
              </div>
            </section>
          ) : null}
          {(profile.specialist.offers ?? []).length ? (
            <section className="public-profile-section public-specialist-section">
              <div className="sec-head">
                <h2>Xizmatlar va mahsulotlar</h2>
                <span className="link">{profile.specialist.offers?.length} ta</span>
              </div>
              <div className="public-specialist-rail">
                {profile.specialist.offers?.map((item) => (
                  <article className="sp-offer-card" key={item.id}>
                    <div className="sp-offer-img">
                      {item.image_url
                        ? <img alt="" loading="lazy" src={item.image_url} />
                        : item.kind === "product" ? "📦" : "🧰"}
                    </div>
                    <div className="sp-offer-body">
                      <div className="sp-offer-kind">
                        {item.kind === "product" ? "Mahsulot" : "Xizmat"}
                      </div>
                      <div className="sp-offer-name">{item.name}</div>
                      {item.price_text ? <div className="sp-offer-price">{item.price_text}</div> : null}
                      {item.note ? <div className="idesc">{item.note}</div> : null}
                    </div>
                  </article>
                ))}
              </div>
            </section>
          ) : null}
          {(profile.specialist.portfolio ?? []).length ? (
            <section className="public-profile-section public-specialist-section">
              <div className="sec-head">
                <h2>Bajargan ishlari</h2>
                <span className="link">{profile.specialist.portfolio?.length} ta</span>
              </div>
              <div className="public-specialist-rail">
                {profile.specialist.portfolio?.map((item) => (
                  <div className="sp-media-card" key={item.id}>
                    {item.media_type === "video" ? (
                      <>
                        <video controls playsInline preload="metadata" src={item.media_url} />
                        <span className="sp-media-type">▶ VIDEO</span>
                      </>
                    ) : (
                      <img alt="Ish namunasi" loading="lazy" src={item.media_url} />
                    )}
                  </div>
                ))}
              </div>
            </section>
          ) : null}
        </>
      ) : null}

      {business && profile.items.length ? (
        <section className="public-profile-section">
          <div className="sec-head">
            <h2>{education ? "Kurslar va xizmatlar" : "Mahsulot va xizmatlar"}</h2>
            <span className="link">{profile.items.length} ta</span>
          </div>
          {groups.map(([groupName, items]) => (
            <div className="item-group-block" key={groupName || "ungrouped"}>
              {groupName ? (
                <div className="item-group-head">
                  <div className="item-group-title">
                    <h3>{groupName}</h3>
                    <p>{items.length} ta</p>
                  </div>
                </div>
              ) : null}
              <div className="item-hrow">
                {items.map((item) => {
                  const focused = item.public_id === focusItemPublicId;
                  const queueEnabled = queueSupported
                    && item.kind === "service"
                    && item.queue_enabled;
                  const queueCount = Math.max(
                    0,
                    Number(item.today_queue_count) || 0,
                  );
                  return (
                    <article
                      aria-current={focused ? "true" : undefined}
                      className={`item-card2 biz-prod-card${focused ? " is-search-target" : ""}`}
                      data-item-public-id={item.public_id}
                      key={item.public_id}
                      ref={focused ? focusItemRef : undefined}
                      tabIndex={focused ? -1 : undefined}
                    >
                      <div className="item-card2-img">
                        {item.image_url ? <img alt="" src={item.image_url} /> : <span>📦</span>}
                      </div>
                      <div className="name">{item.name}</div>
                      <div className="price">{item.price_text || "Narx kelishiladi"}</div>
                      {item.note ? <div className="note">{item.note}</div> : null}
                      {education ? (
                        <>
                          <div className="note">
                            {item.course_mode === "online"
                              ? "Onlayn"
                              : item.course_mode === "hybrid"
                                ? "Aralash"
                                : "Offline"}
                            {item.course_duration ? ` · ${item.course_duration}` : ""}
                            {item.lesson_duration
                              ? ` · ${item.lesson_duration} daqiqa`
                              : ""}
                          </div>
                          {item.age_from || item.age_to ? (
                            <div className="note">
                              Yosh: {item.age_from || 0}–{item.age_to || "+"}
                            </div>
                          ) : null}
                          <div className="kind">
                            {item.enrollment_status === "closed"
                              ? "Qabul yopiq"
                              : "Qabul ochiq"}
                          </div>
                        </>
                      ) : null}
                      {queueEnabled ? (
                        <div
                          className="idesc"
                          data-medical-queue-count={queueCount}
                          style={{ color: "var(--primary)", fontWeight: 800, marginTop: 3 }}
                        >👥 Bugungi navbat: {queueCount} ta</div>
                      ) : null}
                      {itemAction(item)}
                    </article>
                  );
                })}
              </div>
            </div>
          ))}
        </section>
      ) : null}

      {profile.listings.length ? (
        <section className="public-profile-section">
          <div className="sec-head">
            <h2>E'lonlari</h2>
            <span className="link">{profile.listings.length} ta</span>
          </div>
          {profile.listings.map((listing) => (
            <button
              className="elon-item"
              key={listing.public_id}
              type="button"
              onClick={() => onOpenListing?.(listing.public_id)}
            >
              <div className="li-thumb">
                {listing.image_url ? <img alt="" src={listing.image_url} /> : <span>📦</span>}
              </div>
              <div className="li-main">
                <div className="li-title">{listing.title}</div>
                {listing.price_text ? <div className="iprice">{listing.price_text}</div> : null}
                {listing.address ? <div className="li-meta">{listing.address}</div> : null}
              </div>
            </button>
          ))}
        </section>
      ) : null}

      {reviewApi && (business || profile.specialist) ? (
        <PublicReviewsV1656
          api={reviewApi}
          targetKind={business ? "business" : "specialist"}
          targetPublicId={publicId}
        />
      ) : null}

      {!profile.items.length && !profile.listings.length && !profile.specialist ? (
        <div className="idesc public-profile-empty">
          {business ? "Hozircha ma'lumot yo'q" : "Hozircha e'lon yo'q"}
        </div>
      ) : null}
    </main>
  );
}
