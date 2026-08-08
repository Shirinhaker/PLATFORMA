import type { StoryGroup } from "../api/types";
import "./StoriesV1656.css";


type Props = {
  groups: StoryGroup[];
  onOpen(index: number): void;
};


export function StoryRailV1656({ groups, onOpen }: Props) {
  if (groups.length === 0) return null;
  return (
    <section aria-label="Istoriyalar" className="story-rail-v1656">
      {groups.map((group, index) => (
        <button
          aria-label={`${group.name} istoriyasini ko‘rish`}
          className={`story-card ${group.has_unseen ? "story-card--unseen" : "story-card--seen"}`}
          key={`${group.owner_type}:${group.owner_public_id}`}
          type="button"
          onClick={() => onOpen(index)}
        >
          <span className="story-card__ring">
            {group.avatar_url || group.stories[0]?.thumbnail_url ? (
              <img alt="" src={group.avatar_url || group.stories[0]?.thumbnail_url} />
            ) : (
              <span aria-hidden="true">{group.name.trim().charAt(0).toUpperCase()}</span>
            )}
          </span>
          <span className="story-card__name">{group.is_own ? "Siz" : group.name}</span>
        </button>
      ))}
    </section>
  );
}
