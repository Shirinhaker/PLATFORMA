import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SessionIdentity } from "../api/types";
import { App } from "./App";

vi.mock("../auth/AuthFlow", () => ({
  AuthFlow: ({
    onAuthenticated,
  }: {
    onAuthenticated(identity: SessionIdentity): void;
  }) => (
    <button
      onClick={() =>
        onAuthenticated({
          account_id: 5,
          account_type: "user",
          name: "Ali",
          login: "ali",
          csrf_token: "test",
          expires_at: "2099-01-01",
        })
      }
    >
      Test: kirishni yakunlash
    </button>
  ),
}));

const product = {
  public_id: "p_banana",
  name: "Banan",
  kind: "product" as const,
  price_text: "25 000",
  unit: "kg",
  image_url: "",
  note: "",
  group_name: "Mevalar",
};
const profile = {
  kind: "business" as const,
  public_id: "b_store",
  name: "Meva do‘koni",
  public_username: "",
  description: "",
  direction: "Savdo",
  activity_type: "Do‘kon",
  address: "",
  phone: "",
  image_url: "",
  crop_x: 50,
  crop_y: 50,
  crop_zoom: 1,
  followers_count: 0,
  specialist: null,
  items: [product],
  listings: [],
};
const result = {
  ...product,
  owner_public_id: "b_store",
  owner_name: profile.name,
  public_username: "",
  description: "",
  direction: "Savdo",
  activity_type: "Do‘kon",
  region: "",
  district: "",
  mahalla: "",
};
const catalogItem = {
  ...product,
  direction: "Savdo",
  activity_type: "Do‘kon",
  owner_public_id: "b_store",
  owner_name: profile.name,
  owner_label: profile.name,
  owner_state: "linked" as const,
  can_chat: true,
  can_order: true,
  queue_enabled: false,
  queue_provider_count: 0,
};
const features = {
  listings: false,
  stories: false,
  chat: true,
  systemization: false,
  taxi: false,
};
function guestApi() {
  return {
    getSession: vi
      .fn()
      .mockRejectedValue(Object.assign(new Error("guest"), { status: 401 })),
    getPublicFeatures: vi.fn().mockResolvedValue(features),
    searchPublic: vi.fn().mockResolvedValue({
      items: [result],
      page: 1,
      page_size: 20,
      total: 1,
      pages: 1,
    }),
    getPublicProfile: vi.fn().mockResolvedValue(profile),
    getCatalogItems: vi
      .fn()
      .mockResolvedValue({ items: [catalogItem], total: 1, page: 1, pages: 1 }),
    startRegistration: vi.fn(),
    startLogin: vi.fn(),
    verifyRegistration: vi.fn(),
    verifyLogin: vi.fn(),
    resendChallenge: vi.fn(),
    getMessageConversations: vi.fn().mockResolvedValue([]),
    getMessageThread: vi.fn().mockResolvedValue({
      other: {
        kind: "business",
        public_id: "b_store",
        name: profile.name,
        avatar_url: "",
      },
      messages: [],
    }),
    sendMessage: vi.fn(),
    sendMessageImage: vi.fn(),
    editMessage: vi.fn(),
    deleteMessage: vi.fn(),
    createUploadGrant: vi.fn(),
    uploadGrantedFile: vi.fn(),
    getQueueOptions: vi.fn(),
    getQueueSlots: vi.fn(),
    createQueue: vi.fn(),
    createCourseEnrollment: vi.fn(),
  };
}
beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  window.history.replaceState({}, "", "/");
  localStorage.setItem(
    "koprik_home_location_v1",
    JSON.stringify({
      region: "Surxondaryo viloyati",
      district: "Qumqo‘rg‘on tumani",
      mahalla: "",
    }),
  );
});
async function search() {
  await userEvent.type(
    await screen.findByPlaceholderText("Nima qidiryapsiz?"),
    "Banan",
  );
  await userEvent.click(screen.getByRole("button", { name: "Qidirish" }));
  return screen.findByRole("button", { name: /Banan.*25 000/ });
}
async function nativeBack() {
  await act(async () => {
    window.history.back();
    await new Promise((resolve) => setTimeout(resolve, 25));
  });
}

