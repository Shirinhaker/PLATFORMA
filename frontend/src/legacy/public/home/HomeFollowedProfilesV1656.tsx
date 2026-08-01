import type { PublicFollowedProfile } from "../../../api/types";


interface HomeFollowedProfilesV1656Props {
  items: PublicFollowedProfile[];
  onOpenProfile(kind: "user" | "business", publicId: string): void;
}


export function HomeFollowedProfilesV1656({
  items,
  onOpenProfile,
}: HomeFollowedProfilesV1656Props) {
  return (
    <section
      className="story-strip"
      hidden={!items.length}
      id="followedProfileStrip"
      aria-label="Obuna bo‘lingan profillar"
    >
      <div className="story-rail" id="followedProfileRail">
        {items.map((item) => (
          <button
            aria-label={`${item.name || "Profil"} profilini ochish`}
            className="story-card"
            key={`${item.kind}:${item.public_id}`}
            type="button"
            onClick={() => onOpenProfile(item.kind, item.public_id)}
          >
            <span className="story-thumb">
              {item.image_url ? (
                <img
                  alt=""
                  loading="lazy"
                  src={item.image_url}
                />
              ) : null}
              <span className="story-fallback">
                {item.name.trim().charAt(0) || "K"}
              </span>
            </span>
            <span className="story-name">{item.name}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
