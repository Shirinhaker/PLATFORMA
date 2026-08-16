import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import type { ApiClient } from "../api/client";
import type { UserProfile, UserProfilePatch } from "../api/types";
import {
  avatarImageStyle,
  normalizedAvatarCrop,
  UserAvatarCropV1656,
  type AvatarCrop,
} from "./UserAvatarCrop";
import "./UserProfile.css";

type EditorApi = Pick<
  ApiClient,
  "updateUserProfile" | "createUploadGrant" | "uploadGrantedFile" | "attachUserAvatar"
>;

type Props = {
  api: EditorApi;
  profile: UserProfile;
  onBack(): void;
  onFollowing(): void;
  onFollowers(): void;
  onProfile(profile: UserProfile): void;
};

type QrCtor = new (
  element: HTMLElement,
  options: {
    text: string;
    width: number;
    height: number;
    colorDark: string;
    colorLight: string;
  },
) => unknown;

const IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp", "image/gif"]);
const MAX_IMAGE_BYTES = 8 * 1024 * 1024;
const PATCH_FIELDS = ["name", "phone", "public_username"] as const;

function errorText(reason: unknown) {
  return reason instanceof Error ? reason.message : "So‘rov bajarilmadi.";
}

function locationText(profile: UserProfile) {
  return (
    [profile.district, profile.region].filter(Boolean).join(", ") ||
    "Joylashuv kiritilmagan"
  );
}

function pageLink(profile: UserProfile) {
  const url = new URL(window.location.origin);
  url.searchParams.set(
    "user",
    profile.public_id || profile.public_username || String(profile.account_id),
  );
  return url.toString();
}

function initials(name: string) {
  const words = name.trim().split(/\s+/).filter(Boolean);
  return words.length
    ? words
        .slice(0, 2)
        .map((word) => word[0]?.toUpperCase())
        .join("")
    : "🙂";
}

function QrCode({ value }: { value: string }) {
  const root = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const node = root.current;
    if (!node) return;
    node.replaceChildren();
    const QRCode = (window as unknown as { QRCode?: QrCtor }).QRCode;
    if (!QRCode) {
      node.textContent = "QR kod yuklanmadi";
      return;
    }
    new QRCode(node, {
      text: value,
      width: 180,
      height: 180,
      colorDark: "#081c17",
      colorLight: "#ffffff",
    });
  }, [value]);
  return (
    <div
      ref={root}
      className="user-profile-share-v1656__qr"
      aria-label="Foydalanuvchi sahifasi QR kodi"
    />
  );
}

