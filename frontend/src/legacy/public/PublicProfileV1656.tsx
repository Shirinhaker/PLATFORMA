import { useEffect, useState } from "react";

import type { ApiClient } from "../../api/client";
import type { PublicProfileDetail, PublicProfileItem } from "../../api/types";


interface PublicProfileV1656Props {
  kind: "user" | "business";
  publicId: string;
  getPublicProfile: ApiClient["getPublicProfile"];
  onTitleChange?(title: string): void;
  onOpenListing?(publicId: string): void;
}


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
  getPublicProfile,
  onTitleChange,
  onOpenListing,
}: PublicProfileV1656Props) {
  const [profile, setProfile] = useState<PublicProfileDetail | null>(null);
  const [error, setError] = useState("");

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

  return (
    <main
      className="screen active public-profile-v1656"
      data-screen={business ? "business" : "user-page"}
    >
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
      </section>

      {profile.specialist ? (
        <section className="specialist-card">
          <b>{profile.specialist.profession || "Mutaxasis"}</b>
          {profile.specialist.description ? (
            <div className="idesc">{profile.specialist.description}</div>
          ) : null}
        </section>
      ) : null}

      {business && profile.items.length ? (
        <section className="public-profile-section">
          <div className="sec-head">
            <h2>Mahsulot va xizmatlar</h2>
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
                {items.map((item) => (
                  <article className="item-card2 biz-prod-card" key={item.public_id}>
                    <div className="item-card2-img">
                      {item.image_url ? <img alt="" src={item.image_url} /> : <span>📦</span>}
                    </div>
                    <div className="name">{item.name}</div>
                    <div className="price">{item.price_text || "Narx kelishiladi"}</div>
                    {item.note ? <div className="note">{item.note}</div> : null}
                  </article>
                ))}
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

      {!profile.items.length && !profile.listings.length && !profile.specialist ? (
        <div className="idesc public-profile-empty">
          {business ? "Hozircha ma'lumot yo'q" : "Hozircha e'lon yo'q"}
        </div>
      ) : null}
    </main>
  );
}
