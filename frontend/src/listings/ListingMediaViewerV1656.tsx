import { useEffect } from "react";


type Props = {
  media: { type: "photo" | "video"; url: string } | null;
  onClose(): void;
};


export function ListingMediaViewerV1656({ media, onClose }: Props) {
  useEffect(() => {
    if (!media) return undefined;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [media, onClose]);

  if (!media) return null;

  return (
    <div
      aria-label="E'lon mediasi"
      aria-modal="true"
      className="image-viewer on"
      role="dialog"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <button
        aria-label="Yopish"
        className="image-viewer-close"
        type="button"
        onClick={onClose}
      >
        ×
      </button>
      <div className="image-viewer-frame">
        {media.type === "video" ? (
          <video autoPlay controls playsInline preload="metadata" src={media.url} />
        ) : (
          <img alt="Kattalashtirilgan rasm" src={media.url} />
        )}
      </div>
    </div>
  );
}
