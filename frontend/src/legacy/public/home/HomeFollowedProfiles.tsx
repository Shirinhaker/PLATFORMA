import { useMemo } from "react";

import type { PublicFollowedProfile, StoryGroup } from "../../../api/types";


interface HomeFollowedProfilesProps {
  items: PublicFollowedProfile[];
  storyGroups?: StoryGroup[];
  onOpenStory?(index: number): void;
  onOpenProfile(kind: "user" | "business", publicId: string): void;
}


type HomeProfileCard = {
  displayName: string;
  hasUnseen: boolean;
  imageUrl: string;
  key: string;
  kind: "user" | "business";
  name: string;
  publicId: string;
  storyIndex: number | null;
};


export function HomeFollowedProfiles({
  items,
  storyGroups = [],
  onOpenStory,
  onOpenProfile,
}: HomeFollowedProfilesProps) {
  const cards = useMemo(() => {
    const storiesByOwner = new Map<string, {
      group: StoryGroup;
      index: number;
    }>();
    let ownStory: { group: StoryGroup; index: number } | null = null;
    for (let index = 0; index < storyGroups.length; index += 1) {
      const group = storyGroups[index];
      if (!group || group.stories.length === 0) continue;
      const entry = { group, index };
      storiesByOwner.set(`${group.owner_type}:${group.owner_public_id}`, entry);
      if (group.is_own && ownStory === null) ownStory = entry;
    }

    const result: HomeProfileCard[] = [];
    if (ownStory && onOpenStory) {
      const { group, index } = ownStory;
      result.push({
        displayName: "Siz",
        hasUnseen: group.has_unseen,
        imageUrl: group.avatar_url,
        key: `own:${group.owner_type}:${group.owner_public_id}`,
        kind: group.owner_type,
        name: group.name,
        publicId: group.owner_public_id,
        storyIndex: index,
      });
    }

    items.forEach((item) => {
      const key = `${item.kind}:${item.public_id}`;
      if (ownStory && key === `${ownStory.group.owner_type}:${ownStory.group.owner_public_id}`) {
        return;
      }
      const storyMatch = storiesByOwner.get(key);
      const hasStory = Boolean(storyMatch && onOpenStory);
      result.push({
        displayName: item.name,
        hasUnseen: storyMatch?.group.has_unseen ?? false,
        imageUrl: item.image_url,
        key,
        kind: item.kind,
        name: item.name || "Profil",
        publicId: item.public_id,
        storyIndex: hasStory ? storyMatch?.index ?? null : null,
      });
    });
    return result;
  }, [items, onOpenStory, storyGroups]);

  return (
    <section
      className="story-strip"
      hidden={!cards.length}
      id="followedProfileStrip"
      aria-label="Obuna bo‘lingan profillar"
    >
      <div className="story-rail" id="followedProfileRail">
        {cards.map((card) => {
          const hasStory = card.storyIndex !== null;
          return (
            <button
              aria-label={card.key.startsWith("own:")
                ? "Sizning istoriyangizni ko‘rish"
                : (hasStory
                  ? `${card.name} istoriyasini ko‘rish`
                  : `${card.name} profilini ochish`)}
              className={`story-card${hasStory
                ? (card.hasUnseen ? " unseen" : " seen")
                : ""}`}
              key={card.key}
              type="button"
              onClick={() => {
                if (card.storyIndex !== null) {
                  onOpenStory?.(card.storyIndex);
                  return;
                }
                onOpenProfile(card.kind, card.publicId);
              }}
            >
              <span className="story-thumb">
                {card.imageUrl ? (
                  <img
                    alt=""
                    loading="lazy"
                    src={card.imageUrl}
                  />
                ) : null}
                <span className="story-fallback">
                  {card.name.trim().charAt(0) || "K"}
                </span>
              </span>
              <span className="story-name">{card.displayName}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
