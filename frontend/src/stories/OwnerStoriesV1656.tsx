import { useCallback, useEffect, useMemo, useState } from "react";

import type { ApiClient } from "../api/client";
import type { ManagedStoryRead, StoryGroup } from "../api/types";
import { StoryComposerV1656 } from "./StoryComposerV1656";
import { StoryViewerV1656 } from "./StoryViewerV1656";
import "./StoriesV1656.css";


export type OwnerStoriesApi = Pick<ApiClient,
  | "getMyStories"
  | "createStory"
  | "recordStoryView"
  | "getStoryViewers"
  | "deleteStory"
  | "reportStory"
  | "createUploadGrant"
  | "uploadGrantedFile"
>;

type Props = {
  actor: "user" | "business";
  api: OwnerStoriesApi;
  ownerPublicId?: string;
  ownerName: string;
  ownerAvatar?: string;
  onBack(): void;
};


export function OwnerStoriesV1656({
  actor,
  api,
  ownerPublicId = "",
  ownerName,
  ownerAvatar = "",
  onBack,
}: Props) {
  const [stories, setStories] = useState<ManagedStoryRead[]>([]);
  const [tab, setTab] = useState<"active" | "archived">("active");
  const [composer, setComposer] = useState(false);
  const [viewerIndex, setViewerIndex] = useState<number | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setStories(await api.getMyStories("all"));
      setError("");
    } catch (reasonValue) {
      setError(reasonValue instanceof Error ? reasonValue.message : "Istoriyalar yuklanmadi.");
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  const visible = useMemo(
    () => stories.filter((story) => story.state === tab),
    [stories, tab],
  );
  const group: StoryGroup = {
    owner_type: actor,
    owner_public_id: ownerPublicId || visible[0]?.owner_public_id || "",
    name: ownerName,
    avatar_url: ownerAvatar,
    is_own: true,
    is_followed: false,
    has_unseen: false,
    distance_km: null,
    stories: visible,
  };

  return (
    <main className="owner-stories-v1656">
      <header className="owner-stories__header">
        <button type="button" onClick={onBack}>← Orqaga</button>
        <h1>Istoriyalarim</h1>
        <button type="button" onClick={() => setComposer(true)}>+ Istoriya</button>
      </header>
      <div className="owner-stories__tabs">
        <button className={tab === "active" ? "is-active" : ""} type="button" onClick={() => setTab("active")}>Faol</button>
        <button className={tab === "archived" ? "is-active" : ""} type="button" onClick={() => setTab("archived")}>Arxiv</button>
      </div>
      {error ? <p className="story-v1656__error" role="alert">{error}</p> : null}
      {visible.length ? (
        <div className="owner-stories__grid">
          {visible.map((story, index) => (
            <button key={story.id} type="button" onClick={() => setViewerIndex(index)}>
              <img alt={story.caption || "Istoriya"} src={story.thumbnail_url || story.media_url} />
              <span>{story.view_count} ko‘rish</span>
            </button>
          ))}
        </div>
      ) : <p className="owner-stories__empty">Bu bo‘limda istoriya yo‘q.</p>}
      {composer ? (
        <StoryComposerV1656
          createStory={api.createStory}
          createUploadGrant={api.createUploadGrant}
          uploadGrantedFile={api.uploadGrantedFile}
          onClose={() => setComposer(false)}
          onCreated={load}
        />
      ) : null}
      {viewerIndex !== null && visible.length ? (
        <StoryViewerV1656
          deleteStory={api.deleteStory}
          getViewers={api.getStoryViewers}
          groups={[group]}
          initialGroupIndex={0}
          initialStoryIndex={viewerIndex}
          recordView={api.recordStoryView}
          reportStory={api.reportStory}
          onClose={() => setViewerIndex(null)}
          onDeleted={(storyId) => setStories((current) => current.filter((item) => item.id !== storyId))}
        />
      ) : null}
    </main>
  );
}
