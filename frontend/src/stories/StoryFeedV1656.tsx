import { useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type { StoryGroup } from "../api/types";
import { StoryRailV1656 } from "./StoryRailV1656";
import { StoryViewerV1656 } from "./StoryViewerV1656";


export type StoryViewerApi = Pick<ApiClient,
  | "recordStoryView"
  | "getStoryViewers"
  | "deleteStory"
  | "reportStory"
>;

type Props = StoryViewerApi & {
  load(): Promise<StoryGroup[]>;
};


export function StoryFeedV1656({
  load,
  recordStoryView,
  getStoryViewers,
  deleteStory,
  reportStory,
}: Props) {
  const [groups, setGroups] = useState<StoryGroup[]>([]);
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    load().then((items) => {
      if (active) setGroups(items);
    }).catch(() => {
      if (active) setGroups([]);
    });
    return () => {
      active = false;
    };
  }, [load]);

  return (
    <>
      <StoryRailV1656 groups={groups} onOpen={setOpenIndex} />
      {openIndex !== null ? (
        <StoryViewerV1656
          deleteStory={deleteStory}
          getViewers={getStoryViewers}
          groups={groups}
          initialGroupIndex={openIndex}
          recordView={recordStoryView}
          reportStory={reportStory}
          onClose={() => setOpenIndex(null)}
          onViewed={(storyId) => setGroups((current) => current.map((group) => {
            const stories = group.stories.map((story) => (
              story.id === storyId ? { ...story, viewed: true } : story
            ));
            return {
              ...group,
              has_unseen: stories.some((story) => !story.viewed),
              stories,
            };
          }))}
          onDeleted={(storyId) => setGroups((current) => current
            .map((group) => ({
              ...group,
              stories: group.stories.filter((story) => story.id !== storyId),
            }))
            .filter((group) => group.stories.length > 0))}
        />
      ) : null}
    </>
  );
}
