import { describe, expect, it } from "vitest";

import {
  CATALOG_SEARCH_TYPES,
  PHASE3B_OUT_OF_SCOPE,
  PUBLIC_HEADER_ACTIONS,
  PUBLIC_VIEWS,
} from "./public-contract";

describe("Phase 3B public flow contract", () => {
  it("exposes only the approved migrated views", () => {
    expect(PUBLIC_VIEWS).toEqual([
      "home",
      "catalog",
      "category",
      "listings",
      "location",
      "cart",
      "auth",
      "cabinet",
      "taxi-call",
      "taxidrv",
    ]);
  });

  it("keeps the public header focused on real actions", () => {
    expect(PUBLIC_HEADER_ACTIONS).toEqual(["home", "location", "account"]);
  });

  it("preserves the six modular catalog search types", () => {
    expect(CATALOG_SEARCH_TYPES).toEqual([
      "all",
      "product",
      "service",
      "business",
      "specialist",
      "user",
    ]);
  });

  it("does not claim unmigrated Phase 3B features", () => {
    expect(PHASE3B_OUT_OF_SCOPE).toEqual([
      "payments",
      "admin",
      "staff",
    ]);
  });
});
