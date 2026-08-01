import { describe, expect, it } from "vitest";

import { UZBEKISTAN_REGIONS } from "./location-data";
import { findLocationCenter } from "./location-centers";


describe("v1656 location centers", () => {
  it("uses the exact monolith center for Qumqo'rg'on", () => {
    expect(findLocationCenter(
      "Surxondaryo viloyati",
      "Qumqo'rg'on",
    )).toEqual({ latitude: 37.834, longitude: 67.585 });
  });

  it("resolves every migrated region and district name", () => {
    for (const region of UZBEKISTAN_REGIONS) {
      expect(findLocationCenter(region.name, "")).not.toBeNull();
      for (const district of region.districts) {
        expect(
          findLocationCenter(region.name, district),
          `${region.name} / ${district}`,
        ).not.toBeNull();
      }
    }
  });
});
