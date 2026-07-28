import { useMemo, useState, type FormEvent } from "react";

import { UZBEKISTAN_REGIONS } from "./location-data";
import {
  readHomeLocation,
  saveHomeLocation,
  type HomeLocation,
} from "./location-storage";

interface LocationScreenProps {
  initialLocation?: HomeLocation | null;
  onSaved: (location: HomeLocation) => void;
}

const EMPTY_LOCATION: HomeLocation = {
  region: "",
  district: "",
  neighborhood: "",
};

export function LocationScreen({
  initialLocation,
  onSaved,
}: LocationScreenProps) {
  const restoredLocation = useMemo(
    () => initialLocation ?? readHomeLocation() ?? EMPTY_LOCATION,
    [initialLocation],
  );
  const [region, setRegion] = useState(restoredLocation.region);
  const [district, setDistrict] = useState(restoredLocation.district);
  const [neighborhood, setNeighborhood] = useState(
    restoredLocation.neighborhood,
  );
  const [error, setError] = useState("");

  const districts =
    UZBEKISTAN_REGIONS.find((item) => item.name === region)?.districts ?? [];

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const location = {
      region: region.trim(),
      district: district.trim(),
      neighborhood: neighborhood.trim(),
    };

    if (!location.district) {
      setError("Iltimos, tumaningizni tanlang.");
      return;
    }

    if (!saveHomeLocation(location)) {
      setError("Manzilni brauzerda saqlab bo‘lmadi. Qayta urinib ko‘ring.");
      return;
    }

    setError("");
    onSaved(location);
  }

  return (
    <main className="public-location">
      <section className="public-location__intro">
        <p className="public-section-eyebrow">Manzil</p>
        <h1>Hududingizni tanlang</h1>
        <p>
          Tanlangan tumandagi obunali profillar, mahsulotlar va xizmatlar
          ko‘rsatiladi.
        </p>
      </section>

      <form className="public-location__form" onSubmit={submit}>
        <aside className="public-location__privacy">
          <strong>Tuman tanlash talab qilinadi</strong>
          <span>
            Koprikdan foydalanishni boshlash uchun avval tumaningizni belgilang.
            Bu ma’lumot boshqa foydalanuvchilarga ko‘rsatilmaydi.
          </span>
        </aside>

        <label>
          <span>Viloyat / shahar</span>
          <select
            aria-label="Viloyat / shahar"
            value={region}
            onChange={(event) => {
              setRegion(event.currentTarget.value);
              setDistrict("");
              setError("");
            }}
          >
            <option value="">Viloyatni tanlang</option>
            {UZBEKISTAN_REGIONS.map((item) => (
              <option key={item.name} value={item.name}>
                {item.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Tuman</span>
          <select
            aria-label="Tuman"
            disabled={!region}
            value={district}
            onChange={(event) => {
              setDistrict(event.currentTarget.value);
              setError("");
            }}
          >
            <option value="">Tumanni tanlang</option>
            {districts.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>

        <label className="public-location__wide">
          <span>Mahalla — ixtiyoriy</span>
          <input
            aria-label="Mahalla — ixtiyoriy"
            placeholder="Mahalla nomi (agar bilsangiz)"
            value={neighborhood}
            onChange={(event) => setNeighborhood(event.currentTarget.value)}
          />
        </label>

        {error ? (
          <p className="public-location__error" role="alert">
            {error}
          </p>
        ) : null}

        <button className="public-location__save" type="submit">
          Saqlash
        </button>
      </form>
    </main>
  );
}
