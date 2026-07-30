import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BusinessProfile } from "./BusinessProfile";


const identity = {
  account_id: 7,
  account_type: "business" as const,
  name: "Muhr",
  login: "muhr1",
  csrf_token: "csrf",
  expires_at: "2026-08-30T08:00:00Z",
};

const profile = {
  account_id: 7,
  name: "Muhr",
  phone: "912377784",
  description: "",
  public_username: "muhr1",
  direction: "Savdo",
  activity_type: "Oziq-ovqat do'koni",
  address: "Beruniy ko‘chasi, Qumqo‘rg‘on tumani, Surxondaryo viloyati",
  latitude: 37.83,
  longitude: 67.58,
  work_hours: {},
  pay_card: "",
  pay_holder: "",
  pay_qr_object_key: "",
  pay_qr_url: "",
  director: "",
  tax_id: "",
  logo_object_key: "",
  logo_url: "",
  logo_x: 50,
  logo_y: 50,
  logo_zoom: 1,
  followers_count: 3,
  following_count: 1,
  rating_sum: 0,
  rating_count: 0,
  map_visible: true,
  dashboard_snapshot: {},
  recent_activity: [],
  cabinet_payload: {
    followers: [{ id: 8, name: "Vali" }],
    following: [{ id: 9, name: "Hamkor biznes" }],
  },
};

function api() {
  return {
    getSession: vi.fn().mockResolvedValue(identity),
    getBusinessProfile: vi.fn().mockResolvedValue(profile),
    updateBusinessProfile: vi.fn().mockResolvedValue(profile),
    createUploadGrant: vi.fn(),
    uploadGrantedFile: vi.fn(),
    attachBusinessLogo: vi.fn().mockResolvedValue(profile),
    attachBusinessPaymentQr: vi.fn().mockResolvedValue(profile),
    switchCabinet: vi.fn(),
    logout: vi.fn(),
  };
}


describe("v1656 business header follow counts", () => {
  it("shows follower counts in the identity card and hides duplicate menu cards", async () => {
    const user = userEvent.setup();
    render(
      <BusinessProfile
        api={api()}
        identity={identity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );

    await screen.findByRole("heading", { name: "Muhr" });

    const followers = screen.getByRole("button", { name: "3 obunachi" });
    const following = screen.getByRole("button", { name: "1 obuna" });
    expect(followers).toBeInTheDocument();
    expect(following).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Obunachilar/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Biznes obunalari/ })).not.toBeInTheDocument();

    await user.click(followers);
    expect(await screen.findByRole("heading", { name: "Obunachilar" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Kabinetga qaytish/ }));
    await screen.findByRole("heading", { name: "Muhr" });
    await user.click(screen.getByRole("button", { name: "1 obuna" }));
    expect(await screen.findByRole("heading", { name: "Biznes obunalari" })).toBeInTheDocument();
  });
});
