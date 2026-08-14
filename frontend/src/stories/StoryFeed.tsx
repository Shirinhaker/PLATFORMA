import { type ReactNode, useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type { StoryGroup } from "../api/types";
import { StoryRail } from "./StoryRail";
import { StoryViewer } from "./StoryViewer";


export type StoryViewerApi = Pick<ApiClient,
  | "recordStoryView"
  | "getStoryViewers"
  | "deleteStory"
  | "reportStory"
>;

type Props = StoryViewerApi & {
  load(): Promise<StoryGroup[]>;
  onOpenOwner?(kind: StoryGroup["owner_type"], publicId: string): void;
  renderRail?(groups: StoryGroup[], onOpen: (index: number) => void): ReactNode;
};


export function StoryFeed({
  load,
  recordStoryView,
  getStoryViewers,
  deleteStory,
  reportStory,
  onOpenOwner,
  renderRail,
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
      {renderRail
        ? renderRail(groups, setOpenIndex)
        : <StoryRail groups={groups} onOpen={setOpenIndex} />}
      {openIndex !== null ? (
        <StoryViewer
          deleteStory={deleteStory}
          getViewers={getStoryViewers}
          groups={groups}
          initialGroupIndex={openIndex}
          recordView={recordStoryView}
          reportStory={reportStory}
          onClose={() => setOpenIndex(null)}
          onOpenOwner={onOpenOwner}
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
