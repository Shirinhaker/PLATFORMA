import type { Dispatch, ReactNode, SetStateAction } from "react";

import type { BusinessOnlineRecord } from "../../api/business-online-types";
import { recordId, recordText, type SharedActions } from "../BusinessOnlineViews";
import { storyRemaining } from "./shared";

type StoryConfirm = {
  id: number | string;
  title?: string;
  text: string;
  ok: string;
};

export function CrudStoriesView({
  rows,
  storyState,
  setStoryState,
  storyViewer,
  setStoryViewer,
  storyFile,
  setStoryFile,
  openForm,
  setOpenForm,
  draft,
  setDraft,
  validationError,
  setValidationError,
  setConfirm,
  begin,
  actions,
  dialog,
}: {
  rows: BusinessOnlineRecord[];
  storyState: "active" | "archived";
  setStoryState: Dispatch<SetStateAction<"active" | "archived">>;
  storyViewer: BusinessOnlineRecord | null;
  setStoryViewer: Dispatch<SetStateAction<BusinessOnlineRecord | null>>;
  storyFile: File | null;
  setStoryFile: Dispatch<SetStateAction<File | null>>;
  openForm: boolean;
  setOpenForm: Dispatch<SetStateAction<boolean>>;
  draft: BusinessOnlineRecord;
  setDraft: Dispatch<SetStateAction<BusinessOnlineRecord>>;
  validationError: string;
  setValidationError: Dispatch<SetStateAction<string>>;
  setConfirm: Dispatch<SetStateAction<StoryConfirm | null>>;
  begin: (next: BusinessOnlineRecord) => void;
  actions: SharedActions;
  dialog: ReactNode;
}) {
  const visible = rows.filter((row) => {
    const state = recordText(row, "state", "status");
    return storyState === "archived"
      ? ["archived", "expired"].includes(state)
      : !["archived", "expired"].includes(state);
  });
  return (
    <section className="my-stories-shell">
      <div className="my-stories-tabs ad-tabs">
        <button
          type="button"
          className={storyState === "active" ? "ad-tab on" : "ad-tab"}
          onClick={() => setStoryState("active")}
        >
          Faol
        </button>
        <button
          type="button"
          className={storyState === "archived" ? "ad-tab on" : "ad-tab"}
          onClick={() => setStoryState("archived")}
        >
          Arxiv
        </button>
      </div>
      <div className="my-stories-grid">
        {visible.length ? (
          visible.map((row, index) => {
            const id = recordId(row, index);
            const archived = ["archived", "expired"].includes(
              recordText(row, "state", "status"),
            );
            return (
              <article className="my-story-card" data-my-story-id={id} key={String(id)}>
                <div className="my-story-thumb">
                  {recordText(row, "thumbnail_url", "media_url") ? (
                    <img
                      src={recordText(row, "thumbnail_url", "media_url")}
                      alt="Istoriya muqovasi"
                    />
                  ) : (
                    <span className="my-story-thumb-fallback">Media topilmadi</span>
                  )}
                  {recordText(row, "media_type") === "video" && (
                    <span className="my-story-video-badge">▶ Video</span>
                  )}
                </div>
                <div className="my-story-main">
                  <div className="my-story-caption">
                    {recordText(row, "caption") || "Matnsiz istoriya"}
                  </div>
                  <div className="my-story-meta">
                    {new Date(Number(row.created_at ?? 0) * 1000).toLocaleString(
                      "uz-UZ",
                      {
                        day: "2-digit",
                        month: "2-digit",
                        year: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      },
                    )}
                    <br />
                    👁 {Number(row.view_count ?? 0)} ko‘rish
                  </div>
                  <span
                    className={archived ? "my-story-state archived" : "my-story-state"}
                  >
                    {archived ? "Arxiv" : `Faol · ${storyRemaining(row.expires_at)}`}
                  </span>
                  <div className="my-story-actions">
                    <button type="button" onClick={() => setStoryViewer(row)}>
                      Ko‘rish
                    </button>
                    <button
                      type="button"
                      className="danger"
                      onClick={() =>
                        setConfirm({
                          id,
                          title: "Istoriyani o‘chirish",
                          text: "Istoriya va uning media fayli butunlay o‘chiriladi.",
                          ok: "O‘chirish",
                        })
                      }
                    >
                      O‘chirish
                    </button>
                  </div>
                </div>
              </article>
            );
          })
        ) : storyState === "archived" ? (
          <div className="empty my-stories-status">
            <h3>Arxiv hozircha bo‘sh</h3>
            <p>24 soati tugagan istoriyalar shu yerda saqlanadi.</p>
          </div>
        ) : (
          <div className="empty my-stories-status">
            <h3>Hali istoriya joylamagansiz</h3>
            <p>Rasm yoki 1 daqiqagacha video joylang.</p>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => begin({ status: "active" })}
            >
              Istoriya joylash
            </button>
          </div>
        )}
      </div>
      {openForm && (
        <div className="story-layer on">
          <div
            className="story-sheet"
            role="dialog"
            aria-modal="true"
            aria-label="Istoriya joylash"
          >
            <div className="story-sheet-head">
              <div className="story-sheet-title">Istoriya joylash</div>
              <button
                type="button"
                className="story-text-btn"
                onClick={() => setOpenForm(false)}
              >
                Yopish
              </button>
            </div>
            <input
              type="file"
              hidden
              id="reactStoryFileInput"
              aria-label="Istoriya media fayli"
              accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm"
              onChange={(event) => {
                const file = event.currentTarget.files?.[0] ?? null;
                if (
                  file &&
                  ![
                    "image/jpeg",
                    "image/png",
                    "image/webp",
                    "video/mp4",
                    "video/quicktime",
                    "video/webm",
                  ].includes(file.type)
                ) {
                  setStoryFile(null);
                  setValidationError("Rasm yoki video tanlang.");
                  event.currentTarget.value = "";
                  return;
                }
                if (file?.type.startsWith("image/") && file.size > 10 * 1024 * 1024) {
                  setStoryFile(null);
                  setValidationError("Rasm hajmi 10 MB dan oshmasin.");
                  event.currentTarget.value = "";
                  return;
                }
                if (file?.type.startsWith("video/") && file.size > 100 * 1024 * 1024) {
                  setStoryFile(null);
                  setValidationError("Video hajmi 100 MB dan oshmasin.");
                  event.currentTarget.value = "";
                  return;
                }
                setStoryFile(file);
                setValidationError("");
              }}
            />
            <div className="story-source-grid">
              <button
                type="button"
                className="story-source-btn"
                onClick={() => {
                  const input = document.getElementById("reactStoryFileInput");
                  input?.setAttribute("capture", "environment");
                  input?.click();
                }}
              >
                Kamera orqali<small>Hozir rasm yoki video oling</small>
              </button>
              <button
                type="button"
                className="story-source-btn"
                onClick={() => {
                  const input = document.getElementById("reactStoryFileInput");
                  input?.removeAttribute("capture");
                  input?.click();
                }}
              >
                Galereyadan<small>Telefondagi rasm yoki videoni tanlang</small>
              </button>
            </div>
            {storyFile && (
              <div className="story-compose-fields on">
                <div className="idesc">{storyFile.name}</div>
                <label className="field">
                  Qisqa matn — ixtiyoriy
                  <textarea
                    className="textarea"
                    maxLength={200}
                    placeholder="Istoriya haqida qisqa yozing"
                    value={recordText(draft, "caption")}
                    onChange={(event) =>
                      setDraft({ ...draft, caption: event.currentTarget.value })
                    }
                  />
                  <span className="idesc">
                    {recordText(draft, "caption").length} / 200
                  </span>
                </label>
              </div>
            )}
            {validationError && (
              <div className="story-upload-error on" role="alert">
                {validationError}
              </div>
            )}
            <button
              type="button"
              className="btn btn-primary btn-block"
              disabled={actions.busy}
              onClick={async () => {
                if (!storyFile) {
                  setValidationError("Avval rasm yoki video tanlang.");
                  return;
                }
                await actions.create("stories", {
                  caption: recordText(draft, "caption").trim(),
                  media_file: storyFile.name,
                  media_type: storyFile.type.startsWith("video/") ? "video" : "photo",
                  status: "active",
                });
                setStoryFile(null);
                setOpenForm(false);
              }}
            >
              Joylash
            </button>
          </div>
        </div>
      )}
      {storyViewer && (
        <div className="story-viewer on">
          <div
            className="story-stage"
            role="dialog"
            aria-modal="true"
            aria-label="Istoriya"
          >
            <div className="story-viewer-media">
              {recordText(storyViewer, "media_type") === "video" ? (
                <video src={recordText(storyViewer, "media_url")} controls />
              ) : (
                <img
                  src={recordText(storyViewer, "media_url", "thumbnail_url")}
                  alt="Istoriya"
                />
              )}
            </div>
            <button
              type="button"
              className="story-viewer-close"
              aria-label="Istoriyani yopish"
              onClick={() => setStoryViewer(null)}
            >
              ×
            </button>
            <div className="story-viewer-caption">
              {recordText(storyViewer, "caption")}
            </div>
          </div>
        </div>
      )}
      {dialog}
    </section>
  );
}
