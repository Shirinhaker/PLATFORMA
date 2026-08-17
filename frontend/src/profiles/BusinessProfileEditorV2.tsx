import { useEffect, useMemo, useRef, useState } from "react";

import type { ApiClient } from "../api/client";
import type { BusinessProfile, BusinessProfilePatch } from "../api/types";
import { directionActivities, initials } from "./business-profile-config";
import { BusinessLocationPickerView } from "./BusinessLocationPickerView";
import { BusinessProfileEditorForm } from "./BusinessProfileEditorForm";
import {
  IMAGE_TYPES,
  MAX_IMAGE_BYTES,
  PATCH_FIELDS,
  errorText,
  finite,
  parseHours,
  shopLink,
  workHours,
  type Hours,
  type Point,
} from "./BusinessProfileEditorShared";
import "./BusinessProfileEditor.css";

type EditorApi = Pick<
  ApiClient,
  | "updateBusinessProfile"
  | "createUploadGrant"
  | "uploadGrantedFile"
  | "attachBusinessLogo"
> &
  Partial<Pick<ApiClient, "attachBusinessPaymentQr" | "reverseGeocode">>;

type Props = {
  api: EditorApi;
  profile: BusinessProfile;
  onBack: () => void;
  onProfile: (profile: BusinessProfile) => void;
  onOpenOnline?: (view: "followers" | "following") => void;
};

