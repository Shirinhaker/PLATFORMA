import type { PublicView } from "./public-contract";

export interface PublicNavigationState {
  view: PublicView;
  query: string;
  categoryId: string | null;
}

export type PublicNavigationAction =
  | { type: "OPEN_CATALOG"; query: string }
  | { type: "OPEN_CATEGORY"; categoryId: string }
  | { type: "OPEN_LISTINGS" }
  | { type: "OPEN_LOCATION" }
  | { type: "OPEN_CART" }
  | { type: "OPEN_AUTH" }
  | { type: "OPEN_CABINET" }
  | { type: "GO_HOME" }
  | { type: "BACK" };

export const initialPublicNavigationState: PublicNavigationState = {
  view: "home",
  query: "",
  categoryId: null,
};

export function publicNavigationReducer(
  state: PublicNavigationState,
  action: PublicNavigationAction,
): PublicNavigationState {
  switch (action.type) {
    case "OPEN_CATALOG":
      return {
        view: "catalog",
        query: action.query,
        categoryId: null,
      };
    case "OPEN_CATEGORY":
      return {
        view: "category",
        query: state.query,
        categoryId: action.categoryId,
      };
    case "OPEN_LISTINGS":
      return {
        view: "listings",
        query: "",
        categoryId: null,
      };
    case "OPEN_LOCATION":
      return {
        view: "location",
        query: "",
        categoryId: null,
      };
    case "OPEN_CART":
      return {
        view: "cart",
        query: "",
        categoryId: null,
      };
    case "OPEN_AUTH":
      return {
        view: "auth",
        query: "",
        categoryId: null,
      };
    case "OPEN_CABINET":
      return {
        view: "cabinet",
        query: "",
        categoryId: null,
      };
    case "GO_HOME":
      return initialPublicNavigationState;
    case "BACK":
      if (state.view === "category") {
        return {
          view: "catalog",
          query: state.query,
          categoryId: null,
        };
      }

      return initialPublicNavigationState;
  }
}
