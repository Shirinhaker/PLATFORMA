export const HOME_LOCATION_STORAGE_KEY = "koprik_home_location_v1";

export interface HomeLocation {
  region: string;
  district: string;
  neighborhood: string;
}

interface ReadableStorage {
  getItem(key: string): string | null;
}

interface WritableStorage {
  setItem(key: string, value: string): void;
}

interface StoredHomeLocation {
  region?: unknown;
  district?: unknown;
  mahalla?: unknown;
}

function browserStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function readHomeLocation(
  storage: ReadableStorage | null = browserStorage(),
): HomeLocation | null {
  if (!storage) {
    return null;
  }

  try {
    const parsed = JSON.parse(
      storage.getItem(HOME_LOCATION_STORAGE_KEY) ?? "null",
    ) as StoredHomeLocation | null;
    const district = String(parsed?.district ?? "").trim();

    if (!parsed || !district) {
      return null;
    }

    return {
      region: String(parsed.region ?? "").trim(),
      district,
      neighborhood: String(parsed.mahalla ?? "").trim(),
    };
  } catch {
    return null;
  }
}

export function saveHomeLocation(
  location: HomeLocation,
  storage: WritableStorage | null = browserStorage(),
): boolean {
  const district = location.district.trim();

  if (!storage || !district) {
    return false;
  }

  try {
    storage.setItem(
      HOME_LOCATION_STORAGE_KEY,
      JSON.stringify({
        region: location.region.trim(),
        district,
        mahalla: location.neighborhood.trim(),
        lat: null,
        lng: null,
        exact: false,
      }),
    );
    return true;
  } catch {
    return false;
  }
}
