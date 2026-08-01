import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ListingDetailV1656 } from "./ListingDetailV1656";
import { ListingPageV1656 } from "./ListingPageV1656";
import { OwnerListingsV1656 } from "./OwnerListingsV1656";
import { PublicListingsV1656 } from "./PublicListingsV1656";
import { SavedListingsV1656 } from "./SavedListingsV1656";


const listing = {
  public_id: "l_1234567890abcdef",
  cat: "uy" as const,
  title: "3 xonali kvartira",
  price: "Kelishilgan",
  descr: "Markazda, barcha qulayliklar bor",
  address: "Qumqo‘rg‘on",
  lat: 37.82,
  lng: 67.58,
  visibility: "all" as const,
  status: "active" as const,
  created_at: "2026-08-02T10:00:00Z",
  media: [{ type: "photo" as const, url: "/home.webp" }],
  owner_kind: "business" as const,
  owner_public_id: "b_1234567890abcdef",
  owner_name: "Muhr",
  is_saved: false,
};


describe("v1656 public E'lonlar", () => {
  it("renders six categories, loads the selected category and opens its accordion", async () => {
    const user = userEvent.setup();
    const api = {
      getListingCounts: vi.fn().mockResolvedValue({ uy: 1 }),
      getPublicListings: vi.fn().mockResolvedValue([listing]),
      toggleListingSave: vi.fn().mockResolvedValue({ saved: true }),
    };
    const onOpenOwner = vi.fn();
    render(
      <PublicListingsV1656
        api={api}
        authenticated
        onOpenOwner={onOpenOwner}
      />,
    );

    expect(screen.getByRole("heading", { name: "E’lonlar" })).toBeInTheDocument();
    expect(screen.getByText("Toifani tanlang — tegishli e’lonlar shu oynada chiqadi."))
      .toBeInTheDocument();
    expect(screen.getAllByText(/ta e'lon$/)).toHaveLength(6);

    await user.click(screen.getByRole("button", { name: /Uy-joy/ }));
    expect(await screen.findByText("3 xonali kvartira")).toBeInTheDocument();
    expect(api.getPublicListings).toHaveBeenCalledWith({ cat: "uy" });
    expect(screen.getByRole("button", { name: "Yangi" })).toHaveClass("on");

    await user.click(screen.getByRole("button", { name: /3 xonali kvartira/ }));
    expect(screen.getByText("Markazda, barcha qulayliklar bor")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bog'lanish" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "🔖 Saqlash" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Bog'lanish" }));
    expect(onOpenOwner).toHaveBeenCalledWith("business", "b_1234567890abcdef");
    await user.click(screen.getByRole("button", { name: "🔖 Saqlash" }));
    expect(await screen.findByRole("button", { name: "✓ Saqlangan" }))
      .toBeInTheDocument();
  });

  it("keeps the exact v1656 empty-category text", async () => {
    const user = userEvent.setup();
    render(
      <PublicListingsV1656
        api={{
          getListingCounts: vi.fn().mockResolvedValue({}),
          getPublicListings: vi.fn().mockResolvedValue([]),
          toggleListingSave: vi.fn(),
        }}
        authenticated={false}
        onOpenOwner={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Texnika/ }));
    expect(await screen.findByRole("heading", { name: "Bu toifada e'lon yo'q" }))
      .toBeInTheDocument();
    expect(screen.getByText("Texnika bo'yicha hozircha e'lonlar joylanmagan."))
      .toBeInTheDocument();
  });

  it("opens listing photos in the v1656 media viewer", async () => {
    const user = userEvent.setup();
    render(
      <ListingDetailV1656
        listing={listing}
        onContact={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Rasmni katta ko‘rish" }));

    const viewer = screen.getByRole("dialog", { name: "E'lon mediasi" });
    expect(viewer).toHaveClass("image-viewer", "on");
    expect(screen.getByAltText("Kattalashtirilgan rasm")).toHaveAttribute(
      "src",
      "/home.webp",
    );
    await user.click(screen.getByRole("button", { name: "Yopish" }));
    expect(screen.queryByRole("dialog", { name: "E'lon mediasi" }))
      .not.toBeInTheDocument();
  });

  it("keeps the standalone v1656 listing detail surface", async () => {
    const { container } = render(
      <ListingPageV1656
        authenticated
        getPublicListing={vi.fn().mockResolvedValue({ ...listing, media: [] })}
        publicId={listing.public_id}
        toggleListingSave={vi.fn()}
        onNeedLogin={vi.fn()}
        onOpenOwner={vi.fn()}
      />,
    );

    expect(await screen.findByRole("heading", { name: listing.title }))
      .toHaveClass("biz-title");
    expect(container.querySelector(".biz-hero .emoji")).toHaveTextContent("📦");
    expect(container.querySelector(".biz-sub")).toHaveTextContent("Kelishilgan");
    expect(container.querySelector(".actionbar")).toBeInTheDocument();
  });

  it("shows the API reason when saving a listing fails", async () => {
    const user = userEvent.setup();
    render(
      <PublicListingsV1656
        api={{
          getListingCounts: vi.fn().mockResolvedValue({ uy: 1 }),
          getPublicListings: vi.fn().mockResolvedValue([listing]),
          toggleListingSave: vi.fn().mockRejectedValue(new Error("Saqlashda xatolik")),
        }}
        authenticated
        onOpenOwner={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Uy-joy/ }));
    await user.click(await screen.findByRole("button", { name: /3 xonali kvartira/ }));
    await user.click(screen.getByRole("button", { name: "🔖 Saqlash" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Saqlashda xatolik");
  });
});


describe("v1656 owner E'lonlar", () => {
  it("keeps user form texts, required-title message and delete confirmation", async () => {
    const user = userEvent.setup();
    const api = {
      getMyListings: vi.fn().mockResolvedValue([listing]),
      createListing: vi.fn(),
      deleteListing: vi.fn().mockResolvedValue(undefined),
      createUploadGrant: vi.fn(),
      uploadGrantedFile: vi.fn(),
    };
    render(<OwnerListingsV1656 api={api} actor="user" onBack={vi.fn()} />);

    expect(await screen.findByText("3 xonali kvartira")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reklamalarim" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "E'lonlarim" })).toHaveClass("on");

    await user.click(screen.getByRole("button", { name: "+ E'lon joylash" }));
    expect(screen.getByPlaceholderText("Masalan: Nexia 3 sotiladi"))
      .toBeInTheDocument();
    expect(screen.getByPlaceholderText("Narx yoki «kelishilgan»"))
      .toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Joylash" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Sarlavha kiritilishi shart.");

    expect(screen.queryByRole("button", { name: "Bekor qilish" }))
      .not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Orqaga" }));
    expect(screen.getByRole("button", { name: "+ E'lon joylash" }))
      .toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "E'lonni o'chirish" }));
    expect(screen.getByText("Bu e'lon o'chirilsinmi?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "O'chirish" }));
    await waitFor(() => expect(api.deleteListing).toHaveBeenCalledWith(listing.public_id));
  });

  it("shows the business-only visibility choices", async () => {
    const user = userEvent.setup();
    render(
      <OwnerListingsV1656
        api={{
          getMyListings: vi.fn().mockResolvedValue([]),
          createListing: vi.fn(),
          deleteListing: vi.fn(),
          createUploadGrant: vi.fn(),
          uploadGrantedFile: vi.fn(),
        }}
        actor="business"
        onBack={vi.fn()}
      />,
    );

    await user.click(await screen.findByRole("button", { name: "+ E'lon joylash" }));
    expect(screen.getByPlaceholderText("Masalan: 3 xonali kvartira"))
      .toBeInTheDocument();
    expect(screen.getByText("Butun platformaga")).toBeInTheDocument();
    expect(screen.getByText("Faqat sahifam mehmonlariga")).toBeInTheDocument();
  });

  it("shows uploaded media previews and lets the owner remove one", async () => {
    const user = userEvent.setup();
    const api = {
      getMyListings: vi.fn().mockResolvedValue([]),
      createListing: vi.fn(),
      deleteListing: vi.fn(),
      createUploadGrant: vi.fn().mockResolvedValue({
        object_key: "private/user/7/listings/photo.png",
        upload_url: "https://r2.example/upload",
        method: "PUT" as const,
        headers: { "Content-Type": "image/png" },
        expires_in_seconds: 900,
      }),
      uploadGrantedFile: vi.fn().mockResolvedValue(undefined),
    };
    render(<OwnerListingsV1656 api={api} actor="user" onBack={vi.fn()} />);

    await user.click(await screen.findByRole("button", { name: "+ E'lon joylash" }));
    await user.upload(
      screen.getByLabelText("E'lon media fayllari"),
      new File(["image"], "photo.png", { type: "image/png" }),
    );

    expect(await screen.findByRole("button", { name: "Rasmni katta ko‘rish" }))
      .toHaveClass("listing-upload-open");
    expect(screen.getByText("RASM")).toHaveClass("listing-upload-status");
    await user.click(screen.getByRole("button", { name: "Mediani olib tashlash" }));
    expect(screen.queryByRole("button", { name: "Rasmni katta ko‘rish" }))
      .not.toBeInTheDocument();
  });
});


describe("v1656 saved E'lonlar", () => {
  it("opens a saved listing from its card", async () => {
    const user = userEvent.setup();
    const onOpenListing = vi.fn();
    render(
      <SavedListingsV1656
        getSavedListings={vi.fn().mockResolvedValue([{ ...listing, is_saved: true }])}
        legacyRows={[]}
        onBack={vi.fn()}
        onOpenListing={onOpenListing}
      />,
    );

    await user.click(await screen.findByRole("button", { name: /3 xonali kvartira/ }));
    expect(onOpenListing).toHaveBeenCalledWith(listing.public_id);
  });
});