describe("Mijozning ishini davom ettirish", () => {
  it("restores Home results, query, position and header after profile Back without repeating the search", async () => {
    const api = guestApi();
    const { container } = render(<App api={api} />);
    const card = await search();
    const scroller = container.querySelector(".app-shell__content")!;
    scroller.scrollTop = 340;
    await userEvent.click(card);
    await screen.findByText(profile.name, { selector: ".public-profile-name" });
    await userEvent.click(screen.getByRole("button", { name: "Orqaga" }));
    expect(screen.getByPlaceholderText("Nima qidiryapsiz?")).toHaveValue("Banan");
    expect(screen.getByRole("button", { name: /Banan.*25 000/ })).toBeInTheDocument();
    expect(scroller.scrollTop).toBe(340);
    expect(container.querySelector(".app-shell")).toHaveClass("search-results-active");
    expect(api.searchPublic).toHaveBeenCalledTimes(1);
  });

  it("restores the preceding app screen on browser Back and Forward, ignoring profile title updates", async () => {
    const api = guestApi();
    render(<App api={api} />);
    await userEvent.click(await search());
    await screen.findByText(profile.name, { selector: ".public-profile-name" });
    await nativeBack();
    expect(screen.getByPlaceholderText("Nima qidiryapsiz?")).toHaveValue("Banan");
    await act(async () => {
      window.history.forward();
      await new Promise((resolve) => setTimeout(resolve, 25));
    });
    expect(
      await screen.findByText(profile.name, { selector: ".public-profile-name" }),
    ).toBeInTheDocument();
  });

  it("closes Home search on browser Back and restores it on Forward", async () => {
    const api = guestApi();
    render(<App api={api} />);
    await search();
    await nativeBack();
    expect(
      screen.queryByRole("button", { name: /Banan.*25 000/ }),
    ).not.toBeInTheDocument();
    await act(async () => {
      window.history.forward();
      await new Promise((resolve) => setTimeout(resolve, 25));
    });
    expect(
      await screen.findByRole("button", { name: /Banan.*25 000/ }),
    ).toBeInTheDocument();
    expect(api.searchPublic).toHaveBeenCalledTimes(1);
  });

  it("opens the seller chat after a guest completes authentication without sending a message", async () => {
    const api = guestApi();
    render(<App api={api} />);
    await userEvent.click(await screen.findByRole("button", { name: /Katalog bo/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Chat" }));
    expect(api.getMessageThread).not.toHaveBeenCalled();
    await userEvent.click(
      screen.getByRole("button", { name: "Test: kirishni yakunlash" }),
    );
    await waitFor(() =>
      expect(api.getMessageThread).toHaveBeenCalledWith("business", "b_store"),
    );
    expect(await screen.findByPlaceholderText("Xabar yozing...")).toBeInTheDocument();
    expect(api.sendMessage).not.toHaveBeenCalled();
    expect(screen.queryByText("Test: kirishni yakunlash")).not.toBeInTheDocument();
  });

  it.each(["queue", "course"])(
    "resumes the selected %s after guest login without submitting it",
    async (kind) => {
      const api = guestApi();
      const service = {
        ...product,
        kind: "service",
        queue_enabled: kind === "queue",
        queue_provider_count: 1,
        enrollment_status: "open",
      };
      api.getPublicProfile.mockResolvedValue({
        ...profile,
        direction: kind === "course" ? "Ta'lim faoliyati" : "Tibbiy xizmatlar",
        items: [service],
      });
      render(<App api={api} />);
      await userEvent.click(await search());
      await userEvent.click(
        await screen.findByRole("button", {
          name: kind === "queue" ? "Navbat olish" : "Kursga yozilish",
        }),
      );
      await userEvent.click(
        screen.getByRole("button", { name: "Test: kirishni yakunlash" }),
      );
      expect(await screen.findByRole("dialog")).toBeInTheDocument();
      if (kind === "course")
        expect(
          within(screen.getByRole("dialog")).getByText("Banan kursiga yozilish"),
        ).toBeInTheDocument();
      expect(api.createQueue).not.toHaveBeenCalled();
      expect(api.createCourseEnrollment).not.toHaveBeenCalled();
    },
  );

  it("keeps first-visit district selection mandatory without a dead Back control", async () => {
    localStorage.clear();
    render(<App api={guestApi()} />);
    expect(
      await screen.findByRole("heading", { name: "Hududingizni tanlang" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Orqaga" })).not.toBeInTheDocument();
  });
});
