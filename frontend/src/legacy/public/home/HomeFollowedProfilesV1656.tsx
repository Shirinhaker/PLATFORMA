import { useMemo } from "react";

import type { PublicFollowedProfile, StoryGroup } from "../../../api/types";


interface HomeFollowedProfilesV1656Props {
  items: PublicFollowedProfile[];
  storyGroups?: StoryGroup[];
  onOpenStory?(index: number): void;
  onOpenProfile(kind: "user" | "business", publicId: string): void;
}


export function HomeFollowedProfilesV1656({
  items,
  storyGroups = [],
  onOpenStory,
  onOpenProfile,
}: HomeFollowedProfilesV1656Props) {
  const storiesByOwner = useMemo(() => new Map(
    storyGroups.map((group, index) => [
      `${group.owner_type}:${group.owner_public_id}`,
      { group, index },
    ]),
  ), [storyGroups]);

  return (
    <section
      className="story-strip"
      hidden={!items.length}
      id="followedProfileStrip"
      aria-label="Obuna bo‘lingan profillar"
    >
      <div className="story-rail" id="followedProfileRail">
        {items.map((item) => {
          const storyMatch = storiesByOwner.get(`${item.kind}:${item.public_id}`);
          const hasStory = Boolean(storyMatch?.group.stories.length && onOpenStory);
          const label = item.name || "Profil";
          return (
            <button
              aria-label={hasStory
                ? `${label} istoriyasini ko‘rish`
                : `${label} profilini ochish`}
              className={`story-card${hasStory
                ? (storyMatch?.group.has_unseen ? " unseen" : " seen")
                : ""}`}
              key={`${item.kind}:${item.public_id}`}
              type="button"
              onClick={() => {
                if (hasStory && storyMatch) {
                  onOpenStory?.(storyMatch.index);
                  return;
                }
                onOpenProfile(item.kind, item.public_id);
              }}
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
          );
        })}
      </div>
    </section>
  );
}
