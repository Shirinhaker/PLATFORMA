import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

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

function unauthorized() {
  return Object.assign(new Error("unauthorized"), { status: 401 });
}

function guestApi() {
  return {
    getSession: vi.fn().mockRejectedValue(unauthorized()),
    startRegistration: vi.fn(),
    startLogin: vi.fn(),
    verifyRegistration: vi.fn(),
    verifyLogin: vi.fn(),
    resendChallenge: vi.fn(),
  };
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
    logout: vi.fn().mockResolvedValue(undefined),
  };
}


describe("App", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("starts a guest on the public home instead of the login form", async () => {
    render(<App api={guestApi()} />);

    expect(
      await screen.findByRole("heading", {
        name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kirish" }))
      .toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Koprik’ga kirish" }))
      .not.toBeInTheDocument();
  });

  it("opens the existing authentication flow from the public header", async () => {
    const user = userEvent.setup();
    render(<App api={guestApi()} />);

    await screen.findByRole("heading", {
      name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
    });
    await user.click(screen.getByRole("button", { name: "Kirish" }));

    expect(
      screen.getByRole("heading", { name: "Koprik’ga kirish" }),
    ).toBeInTheDocument();
  });

  it("opens the matching cabinet after a completed login", async () => {
    const user = userEvent.setup();
    const api = guestApi();
    api.getSession
      .mockRejectedValueOnce(unauthorized())
      .mockResolvedValue(businessIdentity);
    api.startLogin.mockResolvedValue({
      request_id: 13,
      deep_link: "https://t.me/koprik_bot?start=login-token",
      code_sent: true,
      expires_in: 300,
      resend_after: 0,
    });
    api.verifyLogin.mockResolvedValue({
      account_id: 7,
      account_type: "business",
      csrf_token: "csrf",
      expires_at: "2026-08-27T08:00:00Z",
    });

    render(<App api={api} />);

    await screen.findByRole("heading", {
      name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
    });
    await user.click(screen.getByRole("button", { name: "Kirish" }));
    await user.click(
      screen.getAllByRole("button", { name: "Kirish" }).at(-1)!,
    );
    await user.type(screen.getByLabelText("Login"), "b_turon");
    await user.type(screen.getByLabelText("Parol"), "secret-42");
    await user.click(screen.getByRole("button", { name: "Davom etish" }));
    await user.type(await screen.findByLabelText("6 xonali kod"), "123456");
    await user.click(screen.getByRole("button", { name: "Tasdiqlash" }));

    expect(
      await screen.findByRole("heading", { name: "Biznes kabinet" }),
    ).toBeInTheDocument();
  });

  it("starts an authenticated session on Home and opens Cabinet on demand", async () => {
    const user = userEvent.setup();
    const api = {
      getSession: vi.fn().mockResolvedValue(businessIdentity),
    };

    render(<App api={api} />);

    expect(
      await screen.findByRole("heading", {
        name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
      }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Biznes kabinet" }))
      .not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Kabinet" }));
    expect(
      screen.getByRole("heading", { name: "Biznes kabinet" }),
    ).toBeInTheDocument();
  });

  it("returns to the public home after profile logout", async () => {
    const user = userEvent.setup();
    const api = profileApi();
    render(<App api={api} />);

    await screen.findByRole("heading", {
      name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
    });
    await user.click(screen.getByRole("button", { name: "Kabinet" }));
    await screen.findByLabelText("Ism");
    await user.click(screen.getByRole("button", { name: "Chiqish" }));

    expect(api.logout).toHaveBeenCalledOnce();
    expect(
      await screen.findByRole("heading", {
        name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kirish" }))
      .toBeInTheDocument();
  });

  it("opens the catalog with the Home search query", async () => {
    const user = userEvent.setup();
    render(<App api={guestApi()} />);

    await screen.findByRole("heading", {
      name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
    });
    await user.type(screen.getByLabelText("Qidiruv"), "telefon");
    await user.click(screen.getByRole("button", { name: "Qidirish" }));

    expect(
      screen.getByRole("heading", { name: "Faoliyat yo‘nalishlari" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Qidiruv")).toHaveValue("telefon");
  });

  it("navigates Catalog to Category and back", async () => {
    const user = userEvent.setup();
    render(<App api={guestApi()} />);

    await screen.findByRole("heading", {
      name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
    });
    await user.click(screen.getByRole("button", { name: "Katalog bo‘yicha" }));
    await user.click(
      screen.getByRole("button", { name: /^Savdo —/ }),
    );
    expect(screen.getByRole("heading", { name: "Savdo" }))
      .toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Orqaga" }));
    expect(
      screen.getByRole("heading", { name: "Faoliyat yo‘nalishlari" }),
    ).toBeInTheDocument();
  });

  it("updates the Home district after location save", async () => {
    const user = userEvent.setup();
    render(<App api={guestApi()} />);

    await screen.findByRole("heading", {
      name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
    });
    await user.click(screen.getByRole("button", { name: "Manzil" }));
    await user.selectOptions(
      screen.getByLabelText("Viloyat / shahar"),
      "Toshkent shahri",
    );
    await user.selectOptions(screen.getByLabelText("Tuman"), "Chilonzor");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));

    expect(
      await screen.findByRole("heading", { name: "Chilonzor" }),
    ).toBeInTheDocument();
  });

  it("keeps public location usable when session bootstrap fails", async () => {
    const user = userEvent.setup();
    const api = {
      getSession: vi.fn().mockRejectedValue(new TypeError("offline")),
    };

    render(<App api={api} />);

    expect(
      await screen.findByRole("heading", {
        name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
      }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Manzil" }));

    expect(
      screen.getByRole("heading", { name: "Hududingizni tanlang" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("keeps the retryable session error on account views", async () => {
    const user = userEvent.setup();
    const api = {
      getSession: vi.fn()
        .mockRejectedValueOnce(new TypeError("offline"))
        .mockResolvedValueOnce(userIdentity),
    };

    render(<App api={api} />);

    await screen.findByRole("heading", {
      name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
    });
    await user.click(screen.getByRole("button", { name: "Kirish" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Server bilan bog‘lanib bo‘lmadi.",
    );

    await user.click(screen.getByRole("button", { name: "Qayta urinish" }));

    expect(
      await screen.findByRole("heading", { name: "Oddiy kabinet" }),
    ).toBeInTheDocument();
    expect(api.getSession).toHaveBeenCalledTimes(2);
  });
});
