import { fireEvent, render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, afterAll, beforeEach, describe, expect, it, vi } from "vitest";
import type { PublicCatalogItem, PublicProfileItem } from "../../api/types";
import { CatalogItemCard } from "./CatalogItemCard";
import { PublicProfile } from "./PublicProfile";
import { App } from "../../app/App";
import { ItemsEditorView } from "../../profiles/BusinessItemsView";

// jsdom does not implement native dialog top-layer APIs. Browser focus trapping
// and viewport layout still need a real-browser check.
const oldShow = HTMLDialogElement.prototype.showModal;
const oldClose = HTMLDialogElement.prototype.close;
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
    this.querySelector<HTMLButtonElement>("button")?.focus();
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});
afterAll(() => {
  HTMLDialogElement.prototype.showModal = oldShow;
  HTMLDialogElement.prototype.close = oldClose;
});
beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  window.localStorage.setItem(
    "koprik_home_location_v1",
    JSON.stringify({
      region: "Surxondaryo viloyati",
      district: "Qumqo‘rg‘on tumani",
      mahalla: "",
      exact: false,
    }),
  );
});
const item: PublicCatalogItem = {
  kind: "product",
  public_id: "p_test",
  name: "Sinov mahsuloti",
  price_text: "25 000 so‘m",
  unit: "kg",
  note: "To‘liq mahsulot tavsifi\nIkkinchi qator",
  owner_state: "linked",
  owner_public_id: "b_test",
  owner_name: "Sinov do‘koni",
  owner_label: "Sinov do‘koni",
  direction: "Savdo",
  activity_type: "Do‘kon",
  region: "",
  district: "",
  mahalla: "",
  image_url: "",
  can_order: true,
  can_chat: true,
  queue_enabled: false,
};
function homeApi(catalogItem = item) {
  return {
    getSession: vi
      .fn()
      .mockRejectedValue(Object.assign(new Error("unauthorized"), { status: 401 })),
    getPublicFeatures: vi.fn().mockResolvedValue({
      listings: false,
      stories: false,
      chat: false,
      systemization: false,
      taxi: false,
    }),
    getCatalogItem: vi.fn().mockResolvedValue(catalogItem),
    getPublicProfile: vi.fn(),
    getDistrictOffers: vi.fn().mockResolvedValue({
      needs_district: false,
      items: [
        {
          kind: catalogItem.kind,
          content_public_id: catalogItem.public_id,
          title: catalogItem.name,
          business_name: catalogItem.owner_name,
          image: "",
          business_logo: "",
          price: catalogItem.price_text,
          unit: catalogItem.unit,
        },
      ],
    }),
    searchPublic: vi.fn().mockResolvedValue({
      items: [{ ...catalogItem, description: catalogItem.note, public_username: "" }],
      page: 1,
      pages: 1,
      total: 1,
      page_size: 20,
    }),
  };
}

