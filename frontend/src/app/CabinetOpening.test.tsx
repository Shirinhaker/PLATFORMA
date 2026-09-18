import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";
const userIdentity = {
  account_id: 5,
  account_type: "user" as const,
  name: "Ali",
  login: "u_ali",
  csrf_token: "csrf",
  expires_at: "2026-08-27T08:00:00Z",
};

const businessIdentity = {
  account_id: 7,
  account_type: "business" as const,
  name: "Turon",
  login: "b_turon",
  csrf_token: "csrf",
  expires_at: "2026-08-27T08:00:00Z",
};

const userProfile = {
  account_id: 5,
  public_id: "u_1234567890abcdef",
  name: "Ali",
  phone: "",
  public_username: "",
  region: "",
  district: "",
  mahalla: "",
  latitude: null,
  longitude: null,
  location_exact: false,
  avatar_object_key: "",
  avatar_url: "",
  avatar_x: 50,
  avatar_y: 50,
  avatar_zoom: 1,
  followers_count: 0,
  following_count: 0,
  has_business: false,
  dashboard_snapshot: {},
  recent_activity: [],
  specialist_profile: {},
  cabinet_payload: {},
};

const businessProfile = {
  account_id: 7,
  name: "Turon",
  phone: "",
  description: "",
  public_username: "",
  direction: "",
  activity_type: "",
  address: "",
  latitude: null,
  longitude: null,
  work_hours: {},
  pay_card: "",
  pay_holder: "",
  pay_qr_object_key: "",
  director: "",
  tax_id: "",
  logo_object_key: "",
  logo_x: 50,
  logo_y: 50,
  logo_zoom: 1,
  followers_count: 0,
  following_count: 0,
  rating_sum: 0,
  rating_count: 0,
  map_visible: false,
  dashboard_snapshot: {},
  recent_activity: [],
  cabinet_payload: {},
};
function saveHomeLocation() {
  window.localStorage.setItem(
    "koprik_home_location_v1",
    JSON.stringify({
      region: "Surxondaryo viloyati",
      district: "Qumqo‘rg‘on tumani",
      mahalla: "",
      lat: 37.82,
      lng: 67.58,
      exact: false,
    }),
  );
}

function profileApi(identity = userIdentity) {
  return {
    getSession: vi.fn().mockResolvedValue(identity),
    getUserProfile: vi.fn().mockResolvedValue(userProfile),
    updateUserProfile: vi.fn().mockResolvedValue(userProfile),
    getBusinessProfile: vi.fn().mockResolvedValue(businessProfile),
    updateBusinessProfile: vi.fn().mockResolvedValue(businessProfile),
    createUploadGrant: vi.fn(),
    uploadGrantedFile: vi.fn(),
    attachUserAvatar: vi.fn().mockResolvedValue(userProfile),
    attachBusinessLogo: vi.fn().mockResolvedValue(businessProfile),
    switchCabinet: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
  };
}

describe("cabinet opening", () => {
  it.each(["user", "business"] as const)(
    "shows the preloaded %s cabinet while the refresh is still pending",
    async (kind) => {
      window.localStorage.clear();
      window.history.replaceState({}, "", "/");
      saveHomeLocation();
      const user = userEvent.setup();
      const identity = kind === "user" ? userIdentity : businessIdentity;
      const api = { ...profileApi(), getSession: vi.fn().mockResolvedValue(identity) };
      const getProfile = kind === "user" ? api.getUserProfile : api.getBusinessProfile;
      const value = kind === "user" ? userProfile : businessProfile;
      let resolveRefresh!: (value: unknown) => void;
      getProfile.mockResolvedValueOnce(value).mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveRefresh = resolve;
          }),
      );
      render(<App api={api} />);
      await screen.findByRole("heading", {
        name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
      });
      await waitFor(() => expect(getProfile).toHaveBeenCalledOnce());
      await act(async () => {
        await getProfile.mock.results[0]!.value;
      });
      await user.click(screen.getByRole("button", { name: "Kabinet" }));
      expect(getProfile).toHaveBeenCalledTimes(2);
      expect(
        screen.queryByText(/^(Kabinet|Profil) yuklanmoqda/),
      ).not.toBeInTheDocument();
      expect(screen.getByRole("heading", { name: identity.name })).toBeInTheDocument();
      await act(async () => {
        resolveRefresh(value);
      });
    },
  );
});
