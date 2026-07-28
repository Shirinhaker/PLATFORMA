import { describe, expect, it } from "vitest";

import {
  CATALOG_DIRECTIONS,
  searchCatalogDirections,
} from "./catalog-data";

describe("v1656 catalog data", () => {
  it("preserves all 20 directions with stable unique ids", () => {
    expect(CATALOG_DIRECTIONS).toHaveLength(20);
    expect(CATALOG_DIRECTIONS[0]?.id).toBe("trade");
    expect(CATALOG_DIRECTIONS.at(-1)?.id).toBe("import-export");
    expect(new Set(CATALOG_DIRECTIONS.map(({ id }) => id)).size).toBe(20);
  });

  it("keeps at least one activity type in every direction", () => {
    expect(
      CATALOG_DIRECTIONS.every(({ activityTypes }) => activityTypes.length > 0),
    ).toBe(true);
  });

  it("normalizes Uzbek apostrophe variants and case", () => {
    expect(searchCatalogDirections("GO‘ZALLIK").map(({ id }) => id))
      .toContain("household-services");
    expect(searchCatalogDirections("go'zallik").map(({ id }) => id))
      .toContain("household-services");
  });
});