describe("Mahsulot va xizmat ma’lumot oynasi", () => {
  it("opens a catalog product by keyboard, shows full text and restores focus on close", async () => {
    const user = userEvent.setup();
    const owner = vi.fn();
    render(<CatalogItemCard item={item} onOpenOwner={owner} />);
    const card = screen.getByRole("button", { name: /Sinov mahsuloti haqida/ });
    card.focus();
    await user.keyboard("{Enter}");
    const dialog = screen.getByRole("dialog", { name: item.name });
    expect(within(dialog).getByText(/To‘liq mahsulot tavsifi/)).toHaveTextContent(
      "Ikkinchi qator",
    );
    expect(within(dialog).getByText("O‘lchov birligi: kg")).toBeVisible();
    expect(owner).not.toHaveBeenCalled();
    expect(document.body.style.overflow).toBe("hidden");
    await user.click(
      within(dialog).getByRole("button", { name: "Ma’lumot oynasini yopish" }),
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(card).toHaveFocus();
    expect(document.body.style.overflow).toBe("");
    await user.click(card);
    fireEvent(
      screen.getByRole("dialog"),
      new Event("cancel", { bubbles: true, cancelable: true }),
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
  it("keeps queue login and provider guards inside a service dialog", async () => {
    const user = userEvent.setup();
    const onNeedQueueLogin = vi.fn();
    const onBookQueue = vi.fn();
    const service = {
      ...item,
      kind: "service" as const,
      name: "Qabul",
      queue_enabled: true,
      queue_provider_count: 1,
    };
    render(
      <CatalogItemCard
        item={service}
        onNeedQueueLogin={onNeedQueueLogin}
        onBookQueue={onBookQueue}
      />,
    );
    await user.click(screen.getByRole("button", { name: /Qabul haqida/ }));
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "Navbat olish" }),
    );
    expect(onNeedQueueLogin).toHaveBeenCalledOnce();
    expect(onBookQueue).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
  it("does not allow orders for unlinked items and closes on the backdrop", async () => {
    render(
      <CatalogItemCard item={{ ...item, owner_state: "unlinked", can_order: false }} />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: /Sinov mahsuloti haqida/ }),
    );
    const dialog = screen.getByRole("dialog");
    expect(
      within(dialog).getByRole("button", { name: "Buyurtma berish" }),
    ).toBeDisabled();
    fireEvent.click(dialog);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
  it.each(["product", "service"] as const)(
    "opens a home %s offer without leaving home or loading its owner",
    async (kind) => {
      const api = homeApi({ ...item, kind });
      const { container } = render(<App api={api} />);
      const card = await screen.findByRole("button", {
        name: /Sinov mahsuloti Sinov do‘koni/,
      });
      const scroller = container.querySelector(".app-shell__content")!;
      scroller.scrollTop = 230;
      await userEvent.click(card);
      const dialog = await screen.findByRole("dialog", { name: item.name });
      expect(api.getCatalogItem).toHaveBeenCalledWith("p_test");
      expect(api.getPublicProfile).not.toHaveBeenCalled();
      expect(container.querySelector(".public-home-v1656")).toBeInTheDocument();
      await userEvent.click(
        within(dialog).getByRole("button", { name: "Ma’lumot oynasini yopish" }),
      );
      expect(card).toHaveFocus();
      expect(scroller.scrollTop).toBe(230);
      expect(api.getDistrictOffers).toHaveBeenCalledTimes(1);
    },
  );
  it.each(["product", "service"] as const)(
    "opens the owner first for a searched %s, then opens details only on the profile card",
    async (kind) => {
      const user = userEvent.setup();
      const selected = { ...item, kind };
      const api = homeApi(selected);
      api.getCatalogItem.mockRejectedValue(
        new Error("Mahsulot yoki xizmat topilmadi."),
      );
      api.getPublicProfile.mockResolvedValue({
        kind: "business",
        public_id: "b_test",
        name: "Sinov do‘koni",
        direction: "Savdo",
        activity_type: "",
        public_username: "",
        description: "",
        address: "",
        phone: "",
        image_url: "",
        crop_x: 50,
        crop_y: 50,
        crop_zoom: 1,
        followers_count: 0,
        specialist: null,
        items: [{ ...selected, group_name: "Mevalar" }],
        listings: [],
      });
      api.getDistrictOffers.mockResolvedValue({ items: [], needs_district: false });
      const { container } = render(<App api={api} />);
      const query = await screen.findByPlaceholderText("Nima qidiryapsiz?");
      await user.type(query, "sinov");
      await user.click(screen.getByRole("button", { name: "Qidirish" }));
      await user.click(await screen.findByRole("button", { name: /Sinov mahsuloti/ }));
      const card = await screen.findByRole("button", {
        name: /Sinov mahsuloti haqida/,
      });
      expect(api.getPublicProfile).toHaveBeenCalledWith("business", "b_test");
      expect(card.closest("article")).toHaveClass("is-search-target");
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      expect(api.getCatalogItem).not.toHaveBeenCalled();
      const scroller = container.querySelector(".app-shell__content")!;
      scroller.scrollTop = 310;
      await user.click(card);
      const dialog = screen.getByRole("dialog", { name: selected.name });
      expect(within(dialog).getByText(/To‘liq mahsulot tavsifi/)).toBeVisible();
      await user.click(
        within(dialog).getByRole("button", { name: "Ma’lumot oynasini yopish" }),
      );
      expect(card).toHaveFocus();
      expect(scroller.scrollTop).toBe(310);
      expect(api.getPublicProfile).toHaveBeenCalledTimes(1);
      expect(api.getCatalogItem).not.toHaveBeenCalled();
    },
  );
  it("opens the owner profile from a district offer that includes its business id", async () => {
    const api = homeApi();
    api.getDistrictOffers.mockResolvedValue({
      needs_district: false,
      items: [
        {
          kind: item.kind,
          content_public_id: item.public_id,
          business_public_id: "b_test",
          title: item.name,
          business_name: item.owner_name,
          image: "",
          business_logo: "",
          price: item.price_text,
          unit: item.unit,
        },
      ],
    });
    api.getPublicProfile.mockResolvedValue({
      kind: "business",
      public_id: "b_test",
      name: "Sinov do‘koni",
      direction: "Savdo",
      items: [{ ...item, group_name: "Mevalar" }],
      listings: [],
    });
    render(<App api={api} />);
    await userEvent.click(
      await screen.findByRole("button", { name: /Sinov mahsuloti Sinov do‘koni/ }),
    );
    expect(
      await screen.findByRole("button", { name: /Sinov mahsuloti haqida/ }),
    ).toBeInTheDocument();
    expect(api.getPublicProfile).toHaveBeenCalledWith("business", "b_test");
    expect(api.getCatalogItem).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
  it.each(["product", "service"] as const)(
    "opens a cabinet %s card without mutating it and keeps the actions menu separate",
    async (kind) => {
      const user = userEvent.setup();
      const actions = {
        busy: false,
        form: null,
        draft: {},
        setForm: vi.fn(),
        setDraft: vi.fn(),
        create: vi.fn(),
        patch: vi.fn(),
        remove: vi.fn(),
        action: vi.fn(),
      };
      const row = {
        id: 12,
        name: "banan",
        kind,
        price: 25000,
        unit: "kg",
        description: "To‘liq izoh",
        photo_file: "/media/banan.webp",
      };
      const { container } = render(
        <ItemsEditorView
          {...actions}
          rows={[row]}
          groups={[]}
          query=""
          setQuery={vi.fn()}
          kind="all"
          setKind={vi.fn()}
        />,
      );
      const rail = container.querySelector(".item-hrow")!;
      rail.scrollLeft = 120;
      await user.click(screen.getByRole("button", { name: "banan amallari" }));
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Tahrirlash" })).toBeVisible();
      const card = screen.getByRole("button", { name: /banan haqida/ });
      card.focus();
      await user.keyboard("{Enter}");
      const dialog = screen.getByRole("dialog", { name: "banan" });
      expect(within(dialog).getByText("To‘liq izoh")).toBeVisible();
      expect(within(dialog).getByRole("img", { name: "banan" })).toHaveAttribute(
        "src",
        "/media/banan.webp",
      );
      expect(actions.setForm).not.toHaveBeenCalled();
      expect(actions.patch).not.toHaveBeenCalled();
      expect(actions.remove).not.toHaveBeenCalled();
      await user.click(
        within(dialog).getByRole("button", { name: "Ma’lumot oynasini yopish" }),
      );
      expect(card).toHaveFocus();
      expect(rail.scrollLeft).toBe(120);
      await user.click(card);
      await user.click(
        within(screen.getByRole("dialog")).getByRole("button", { name: "Tahrirlash" }),
      );
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      expect(actions.setDraft).toHaveBeenCalledWith(row);
      expect(actions.setForm).toHaveBeenCalledWith("items:edit");
    },
  );
  it("can retry failed loading and ignores a response after the window closes", async () => {
    const api = homeApi();
    api.getCatalogItem.mockRejectedValueOnce(new Error("Tarmoq xatosi"));
    render(<App api={api} />);
    const card = await screen.findByRole("button", {
      name: /Sinov mahsuloti Sinov do‘koni/,
    });
    await userEvent.click(card);
    expect(await screen.findByRole("alert")).toHaveTextContent("Tarmoq xatosi");
    await userEvent.click(screen.getByRole("button", { name: "Qayta urinish" }));
    await screen.findByRole("dialog", { name: item.name });
    await userEvent.click(
      screen.getByRole("button", { name: "Ma’lumot oynasini yopish" }),
    );
    let finish!: (value: PublicCatalogItem) => void;
    api.getCatalogItem.mockReturnValueOnce(
      new Promise((resolve) => {
        finish = resolve;
      }),
    );
    await userEvent.click(card);
    await screen.findByRole("dialog");
    await userEvent.click(
      screen.getByRole("button", { name: "Ma’lumot oynasini yopish" }),
    );
    finish(item);
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
  it("uses the existing cart action from a public profile item window", async () => {
    const profileItem: PublicProfileItem = { ...item, group_name: "Mevalar" };
    const onAddCartItem = vi.fn();
    const getPublicProfile = vi.fn().mockResolvedValue({
      kind: "business",
      public_id: "b_test",
      name: "Sinov do‘koni",
      direction: "Savdo",
      activity_type: "",
      public_username: "",
      description: "",
      address: "",
      phone: "",
      image_url: "",
      crop_x: 50,
      crop_y: 50,
      crop_zoom: 1,
      followers_count: 0,
      specialist: null,
      items: [profileItem],
      listings: [],
    });
    render(
      <PublicProfile
        authenticated
        kind="business"
        publicId="b_test"
        getPublicProfile={getPublicProfile}
        onAddCartItem={onAddCartItem}
      />,
    );
    const card = await screen.findByRole("button", { name: /Sinov mahsuloti haqida/ });
    await userEvent.click(card);
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "+ Savatga" }),
    );
    expect(onAddCartItem).toHaveBeenCalledWith(profileItem, {
      public_id: "b_test",
      name: "Sinov do‘koni",
    });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(card).toHaveFocus();
  });
});
