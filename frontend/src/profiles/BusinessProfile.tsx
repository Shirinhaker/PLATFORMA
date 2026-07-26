import { useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  BusinessProfile as BusinessProfileData,
  BusinessProfilePatch,
  SessionIdentity,
} from "../api/types";


export type BusinessProfileApi = Pick<
  ApiClient,
  | "getBusinessProfile"
  | "updateBusinessProfile"
  | "createUploadGrant"
  | "uploadGrantedFile"
  | "attachBusinessLogo"
  | "logout"
>;

type Props = {
  api: BusinessProfileApi;
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
  "description",
  "public_username",
  "direction",
  "activity_type",
  "address",
  "latitude",
  "longitude",
  "pay_card",
  "pay_holder",
  "director",
  "tax_id",
] as const;


function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}


export function BusinessProfile({ api, identity, onLogout }: Props) {
  const [profile, setProfile] = useState<BusinessProfileData | null>(null);
  const [baseline, setBaseline] = useState<BusinessProfileData | null>(null);
  const [workHours, setWorkHours] = useState("{}");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  function applyLoaded(value: BusinessProfileData) {
    setProfile(value);
    setBaseline(value);
    setWorkHours(JSON.stringify(value.work_hours, null, 2));
  }

  async function load() {
    applyLoaded(await api.getBusinessProfile());
  }

  useEffect(() => {
    let active = true;
    api.getBusinessProfile()
      .then((value) => {
        if (active) applyLoaded(value);
      })
      .catch((reason) => {
        if (active) setError(message(reason));
      });
    return () => {
      active = false;
    };
  }, [api]);

  function setField<K extends keyof BusinessProfileData>(
    field: K,
    value: BusinessProfileData[K],
  ) {
    setSaved(false);
    setProfile((current) => (
      current ? { ...current, [field]: value } : current
    ));
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!profile || !baseline) return;
    let parsedHours: Record<string, unknown>;
    try {
      const parsed = JSON.parse(workHours) as unknown;
      if (
        parsed === null
        || Array.isArray(parsed)
        || typeof parsed !== "object"
      ) {
        throw new Error("not an object");
      }
      parsedHours = parsed as Record<string, unknown>;
    } catch {
      setError("Ish vaqti JSON formati noto‘g‘ri.");
      return;
    }
    const patch: BusinessProfilePatch = {};
    for (const field of EDITABLE_FIELDS) {
      if (profile[field] !== baseline[field]) {
        (patch as Record<string, unknown>)[field] = profile[field];
      }
    }
    if (
      JSON.stringify(parsedHours) !== JSON.stringify(baseline.work_hours)
    ) {
      patch.work_hours = parsedHours;
    }
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      let value = Object.keys(patch).length
        ? await api.updateBusinessProfile(patch)
        : profile;
      const cropChanged = (
        profile.logo_x !== baseline.logo_x
        || profile.logo_y !== baseline.logo_y
        || profile.logo_zoom !== baseline.logo_zoom
      );
      if (cropChanged && profile.logo_object_key) {
        value = await api.attachBusinessLogo({
          object_key: profile.logo_object_key,
          x: profile.logo_x,
          y: profile.logo_y,
          zoom: profile.logo_zoom,
        });
      }
      applyLoaded(value);
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
        purpose: "logo",
        filename: file.name,
        content_type: file.type,
        size_bytes: file.size,
      });
      await api.uploadGrantedFile(grant, file);
      await api.attachBusinessLogo({
        object_key: grant.object_key,
        x: profile.logo_x,
        y: profile.logo_y,
        zoom: profile.logo_zoom,
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
          <h1>Biznes kabinet</h1>
        </div>
        <button type="button" className="button-secondary" onClick={logout}>Chiqish</button>
      </header>
      <form className="profile-form" onSubmit={save}>
        <label>Biznes nomi<input required value={profile.name} onChange={(event) => setField("name", event.currentTarget.value)} /></label>
        <label>Telefon<input type="tel" value={profile.phone} onChange={(event) => setField("phone", event.currentTarget.value)} /></label>
        <label>Tavsif<textarea value={profile.description} onChange={(event) => setField("description", event.currentTarget.value)} /></label>
        <label>Ochiq username<input value={profile.public_username} onChange={(event) => setField("public_username", event.currentTarget.value)} /></label>
        <label>Yo‘nalish<input value={profile.direction} onChange={(event) => setField("direction", event.currentTarget.value)} /></label>
        <label>Faoliyat turi<input value={profile.activity_type} onChange={(event) => setField("activity_type", event.currentTarget.value)} /></label>
        <label>Manzil<textarea value={profile.address} onChange={(event) => setField("address", event.currentTarget.value)} /></label>
        <label>Kenglik<input type="number" step="any" value={profile.latitude ?? ""} onChange={(event) => setField("latitude", event.currentTarget.value === "" ? null : Number(event.currentTarget.value))} /></label>
        <label>Uzunlik<input type="number" step="any" value={profile.longitude ?? ""} onChange={(event) => setField("longitude", event.currentTarget.value === "" ? null : Number(event.currentTarget.value))} /></label>
        <label>Ish vaqti (JSON)<textarea value={workHours} onChange={(event) => { setSaved(false); setWorkHours(event.currentTarget.value); }} /></label>
        <label>To‘lov kartasi<input value={profile.pay_card} onChange={(event) => setField("pay_card", event.currentTarget.value)} /></label>
        <label>Karta egasi<input value={profile.pay_holder} onChange={(event) => setField("pay_holder", event.currentTarget.value)} /></label>
        <label>Rahbar<input value={profile.director} onChange={(event) => setField("director", event.currentTarget.value)} /></label>
        <label>STIR<input value={profile.tax_id} onChange={(event) => setField("tax_id", event.currentTarget.value)} /></label>
        <fieldset>
          <legend>Logotip kesimi</legend>
          <label>X<input type="number" min="0" max="100" value={profile.logo_x} onChange={(event) => setField("logo_x", Number(event.currentTarget.value))} /></label>
          <label>Y<input type="number" min="0" max="100" value={profile.logo_y} onChange={(event) => setField("logo_y", Number(event.currentTarget.value))} /></label>
          <label>Zoom<input type="number" min="1" max="5" step="0.1" value={profile.logo_zoom} onChange={(event) => setField("logo_zoom", Number(event.currentTarget.value))} /></label>
        </fieldset>
        <label>Logotip<input type="file" accept="image/jpeg,image/png,image/webp,image/gif" disabled={busy} onChange={(event) => { const file = event.currentTarget.files?.[0]; if (file) void upload(file); }} /></label>
        {error && <p className="form-error" role="alert">{error}</p>}
        {saved && <p className="form-success" role="status">Saqlandi</p>}
        <button type="submit" disabled={busy}>Saqlash</button>
      </form>
    </main>
  );
}