export function BusinessProfileEditorV2({
  api,
  profile,
  onBack,
  onProfile,
  onOpenOnline,
}: Props) {
  const [draft, setDraft] = useState(profile);
  const [baseline, setBaseline] = useState(profile);
  const [hours, setHours] = useState(() => parseHours(profile.work_hours));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [crop, setCrop] = useState(false);
  const [mapOpen, setMapOpen] = useState(false);
  const [lightbox, setLightbox] = useState(false);
  const [copyText, setCopyText] = useState("Nusxa");
  const logoInput = useRef<HTMLInputElement | null>(null);
  const paymentInput = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    setDraft(profile);
    setBaseline(profile);
    setHours(parseHours(profile.work_hours));
  }, [profile]);

  const activities = useMemo(
    () => directionActivities(draft.direction, draft.activity_type),
    [draft.direction, draft.activity_type],
  );
  const link = useMemo(
    () => shopLink(draft),
    [draft.account_id, draft.public_username],
  );
  const point =
    draft.latitude !== null && draft.longitude !== null
      ? { latitude: draft.latitude, longitude: draft.longitude }
      : null;
  const logoStyle = {
    objectPosition: `${finite(draft.logo_x, 50)}% ${finite(draft.logo_y, 50)}%`,
    transform: `scale(${Math.min(5, Math.max(1, finite(draft.logo_zoom, 1)))})`,
  };

  function field<K extends keyof BusinessProfile>(name: K, value: BusinessProfile[K]) {
    setSaved(false);
    setDraft((current) => ({ ...current, [name]: value }));
  }

  function apply(value: BusinessProfile) {
    setDraft(value);
    setBaseline(value);
    setHours(parseHours(value.work_hours));
    onProfile(value);
  }

  function validImage(file: File) {
    if (!IMAGE_TYPES.has(file.type)) {
      setError("Faqat JPEG, PNG, WEBP yoki GIF rasm yuklang.");
      return false;
    }
    if (file.size < 1 || file.size > MAX_IMAGE_BYTES) {
      setError("Rasm hajmi 8 MB dan oshmasin.");
      return false;
    }
    return true;
  }

  async function uploadLogo(file: File) {
    if (!validImage(file)) return;
    setBusy(true);
    setError("");
    try {
      const grant = await api.createUploadGrant({
        purpose: "logo",
        filename: file.name,
        content_type: file.type,
        size_bytes: file.size,
      });
      await api.uploadGrantedFile(grant, file);
      apply(
        await api.attachBusinessLogo({
          object_key: grant.object_key,
          x: draft.logo_x,
          y: draft.logo_y,
          zoom: draft.logo_zoom,
        }),
      );
      setCrop(true);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function uploadPaymentQr(file: File) {
    if (!api.attachBusinessPaymentQr) {
      setError("To‘lov QR yuklash backendda yoqilmagan.");
      return;
    }
    if (!validImage(file)) return;
    setBusy(true);
    setError("");
    try {
      const grant = await api.createUploadGrant({
        purpose: "payment_qr",
        filename: file.name,
        content_type: file.type,
        size_bytes: file.size,
      });
      await api.uploadGrantedFile(grant, file);
      apply(await api.attachBusinessPaymentQr({ object_key: grant.object_key }));
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function saveCrop() {
    if (!draft.logo_object_key) return;
    setBusy(true);
    setError("");
    try {
      apply(
        await api.attachBusinessLogo({
          object_key: draft.logo_object_key,
          x: draft.logo_x,
          y: draft.logo_y,
          zoom: draft.logo_zoom,
        }),
      );
      setCrop(false);
      setSaved(true);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if ((hours.from && !hours.to) || (!hours.from && hours.to)) {
      setError("Ish vaqtining boshlanish va tugash vaqtini birga belgilang.");
      return;
    }
    if (!draft.name.trim()) {
      setError("Biznes nomini kiriting.");
      return;
    }
    if (!draft.direction) {
      setError("Faoliyat yo'nalishini tanlang.");
      return;
    }
    if (!draft.activity_type) {
      setError("Faoliyat turini tanlang.");
      return;
    }

    const patch: BusinessProfilePatch = {};
    for (const name of PATCH_FIELDS) {
      if (draft[name] !== baseline[name]) {
        (patch as Record<string, unknown>)[name] = draft[name];
      }
    }
    const nextHours = workHours(baseline.work_hours, hours);
    if (JSON.stringify(nextHours) !== JSON.stringify(baseline.work_hours)) {
      patch.work_hours = nextHours;
    }

    setBusy(true);
    setError("");
    setSaved(false);
    try {
      const value = Object.keys(patch).length
        ? await api.updateBusinessProfile(patch)
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
      setCopyText("Nusxalandi");
      window.setTimeout(() => setCopyText("Nusxa"), 1200);
    } catch {
      setError("Havolani nusxalab bo‘lmadi.");
    }
  }

  async function savePickedLocation(next: Point) {
    const localPatch = {
      latitude: next.latitude,
      longitude: next.longitude,
      map_visible: true,
    };
    setDraft((current) => ({ ...current, ...localPatch }));
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      let address = draft.address;
      if (api.reverseGeocode) {
        try {
          const geocode = await api.reverseGeocode(next.latitude, next.longitude);
          address = geocode.address || address;
        } catch {
          // Monolit kabi geokodlash ishlamasa ham koordinata saqlanadi.
        }
      }
      apply(
        await api.updateBusinessProfile({
          ...localPatch,
          address,
        }),
      );
      setSaved(true);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
      setMapOpen(false);
    }
  }

  if (mapOpen) {
    return (
      <BusinessLocationPickerView
        prefix="bp"
        value={point}
        onCancel={() => setMapOpen(false)}
        onConfirm={savePickedLocation}
      />
    );
  }

  return (
    <main className="business-profile-editor form-wrap">
      <header className="business-profile-editor__heading">
        <div>
          <p>Profil</p>
          <h1>Profil / Mening sahifam</h1>
        </div>
        <button type="button" className="button-secondary" onClick={onBack}>
          Kabinetga qaytish
        </button>
      </header>

      <section className="business-profile-card user-profile-card koprik-profile-surface">
        <button
          type="button"
          className="business-profile-card__logo user-profile-avatar business-profile-avatar"
          aria-label="Biznes rasmini kattalashtirish"
          onClick={() => draft.logo_url && setLightbox(true)}
        >
          {draft.logo_url ? (
            <img src={draft.logo_url} alt="" style={logoStyle} />
          ) : (
            <span>{initials(draft.name)}</span>
          )}
        </button>
        <div className="business-profile-card__main user-profile-main">
          <h2 className="user-profile-name">{draft.name || "Biznes"}</h2>
          <p className="user-profile-location">
            {draft.direction || "Yo'nalish tanlanmagan"}
            {draft.activity_type ? ` · ${draft.activity_type}` : ""}
          </p>
          <div className="user-profile-stats">
            <button
              type="button"
              className="user-profile-stat"
              onClick={() => onOpenOnline?.("followers")}
            >
              {draft.followers_count ?? 0} obunachi
            </button>
            <button
              type="button"
              className="user-profile-stat following"
              onClick={() => onOpenOnline?.("following")}
            >
              {draft.following_count ?? 0} obuna
            </button>
          </div>
        </div>
        <button
          type="button"
          className="business-profile-card__camera user-avatar-camera"
          aria-label="Biznes rasmini yuklash"
          disabled={busy}
          onClick={() => logoInput.current?.click()}
        >
          📷
        </button>
        <input
          ref={logoInput}
          type="file"
          hidden
          aria-label="Logotip"
          accept="image/jpeg,image/png,image/webp,image/gif"
          onChange={(event) => {
            const file = event.currentTarget.files?.[0];
            event.currentTarget.value = "";
            if (file) void uploadLogo(file);
          }}
        />
      </section>

      <BusinessProfileEditorForm
        api={api}
        draft={draft}
        hours={hours}
        activities={activities}
        point={point}
        logoStyle={logoStyle}
        paymentInput={paymentInput}
        busy={busy}
        error={error}
        saved={saved}
        crop={crop}
        lightbox={lightbox}
        link={link}
        copyText={copyText}
        field={field}
        setDraft={setDraft}
        setHours={setHours}
        setSaved={setSaved}
        setCrop={setCrop}
        setMapOpen={setMapOpen}
        setLightbox={setLightbox}
        onSave={save}
        onSaveCrop={saveCrop}
        onCopyLink={copyLink}
        onUploadPaymentQr={uploadPaymentQr}
        onApply={apply}
        onError={setError}
      />
    </main>
  );
}
