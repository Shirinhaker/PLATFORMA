import { useEffect, useState } from "react";

import type { StoryGroup, StoryViewer } from "../api/types";
import "./StoriesV1656.css";


type Props = {
  groups: StoryGroup[];
  initialGroupIndex: number;
  initialStoryIndex?: number;
  onClose(): void;
  recordView(storyId: number): Promise<unknown>;
  getViewers(storyId: number): Promise<StoryViewer[]>;
  deleteStory(storyId: number): Promise<unknown>;
  reportStory(storyId: number, reason: string): Promise<unknown>;
  onDeleted?(storyId: number): void;
  onViewed?(storyId: number): void;
};


export function StoryViewerV1656({
  groups,
  initialGroupIndex,
  initialStoryIndex,
  onClose,
  recordView,
  getViewers,
  deleteStory,
  reportStory,
  onDeleted,
  onViewed,
}: Props) {
  const [groupIndex, setGroupIndex] = useState(initialGroupIndex);
  const [storyIndex, setStoryIndex] = useState(() => {
    if (initialStoryIndex !== undefined) return Math.max(0, initialStoryIndex);
    const unseen = groups[initialGroupIndex]?.stories.findIndex((item) => !item.viewed);
    return unseen !== undefined && unseen >= 0 ? unseen : 0;
  });
  const [viewers, setViewers] = useState<StoryViewer[] | null>(null);
  const [reporting, setReporting] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const group = groups[groupIndex];
  const story = group?.stories[storyIndex];

  function move(direction: 1 | -1) {
    if (!group) return;
    const nextStory = storyIndex + direction;
    if (nextStory >= 0 && nextStory < group.stories.length) {
      setStoryIndex(nextStory);
      return;
    }
    const nextGroup = groupIndex + direction;
    if (nextGroup >= 0 && nextGroup < groups.length) {
      const targetGroup = groups[nextGroup];
      if (!targetGroup) return;
      setGroupIndex(nextGroup);
      setStoryIndex(direction === 1 ? 0 : targetGroup.stories.length - 1);
      return;
    }
    onClose();
  }

  useEffect(() => {
    if (!story) return undefined;
    setError("");
    setViewers(null);
    setReporting(false);
    setReason("");
    const viewTimer = window.setTimeout(() => {
      void recordView(story.id)
        .then(() => onViewed?.(story.id))
        .catch(() => undefined);
    }, 700);
    const seconds = story.media_type === "image"
      ? 5
      : Math.min(60, Math.max(1, story.duration_seconds || 60));
    const timer = window.setTimeout(() => move(1), seconds * 1000);
    return () => {
      window.clearTimeout(viewTimer);
      window.clearTimeout(timer);
    };
  }, [groupIndex, storyIndex, story?.id]);

  if (!group || !story) return null;
  const storyId = story.id;

  async function showViewers() {
    setError("");
    try {
      setViewers(await getViewers(storyId));
    } catch (reasonValue) {
      setError(reasonValue instanceof Error ? reasonValue.message : "Ko‘ruvchilar yuklanmadi.");
    }
  }

  async function remove() {
    if (!window.confirm("Istoriyani o‘chirasizmi?")) return;
    try {
      await deleteStory(storyId);
      onDeleted?.(storyId);
      onClose();
    } catch (reasonValue) {
      setError(reasonValue instanceof Error ? reasonValue.message : "Istoriya o‘chirilmadi.");
    }
  }

  async function sendReport() {
    const cleanReason = reason.trim();
    if (cleanReason.length < 10) {
      setError("Shikoyat sababi kamida 10 belgi bo‘lsin.");
      return;
    }
    try {
      await reportStory(storyId, cleanReason);
      setReporting(false);
      setReason("");
    } catch (reasonValue) {
      setError(reasonValue instanceof Error ? reasonValue.message : "Shikoyat yuborilmadi.");
    }
  }

  return (
    <div aria-label="Istoriya ko‘ruvchisi" aria-modal="true" className="story-viewer-v1656" role="dialog">
      <div className="story-viewer__panel">
        <div className="story-viewer__progress" aria-hidden="true">
          {group.stories.map((item, index) => (
            <span className={index <= storyIndex ? "is-done" : ""} key={item.id} />
          ))}
        </div>
        <header className="story-viewer__header">
          <strong>{group.name}</strong>
          <button aria-label="Yopish" type="button" onClick={onClose}>×</button>
        </header>
        <div className="story-viewer__media">
          {story.media_type === "video" ? (
            <video
              autoPlay
              playsInline
              poster={story.thumbnail_url}
              src={story.media_url}
              onCanPlay={(event) => {
                const video = event.currentTarget;
                void video.play().catch(() => {
                  video.muted = true;
                  void video.play().catch(() => undefined);
                });
              }}
            />
          ) : (
            <img alt={story.caption || `${group.name} istoriyasi`} src={story.media_url} />
          )}
          <button aria-label="Oldingi istoriya" className="story-viewer__nav story-viewer__nav--prev" type="button" onClick={() => move(-1)} />
          <button aria-label="Keyingi istoriya" className="story-viewer__nav story-viewer__nav--next" type="button" onClick={() => move(1)} />
        </div>
        {story.caption ? <p className="story-viewer__caption">{story.caption}</p> : null}
        <footer className="story-viewer__actions">
          {group.is_own ? (
            <>
              <button type="button" onClick={() => void showViewers()}>Ko‘rganlar</button>
              <button type="button" onClick={() => void remove()}>O‘chirish</button>
            </>
          ) : (
            <button type="button" onClick={() => setReporting(true)}>Shikoyat</button>
          )}
        </footer>
        {viewers ? (
          <div className="story-viewer__drawer">
            <strong>Ko‘rganlar</strong>
            {viewers.length ? viewers.map((viewer) => (
              <div key={`${viewer.account_public_id}:${viewer.viewed_at}`}>{viewer.name}</div>
            )) : <p>Hali hech kim ko‘rmagan.</p>}
          </div>
        ) : null}
        {reporting ? (
          <div className="story-viewer__drawer">
            <label htmlFor="story-report-reason">Shikoyat sababi</label>
            <textarea id="story-report-reason" maxLength={300} value={reason} onChange={(event) => setReason(event.currentTarget.value)} />
            <button type="button" onClick={() => void sendReport()}>Yuborish</button>
          </div>
        ) : null}
        {error ? <p className="story-v1656__error" role="alert">{error}</p> : null}
      </div>
    </div>
  );
}
