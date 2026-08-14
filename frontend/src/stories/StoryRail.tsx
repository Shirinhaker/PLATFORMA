import type { StoryGroup } from "../api/types";
import "./Stories.css";


type Props = {
  groups: StoryGroup[];
  onOpen(index: number): void;
};


export function StoryRail({ groups, onOpen }: Props) {
  if (groups.length === 0) return null;
  return (
    <section aria-label="Istoriyalar" className="story-rail-modular">
      {groups.map((group, index) => (
        <button
          aria-label={`${group.name} istoriyasini ko‘rish`}
          className={`story-rail-card-modular ${group.has_unseen ? "story-rail-card-modular--unseen" : "story-rail-card-modular--seen"}`}
          key={`${group.owner_type}:${group.owner_public_id}`}
          type="button"
          onClick={() => onOpen(index)}
        >
          <span className="story-rail-card-modular__ring">
            {group.avatar_url || group.stories[0]?.thumbnail_url ? (
              <img alt="" src={group.avatar_url || group.stories[0]?.thumbnail_url} />
            ) : (
              <span aria-hidden="true">{group.name.trim().charAt(0).toUpperCase()}</span>
            )}
          </span>
          <span className="story-rail-card-modular__name">{group.is_own ? "Siz" : group.name}</span>
        </button>
      ))}
    </section>
  );
}
