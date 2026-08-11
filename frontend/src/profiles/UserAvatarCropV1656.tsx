import { useEffect, useRef, type CSSProperties, type PointerEvent } from "react";


export type AvatarCrop = {
  x: number;
  y: number;
  zoom: number;
};

type DragState = AvatarCrop & {
  pointerId: number;
  clientX: number;
  clientY: number;
};

type Props = {
  alt: string;
  busy: boolean;
  src: string;
  value: AvatarCrop;
  onChange(value: AvatarCrop): void;
  onSave(): void;
};


function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export function normalizedAvatarCrop(value: Partial<AvatarCrop>): AvatarCrop {
  return {
    x: clamp(Number.isFinite(value.x) ? Number(value.x) : 50, 0, 100),
    y: clamp(Number.isFinite(value.y) ? Number(value.y) : 50, 0, 100),
    zoom: clamp(Number.isFinite(value.zoom) ? Number(value.zoom) : 1, 1, 3),
  };
}

export function avatarImageStyle(value: Partial<AvatarCrop>): CSSProperties {
  const crop = normalizedAvatarCrop(value);
  return {
    objectPosition: `${crop.x}% ${crop.y}%`,
    transform: `scale(${crop.zoom})`,
  };
}


export function UserAvatarCropV1656({
  alt,
  busy,
  src,
  value,
  onChange,
  onSave,
}: Props) {
  const stage = useRef<HTMLDivElement | null>(null);
  const drag = useRef<DragState | null>(null);
  const current = useRef(normalizedAvatarCrop(value));

  useEffect(() => {
    current.current = normalizedAvatarCrop(value);
  }, [value.x, value.y, value.zoom]);

  function begin(event: PointerEvent<HTMLDivElement>) {
    const crop = current.current;
    drag.current = {
      ...crop,
      pointerId: event.pointerId,
      clientX: event.clientX,
      clientY: event.clientY,
    };
    event.currentTarget.setPointerCapture?.(event.pointerId);
    event.preventDefault();
  }

  function move(event: PointerEvent<HTMLDivElement>) {
    const started = drag.current;
    const node = stage.current;
    if (!started || started.pointerId !== event.pointerId || !node) return;
    const bounds = node.getBoundingClientRect();
    const next = normalizedAvatarCrop({
      x: started.x
        - ((event.clientX - started.clientX) / Math.max(1, bounds.width))
          * 100 / started.zoom,
      y: started.y
        - ((event.clientY - started.clientY) / Math.max(1, bounds.height))
          * 100 / started.zoom,
      zoom: started.zoom,
    });
    current.current = next;
    onChange(next);
    event.preventDefault();
  }

  function stop(event: PointerEvent<HTMLDivElement>) {
    if (drag.current?.pointerId === event.pointerId) drag.current = null;
  }

  return (
    <section className="user-avatar-crop-v1656" aria-label="Rasm joylashuvini sozlash">
      <div
        ref={stage}
        className="user-avatar-crop-v1656__stage"
        onPointerDown={begin}
        onPointerMove={move}
        onPointerUp={stop}
        onPointerCancel={stop}
      >
        <img alt={alt} draggable={false} src={src} style={avatarImageStyle(value)} />
      </div>
      <label>
        Kattalashtirish
        <input
          type="range"
          min="1"
          max="3"
          step="0.05"
          value={normalizedAvatarCrop(value).zoom}
          onChange={(event) => onChange(normalizedAvatarCrop({
            ...value,
            zoom: Number(event.currentTarget.value),
          }))}
        />
      </label>
      <p>Rasmni barmoq bilan surib, ko‘rinadigan qismini belgilang.</p>
      <div className="user-avatar-crop-v1656__actions">
        <button
          type="button"
          className="btn btn-outline"
          onClick={() => onChange({ x: 50, y: 50, zoom: 1 })}
        >
          Markazga
        </button>
        <button
          type="button"
          className="btn btn-primary"
          aria-label="Rasm joylashuvini saqlash"
          disabled={busy}
          onClick={onSave}
        >
          {busy ? "Saqlanmoqda…" : "Saqlash"}
        </button>
      </div>
    </section>
  );
}
