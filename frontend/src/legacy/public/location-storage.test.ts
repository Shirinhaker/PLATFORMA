import { describe, expect, it, vi } from "vitest";

import {
  HOME_LOCATION_STORAGE_KEY,
  readHomeLocation,
  saveHomeLocation,
} from "./location-storage";

describe("v1656-compatible home location storage", () => {
  it("returns null when storage is empty", () => {
    expect(
      readHomeLocation({
        getItem: vi.fn(() => null),
      }),
    ).toBeNull();
  });

  it("reads a valid saved region, district, and neighborhood", () => {
    const getItem = vi.fn(() =>
      JSON.stringify({
        region: "Surxondaryo viloyati",
        district: "Qumqo'rg'on",
        mahalla: "Yangi hayot",
        lat: null,
        lng: null,
        exact: false,
      }),
    );

    expect(readHomeLocation({ getItem })).toEqual({
      region: "Surxondaryo viloyati",
      district: "Qumqo'rg'on",
      neighborhood: "Yangi hayot",
    });
    expect(getItem).toHaveBeenCalledWith(HOME_LOCATION_STORAGE_KEY);
  });

  it("preserves the exact saved map center used by the v1656 Home map", () => {
    const getItem = vi.fn(() => JSON.stringify({
      region: "Surxondaryo viloyati",
      district: "Qumqo'rg'on",
      mahalla: "Yangi hayot",
      lat: 37.82,
      lng: 67.58,
      exact: true,
    }));

    expect(readHomeLocation({ getItem })).toEqual({
      region: "Surxondaryo viloyati",
      district: "Qumqo'rg'on",
      neighborhood: "Yangi hayot",
      latitude: 37.82,
      longitude: 67.58,
      exact: true,
    });
  });

  it("ignores malformed JSON and entries without a district", () => {
    expect(
      readHomeLocation({
        getItem: vi.fn(() => "{not-json"),
      }),
    ).toBeNull();
    expect(
      readHomeLocation({
        getItem: vi.fn(() => JSON.stringify({ region: "Toshkent shahri" })),
      }),
    ).toBeNull();
  });

  it("writes the exact v1656 schema under its versioned key", () => {
    const setItem = vi.fn();

    expect(
      saveHomeLocation(
        {
          region: "Samarqand viloyati",
          district: "Urgut",
          neighborhood: "",
        },
        { setItem },
      ),
    ).toBe(true);

    expect(setItem).toHaveBeenCalledWith(
      HOME_LOCATION_STORAGE_KEY,
      JSON.stringify({
        region: "Samarqand viloyati",
        district: "Urgut",
        mahalla: "",
        lat: null,
        lng: null,
        exact: false,
      }),
    );
  });

  it("does not crash when browser storage is unavailable", () => {
    expect(
      readHomeLocation({
        getItem: vi.fn(() => {
          throw new Error("blocked");
        }),
      }),
    ).toBeNull();

    expect(
      saveHomeLocation(
        {
          region: "Toshkent shahri",
          district: "Chilonzor",
          neighborhood: "",
        },
        {
          setItem: vi.fn(() => {
            throw new Error("blocked");
          }),
        },
      ),
    ).toBe(false);
  });
});
