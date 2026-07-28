import { describe, expect, it } from "vitest";

import {
  initialPublicNavigationState,
  publicNavigationReducer,
} from "./public-navigation";

describe("publicNavigationReducer", () => {
  it("starts on the public home", () => {
    expect(initialPublicNavigationState).toEqual({
      view: "home",
      query: "",
      categoryId: null,
    });
  });

  it("opens the catalog and stores the current search query", () => {
    expect(
      publicNavigationReducer(initialPublicNavigationState, {
        type: "OPEN_CATALOG",
        query: "usta",
      }),
    ).toEqual({
      view: "catalog",
      query: "usta",
      categoryId: null,
    });
  });

  it("opens a category and preserves the current query", () => {
    const catalogState = {
      view: "catalog" as const,
      query: "ta'lim",
      categoryId: null,
    };

    expect(
      publicNavigationReducer(catalogState, {
        type: "OPEN_CATEGORY",
        categoryId: "education",
      }),
    ).toEqual({
      view: "category",
      query: "ta'lim",
      categoryId: "education",
    });
  });

  it.each([
    ["OPEN_LOCATION", "location"],
    ["OPEN_AUTH", "auth"],
    ["OPEN_CABINET", "cabinet"],
  ] as const)("%s opens %s", (type, view) => {
    expect(publicNavigationReducer(initialPublicNavigationState, { type })).toEqual({
      view,
      query: "",
      categoryId: null,
    });
  });

  it("goes home and clears transient catalog state", () => {
    expect(
      publicNavigationReducer(
        {
          view: "category",
          query: "usta",
          categoryId: "services",
        },
        { type: "GO_HOME" },
      ),
    ).toEqual(initialPublicNavigationState);
  });

  it("returns from a category to its catalog context", () => {
    expect(
      publicNavigationReducer(
        {
          view: "category",
          query: "usta",
          categoryId: "services",
        },
        { type: "BACK" },
      ),
    ).toEqual({
      view: "catalog",
      query: "usta",
      categoryId: null,
    });
  });

  it.each(["catalog", "location", "auth", "cabinet"] as const)(
    "returns from %s to a clean home",
    (view) => {
      expect(
        publicNavigationReducer(
          {
            view,
            query: "usta",
            categoryId: "services",
          },
          { type: "BACK" },
        ),
      ).toEqual(initialPublicNavigationState);
    },
  );
});
