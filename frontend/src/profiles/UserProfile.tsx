import { useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  SessionIdentity,
  UserProfile as UserProfileData,
  UserProfilePatch,
} from "../api/types";


export type UserProfileApi = Pick<
  ApiClient,
  | "getUserProfile"
  | "updateUserProfile"
  | "createUploadGrant"
  | "uploadGrantedFile"
  | "attachUserAvatar"
  | "logout"
>;

type Props = {
  api: UserProfileApi;
  identity: SessionIdentity;
  onLogout: () => void;
};

const IMAGE_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/gif",
]);
const MAX_IMAGE_BYTES = 8 * 1024 * 1024;
const EDITABLE_FIELDS = [
  "name",
  "phone",
  "public_username",
  "region",
  "district",
  "mahalla",
  "latitude",
  "longitude",
  "location_exact",
] as const;


function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}


export function UserProfile({ api, identity, onLogout }: Props) {
  const [profile, setProfile] = useState<UserProfileData | null>(null);
  const [baseline, setBaseline] = useState<UserProfileData | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  async function load() {
    const value = await api.getUserProfile();
    setProfile(value);
    setBaseline(value);
  }

  useEffect(() => {
    let active = true;
    api.getUserProfile()
      .then((value) => {
        if (!active) return;
        setProfile(value);
        setBaseline(value);
      })
      .catch((reason) => {
        if (active) setError(message(reason));
      });
    return () => {
      active = false;
    };
  }, [api]);

  function setField<K extends keyof UserProfileData>(
    field: K,
    value: UserProfileData[K],
  ) {
    setSaved(false);
    setProfile((current) => (
      current ? { ...current, [field]: value } : current
    ));
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!profile || !baseline) return;
    const patch: UserProfilePatch = {};
    for (const field of EDITABLE_FIELDS) {
      if (profile[field] !== baseline[field]) {
        (patch as Record<string, unknown>)[field] = profile[field];
      }
    }
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      let value = Object.keys(patch).length
        ? await api.updateUserProfile(patch)
        : profile;
      const cropChanged = (
        profile.avatar_x !== baseline.avatar_x
        || profile.avatar_y !== baseline.avatar_y
        || profile.avatar_zoom !== baseline.avatar_zoom
      );
      if (cropChanged && profile.avatar_object_key) {
        value = await api.attachUserAvatar({
          object_key: profile.avatar_object_key,
          x: profile.avatar_x,
          y: profile.avatar_y,
          zoom: profile.avatar_zoom,
        });
      }
      setProfile(value);
      setBaseline(value);
      setSaved(true);
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  async function upload(file: File) {
    if (!IMAGE_TYPES.has(file.type)) {
      setError("Faqat JPEG, PNG, WEBP yoki GIF rasm yuklang.");
      return;
    }
    if (file.size < 1 || file.size > MAX_IMAGE_BYTES) {
      setError("Rasm hajmi 8 MB dan oshmasin.");
      return;
    }
    if (!profile) return;
    setBusy(true);
    setError("");
    try {
      const grant = await api.createUploadGrant({
        purpose: "avatar",
        filename: file.name,
        content_type: file.type,
        size_bytes: file.size,
      });
      await api.uploadGrantedFile(grant, file);
      await api.attachUserAvatar({
        object_key: grant.object_key,
        x: profile.avatar_x,
        y: profile.avatar_y,
        zoom: profile.avatar_zoom,
      });
      await load();
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    setBusy(true);
    setError("");
    try {
      await api.logout();
      onLogout();
    } catch (reason) {
      setError(message(reason));
      setBusy(false);
    }
  }

  if (!profile) {
    return (
      <main className="profile-shell">
        {error ? <p role="alert">{error}</p> : "Profil yuklanmoqda…"}
      </main>
    );
  }

  return (
    <main className="profile-shell">
      <header className="profile-heading">
        <div>
          <p className="session-panel__eyebrow">{identity.login}</p>
          <h1>Oddiy kabinet</h1>
        </div>
        <button type="button" className="button-secondary" onClick={logout}>
          Chiqish
        </button>
      </header>
      <form className="profile-form" onSubmit={save}>
        <label>Ism<input required value={profile.name} onChange={(event) => setField("name", event.currentTarget.value)} /></label>
        <label>Telefon<input type="tel" value={profile.phone} onChange={(event) => setField("phone", event.currentTarget.value)} /></label>
        <label>Ochiq username<input value={profile.public_username} onChange={(event) => setField("public_username", event.currentTarget.value)} /></label>
        <label>Viloyat<input value={profile.region} onChange={(event) => setField("region", event.currentTarget.value)} /></label>
        <label>Tuman<input value={profile.district} onChange={(event) => setField("district", event.currentTarget.value)} /></label>
        <label>Mahalla<input value={profile.mahalla} onChange={(event) => setField("mahalla", event.currentTarget.value)} /></label>
        <label>Kenglik<input type="number" step="any" value={profile.latitude ?? ""} onChange={(event) => setField("latitude", event.currentTarget.value === "" ? null : Number(event.currentTarget.value))} /></label>
        <label>Uzunlik<input type="number" step="any" value={profile.longitude ?? ""} onChange={(event) => setField("longitude", event.currentTarget.value === "" ? null : Number(event.currentTarget.value))} /></label>
        <label className="checkbox-field"><input type="checkbox" checked={profile.location_exact} onChange={(event) => setField("location_exact", event.currentTarget.checked)} />Joylashuv aniq</label>
        <fieldset>
          <legend>Avatar kesimi</legend>
          <label>X<input type="number" min="0" max="100" value={profile.avatar_x} onChange={(event) => setField("avatar_x", Number(event.currentTarget.value))} /></label>
          <label>Y<input type="number" min="0" max="100" value={profile.avatar_y} onChange={(event) => setField("avatar_y", Number(event.currentTarget.value))} /></label>
          <label>Zoom<input type="number" min="1" max="5" step="0.1" value={profile.avatar_zoom} onChange={(event) => setField("avatar_zoom", Number(event.currentTarget.value))} /></label>
        </fieldset>
        <label>Avatar<input type="file" accept="image/jpeg,image/png,image/webp,image/gif" disabled={busy} onChange={(event) => { const file = event.currentTarget.files?.[0]; if (file) void upload(file); }} /></label>
        {error && <p className="form-error" role="alert">{error}</p>}
        {saved && <p className="form-success" role="status">Saqlandi</p>}
        <button type="submit" disabled={busy}>Saqlash</button>
      </form>
    </main>
  );
}
