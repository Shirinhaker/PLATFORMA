import { useState, type FormEvent } from "react";

import type { ApiClient } from "../api/client";
import "./StoriesV1656.css";


type Props = {
  createUploadGrant: ApiClient["createUploadGrant"];
  uploadGrantedFile: ApiClient["uploadGrantedFile"];
  createStory: ApiClient["createStory"];
  onCreated(): void | Promise<void>;
  onClose(): void;
};

const IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const VIDEO_TYPES = new Set(["video/mp4", "video/webm", "video/quicktime"]);
const IMAGE_LIMIT = 10 * 1024 * 1024;
const VIDEO_LIMIT = 100 * 1024 * 1024;


function videoDuration(file: File): Promise<number> {
  return new Promise((resolve, reject) => {
    const video = document.createElement("video");
    const url = URL.createObjectURL(file);
    const timeout = window.setTimeout(() => finish(
      new Error("Video davomiyligi aniqlanmadi."),
    ), 8000);
    let complete = false;
    function finish(error?: Error, duration = 0) {
      if (complete) return;
      complete = true;
      window.clearTimeout(timeout);
      URL.revokeObjectURL(url);
      video.removeAttribute("src");
      if (error) reject(error);
      else resolve(duration);
    }
    video.preload = "metadata";
    video.onloadedmetadata = () => finish(undefined, video.duration);
    video.onerror = () => finish(new Error("Video tekshirilmadi."));
    video.src = url;
  });
}


export function StoryComposerV1656({
  createUploadGrant,
  uploadGrantedFile,
  createStory,
  onCreated,
  onClose,
}: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [caption, setCaption] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("Rasm yoki video tanlang.");
      return;
    }
    const image = IMAGE_TYPES.has(file.type);
    const video = VIDEO_TYPES.has(file.type);
    if (!image && !video) {
      setError("Faqat JPEG, PNG, WEBP, MP4, WEBM yoki MOV qabul qilinadi.");
      return;
    }
    if (file.size > (image ? IMAGE_LIMIT : VIDEO_LIMIT)) {
      setError(image ? "Rasm 10 MB dan oshmasin." : "Video 100 MB dan oshmasin.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      if (video && await videoDuration(file) > 60) {
        throw new Error("Video 60 soniyadan oshmasin.");
      }
      const grant = await createUploadGrant({
        purpose: image ? "story_image" : "story_video",
        filename: file.name,
        content_type: file.type,
        size_bytes: file.size,
      });
      await uploadGrantedFile(grant, file);
      await createStory({
        object_key: grant.object_key,
        content_type: file.type,
        size_bytes: file.size,
        caption: caption.trim(),
      });
      await onCreated();
      onClose();
    } catch (reasonValue) {
      setError(reasonValue instanceof Error ? reasonValue.message : "Istoriya yaratilmadi.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div aria-label="Istoriya yaratish" aria-modal="true" className="story-composer-v1656" role="dialog">
      <form onSubmit={(event) => void submit(event)}>
        <header>
          <strong>Yangi istoriya</strong>
          <button aria-label="Yopish" type="button" onClick={onClose}>×</button>
        </header>
        <label>
          Rasm yoki video
          <input accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm" type="file" onChange={(event) => setFile(event.currentTarget.files?.[0] ?? null)} />
        </label>
        <small>Rasm 10 MB gacha. Video 100 MB gacha. Video 60 soniyadan oshmasin.</small>
        <label>
          Izoh
          <textarea maxLength={200} value={caption} onChange={(event) => setCaption(event.currentTarget.value)} />
        </label>
        <small>{caption.length} / 200</small>
        {error ? <p className="story-v1656__error" role="alert">{error}</p> : null}
        <button disabled={busy} type="submit">{busy ? "Yuklanmoqda…" : "Joylash"}</button>
      </form>
    </div>
  );
}
