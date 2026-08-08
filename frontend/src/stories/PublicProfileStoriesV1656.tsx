import { useCallback } from "react";

import type { ApiClient } from "../api/client";
import type { StoryGroup } from "../api/types";
import { StoryFeedV1656, type StoryViewerApi } from "./StoryFeedV1656";


type Props = StoryViewerApi & {
  kind: "user" | "business";
  publicId: string;
  name: string;
  avatarUrl: string;
  getOwnerStories: ApiClient["getOwnerStories"];
};


export function PublicProfileStoriesV1656({
  kind,
  publicId,
  name,
  avatarUrl,
  getOwnerStories,
  ...viewerApi
}: Props) {
  const load = useCallback(async (): Promise<StoryGroup[]> => {
    const stories = await getOwnerStories(kind, publicId);
    if (stories.length === 0) return [];
    return [{
      owner_type: kind,
      owner_public_id: publicId,
      name,
      avatar_url: avatarUrl,
      is_own: false,
      is_followed: false,
      has_unseen: stories.some((story) => !story.viewed),
      distance_km: null,
      stories,
    }];
  }, [avatarUrl, getOwnerStories, kind, name, publicId]);

  return <StoryFeedV1656 load={load} {...viewerApi} />;
}