export function UserProfileEditorV1656({
  api,
  profile,
  onBack,
  onFollowing,
  onFollowers,
  onProfile,
}: Props) {
  const [draft, setDraft] = useState(profile);
  const [baseline, setBaseline] = useState(profile);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [cropOpen, setCropOpen] = useState(false);
  const [lightbox, setLightbox] = useState(false);
  const [copyLabel, setCopyLabel] = useState("Nusxa");
  const fileInput = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    setDraft(profile);
    setBaseline(profile);
  }, [profile]);

  const link = useMemo(
    () => pageLink(draft),
    [draft.account_id, draft.public_id, draft.public_username],
  );
  const crop = normalizedAvatarCrop({
    x: draft.avatar_x,
    y: draft.avatar_y,
    zoom: draft.avatar_zoom,
  });

  function apply(value: UserProfile) {
    setDraft(value);
    setBaseline(value);
    onProfile(value);
  }

  function field<K extends keyof UserProfile>(name: K, value: UserProfile[K]) {
    setSaved(false);
    setDraft((current) => ({ ...current, [name]: value }));
  }

  function setCrop(value: AvatarCrop) {
    setSaved(false);
    setDraft((current) => ({
      ...current,
      avatar_x: value.x,
      avatar_y: value.y,
      avatar_zoom: value.zoom,
    }));
  }

  function validImage(file: File) {
    if (!IMAGE_TYPES.has(file.type)) {
      setError("Profil rasmi JPG, PNG, WEBP yoki GIF formatida bo‘lsin.");
      return false;
    }
    if (file.size < 1 || file.size > MAX_IMAGE_BYTES) {
      setError("Profil rasmi hajmi 8 MB dan oshmasin.");
      return false;
    }
    return true;
  }

  async function uploadAvatar(file: File) {
    if (!validImage(file)) return;
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      const grant = await api.createUploadGrant({
        purpose: "avatar",
        filename: file.name,
        content_type: file.type,
        size_bytes: file.size,
      });
      await api.uploadGrantedFile(grant, file);
      apply(
        await api.attachUserAvatar({
          object_key: grant.object_key,
          x: 50,
          y: 50,
          zoom: 1,
        }),
      );
      setCropOpen(true);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function saveCrop() {
    if (!draft.avatar_object_key) return;
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      apply(
        await api.attachUserAvatar({
          object_key: draft.avatar_object_key,
          x: crop.x,
          y: crop.y,
          zoom: crop.zoom,
        }),
      );
      setCropOpen(false);
      setSaved(true);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const patch: UserProfilePatch = {};
    for (const name of PATCH_FIELDS) {
      if (draft[name] !== baseline[name]) {
        (patch as Record<string, unknown>)[name] = draft[name];
      }
    }
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      const value = Object.keys(patch).length
        ? await api.updateUserProfile(patch)
        : draft;
      apply(value);
      setSaved(true);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(link);
      setCopyLabel("Nusxa olindi ✅");
    } catch {
      setCopyLabel("Qo‘lda nusxalang");
    }
  }

  return (
    <main className="user-profile-editor-v1656">
      <header className="user-profile-editor-v1656__head">
        <button type="button" aria-label="Kabinetga qaytish" onClick={onBack}>
          ‹
        </button>
        <h1>Profilim</h1>
      </header>

      <section className="user-profile-card-v1656">
        <button
          type="button"
          className="user-profile-card-v1656__avatar"
          aria-label={draft.avatar_url ? "Profil rasmini kattalashtirish" : undefined}
          disabled={!draft.avatar_url}
          onClick={() => setLightbox(Boolean(draft.avatar_url))}
        >
          {draft.avatar_url ? (
            <img
              src={draft.avatar_url}
              alt={`${draft.name || "Foydalanuvchi"} profil rasmi`}
              style={avatarImageStyle(crop)}
            />
          ) : (
            initials(draft.name)
          )}
        </button>
        <div className="user-profile-card-v1656__main">
          <strong>{draft.name || "Foydalanuvchi"}</strong>
          <span>{locationText(draft)}</span>
          <div>
            <button type="button" onClick={onFollowers}>
              {draft.followers_count || 0} obunachi
            </button>
            <button type="button" className="following" onClick={onFollowing}>
              {draft.following_count || 0} obuna
            </button>
          </div>
        </div>
        <button
          type="button"
          className="user-profile-card-v1656__camera"
          aria-label="Profil rasmini yuklash"
          title="Profil rasmini yuklash"
          disabled={busy}
          onClick={() => fileInput.current?.click()}
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <path d="M14.5 4l1.5 2H20a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l1.5-2z" />
            <circle cx="12" cy="13" r="3.5" />
          </svg>
        </button>
        <input
          ref={fileInput}
          type="file"
          hidden
          accept="image/jpeg,image/png,image/webp,image/gif"
          onChange={(event) => {
            const file = event.currentTarget.files?.[0];
            event.currentTarget.value = "";
            if (file) void uploadAvatar(file);
          }}
        />
      </section>

      {draft.avatar_url ? (
        <button
          type="button"
          className="btn btn-outline btn-block user-profile-editor-v1656__adjust"
          onClick={() => setCropOpen((current) => !current)}
        >
          🖼 Rasm joylashuvini sozlash
        </button>
      ) : null}

      {cropOpen && draft.avatar_url ? (
        <UserAvatarCropV1656
          alt="Profil rasmi kesimi"
          busy={busy}
          src={draft.avatar_url}
          value={crop}
          onChange={setCrop}
          onSave={() => void saveCrop()}
        />
      ) : null}

      <form className="user-profile-form-v1656" onSubmit={save}>
        <label>
          Ism familiya
          <input
            className="input"
            required
            placeholder="Ismingiz"
            value={draft.name}
            onChange={(event) => field("name", event.currentTarget.value)}
          />
        </label>
        <label>
          Telefon
          <input
            className="input"
            type="tel"
            inputMode="tel"
            placeholder="+998 __ ___ __ __"
            value={draft.phone}
            onChange={(event) => field("phone", event.currentTarget.value)}
          />
        </label>
        <label>
          Username (sahifa manzili)
          <span className="user-profile-form-v1656__username">
            <b>@</b>
            <input
              className="input"
              aria-label="Username (sahifa manzili)"
              autoComplete="off"
              placeholder="ismingiz"
              value={draft.public_username}
              onChange={(event) =>
                field(
                  "public_username",
                  event.currentTarget.value
                    .toLowerCase()
                    .replace(/^@+/, "")
                    .replace(/[^a-z0-9_]/g, ""),
                )
              }
            />
          </span>
          <small>
            Kichik lotin harflari, raqam va _ (3–20 belgi). Do‘stlaringiz sizni shu nom
            orqali topadi. Ixtiyoriy.
          </small>
        </label>

        <section className="user-profile-share-v1656">
          <strong>🔗 Sahifa havolasi</strong>
          <p>Shu havola yoki QR orqali do‘stlaringiz sahifangizga o‘tadi.</p>
          <div>
            <input
              aria-label="Foydalanuvchi sahifasi havolasi"
              className="input"
              readOnly
              value={link}
            />
            <button type="button" className="mini-btn" onClick={() => void copyLink()}>
              {copyLabel}
            </button>
          </div>
          <QrCode value={link} />
        </section>

        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}
        {saved ? (
          <p className="form-success" role="status">
            Saqlandi ✅
          </p>
        ) : null}
        <button type="submit" className="btn btn-primary btn-block" disabled={busy}>
          {busy ? "Saqlanmoqda…" : "Saqlash"}
        </button>
      </form>

      {lightbox && draft.avatar_url ? (
        <button
          type="button"
          className="user-profile-lightbox-v1656"
          aria-label="Kattalashtirilgan profil rasmini yopish"
          onClick={() => setLightbox(false)}
        >
          <span>
            <img
              src={draft.avatar_url}
              alt={draft.name}
              style={avatarImageStyle(crop)}
            />
          </span>
        </button>
      ) : null}
    </main>
  );
}
