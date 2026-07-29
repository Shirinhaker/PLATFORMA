import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BusinessProfile } from "./BusinessProfile";
import { UserProfile } from "./UserProfile";


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
  name: "Ali",
  phone: "",
  public_username: "ali",
  region: "Surxondaryo",
  district: "Qumqo‘rg‘on",
  mahalla: "",
  latitude: null,
  longitude: null,
  location_exact: false,
  avatar_object_key: "",
  avatar_x: 50,
  avatar_y: 50,
  avatar_zoom: 1,
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
};


function profileApi() {
  return {
    getUserProfile: vi.fn().mockResolvedValue(userProfile),
    updateUserProfile: vi.fn().mockResolvedValue(userProfile),
    getBusinessProfile: vi.fn().mockResolvedValue(businessProfile),
    updateBusinessProfile: vi.fn().mockResolvedValue(businessProfile),
    createUploadGrant: vi.fn(),
    uploadGrantedFile: vi.fn(),
    attachUserAvatar: vi.fn().mockResolvedValue(userProfile),
    attachBusinessLogo: vi.fn().mockResolvedValue(businessProfile),
    logout: vi.fn().mockResolvedValue(undefined),
  };
}


async function openUserProfileForm(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole("button", { name: "Profilim" }));
  return screen.findByLabelText("Ism");
}


describe("profile cabinets", () => {
  it("opens the real user cabinet dashboard before the edit form", async () => {
    const api = profileApi();
    render(
      <UserProfile
        api={api}
        identity={userIdentity}
        onLogout={vi.fn()}
      />,
    );

    expect(await screen.findByRole("heading", { name: "Ali" }))
      .toBeInTheDocument();
    expect(screen.getByText("@ali")).toBeInTheDocument();
    expect(screen.getByText("● Qumqo‘rg‘on, Surxondaryo"))
      .toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Profilim" }))
      .toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Biznes kabinetga o‘tish/ }))
      .toBeInTheDocument();
    expect(screen.queryByLabelText("Ism")).not.toBeInTheDocument();
  });

  it("never renders business fields in the user cabinet", async () => {
    const user = userEvent.setup();
    const api = profileApi();
    render(
      <UserProfile
        api={api}
        identity={userIdentity}
        onLogout={vi.fn()}
      />,
    );
    expect(await openUserProfileForm(user)).toBeInTheDocument();
    expect(screen.queryByLabelText("STIR")).not.toBeInTheDocument();
  });

  it("logs out and opens business switching flow", async () => {
    const user = userEvent.setup();
    const api = profileApi();
    const onSwitchBusiness = vi.fn();
    render(
      <UserProfile
        api={api}
        identity={userIdentity}
        onLogout={vi.fn()}
        onSwitchBusiness={onSwitchBusiness}
      />,
    );

    await user.click(await screen.findByRole(
      "button",
      { name: /Biznes kabinetga o‘tish/ },
    ));

    expect(api.logout).toHaveBeenCalledTimes(1);
    expect(onSwitchBusiness).toHaveBeenCalledTimes(1);
  });

  it("never renders user fields in the business cabinet", async () => {
    const api = profileApi();
    render(
      <BusinessProfile
        api={api}
        identity={businessIdentity}
        onLogout={vi.fn()}
      />,
    );
    expect(await screen.findByLabelText("Biznes nomi"))
      .toBeInTheDocument();
    expect(screen.getByLabelText("STIR")).toBeInTheDocument();
    expect(screen.queryByLabelText("Mahalla")).not.toBeInTheDocument();
  });

  it("uploads a logo through a grant then attaches its object key", async () => {
    const user = userEvent.setup();
    const api = profileApi();
    const file = new File(["image"], "logo.png", { type: "image/png" });
    api.createUploadGrant.mockResolvedValue({
      object_key: "private/business/7/logo/abc.png",
      upload_url: "https://r2.example/upload",
      method: "PUT",
      headers: { "Content-Type": "image/png" },
      expires_in_seconds: 900,
    });
    render(
      <BusinessProfile
        api={api}
        identity={businessIdentity}
        onLogout={vi.fn()}
      />,
    );

    await user.upload(await screen.findByLabelText("Logotip"), file);

    expect(api.createUploadGrant).toHaveBeenCalledWith(
      expect.objectContaining({
        purpose: "logo",
        content_type: "image/png",
        size_bytes: file.size,
      }),
    );
    expect(api.uploadGrantedFile).toHaveBeenCalledWith(
      expect.objectContaining({
        upload_url: "https://r2.example/upload",
      }),
      file,
    );
    expect(api.attachBusinessLogo).toHaveBeenCalledWith(
      expect.objectContaining({
        object_key: "private/business/7/logo/abc.png",
      }),
    );
  });

  it("sends only changed user fields", async () => {
    const user = userEvent.setup();
    const api = profileApi();
    api.updateUserProfile.mockImplementation(async (patch) => ({
      ...userProfile,
      ...patch,
    }));
    render(
      <UserProfile
        api={api}
        identity={userIdentity}
        onLogout={vi.fn()}
      />,
    );

    const name = await openUserProfileForm(user);
    await user.clear(name);
    await user.type(name, "Yangi ism");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));

    expect(api.updateUserProfile).toHaveBeenCalledWith({
      name: "Yangi ism",
    });
    expect(await screen.findByText("Saqlandi")).toBeInTheDocument();
  });
});
