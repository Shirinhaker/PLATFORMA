import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SpecialistProfile } from "../api/types";
import { Specialist, type SpecialistApi } from "./Specialist";

const leaflet = vi.hoisted(() => {
  const map = {
    setView: vi.fn(),
    on: vi.fn(),
    getCenter: vi.fn(() => ({ lat: 37.8389, lng: 67.5834 })),
    invalidateSize: vi.fn(),
    remove: vi.fn(),
  };
  map.setView.mockReturnValue(map);
  return {
    map,
    mapFactory: vi.fn(() => map),
    tileLayer: vi.fn(() => ({ addTo: vi.fn() })),
  };
});

vi.mock("leaflet", () => ({
  default: {
    map: leaflet.mapFactory,
    tileLayer: leaflet.tileLayer,
  },
}));

const PROFILE: SpecialistProfile = {
  exists: true,
  profession: "Santexnik",
  description: "10 yillik tajriba",
  visible: true,
  latitude: 37.8389,
  longitude: 67.5834,
  review_count: 2,
  credentials: [
    {
      id: 1,
      image_url: "/diplom.webp",
      position: 0,
      created_at: "2026-08-10T09:00:00Z",
    },
  ],
  offers: [
    {
      id: 2,
      kind: "service",
      name: "Ta'mirlash",
      price_text: "100 000 so'm",
      note: "Uyga borib",
      image_url: "/service.webp",
      image_object_key: "private/user/7/specialist_offer_image/service.webp",
      created_at: "2026-08-10T09:00:00Z",
    },
  ],
  portfolio: [
    {
      id: 3,
      media_type: "video",
      media_url: "/work.mp4",
      created_at: "2026-08-10T09:00:00Z",
    },
  ],
};

function api(): SpecialistApi {
  return {
    getMySpecialist: vi.fn().mockResolvedValue(PROFILE),
    updateMySpecialist: vi.fn().mockResolvedValue(PROFILE),
    addSpecialistCredential: vi.fn().mockResolvedValue({ ok: true, id: 9 }),
    deleteSpecialistCredential: vi.fn().mockResolvedValue(undefined),
    createSpecialistOffer: vi.fn().mockResolvedValue({ ok: true, id: 10 }),
    updateSpecialistOffer: vi.fn().mockResolvedValue({ ok: true }),
    deleteSpecialistOffer: vi.fn().mockResolvedValue(undefined),
    addSpecialistPortfolio: vi.fn().mockResolvedValue({ ok: true, id: 11 }),
    deleteSpecialistPortfolio: vi.fn().mockResolvedValue(undefined),
    createUploadGrant: vi.fn().mockResolvedValue({
      object_key: "private/user/7/specialist_credential/new.webp",
      upload_url: "https://upload.test",
      method: "PUT",
      headers: { "Content-Type": "image/webp" },
      expires_in_seconds: 900,
    }),
    uploadGrantedFile: vi.fn().mockResolvedValue(undefined),
  };
}

describe("Specialist", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the exact v1656 sections and saves the typed profile", async () => {
    const specialistApi = api();
    const onReviews = vi.fn();
    render(<Specialist api={specialistApi} onBack={vi.fn()} onReviews={onReviews} />);

    expect(
      await screen.findByRole("heading", { name: "Mutaxassisligim" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Mutaxassislikni tasdiqlovchi hujjatlar"),
    ).toBeInTheDocument();
    expect(screen.getByText("Xizmatlarim va mahsulotlarim")).toBeInTheDocument();
    expect(screen.getByText("Bajargan ishlarim")).toBeInTheDocument();
    expect(screen.getByText("Ta'mirlash")).toBeInTheDocument();
    expect(screen.getByText("▶ VIDEO")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Mijoz fikrlari 2/ }));
    expect(onReviews).toHaveBeenCalledOnce();

    fireEvent.change(screen.getByPlaceholderText(/Shifokor/), {
      target: { value: "Usta" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Saqlash" }));
    await waitFor(() =>
      expect(specialistApi.updateMySpecialist).toHaveBeenCalledWith(
        expect.objectContaining({ profession: "Usta", visible: true }),
      ),
    );
  });

  it("uploads a credential through R2 and attaches its object key", async () => {
    const specialistApi = api();
    const { container } = render(<Specialist api={specialistApi} onBack={vi.fn()} />);
    await screen.findByText("Hujjat rasmi qo‘shish");
    const input = container.querySelector(
      'input[accept="image/jpeg,image/png,image/webp"][multiple]',
    ) as HTMLInputElement;
    const file = new File(["image"], "diplom.webp", { type: "image/webp" });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() =>
      expect(specialistApi.createUploadGrant).toHaveBeenCalledWith(
        expect.objectContaining({ purpose: "specialist_credential" }),
      ),
    );
    await waitFor(() =>
      expect(specialistApi.addSpecialistCredential).toHaveBeenCalledWith(
        "private/user/7/specialist_credential/new.webp",
      ),
    );
  });

  it("opens and updates an existing service card", async () => {
    const specialistApi = api();
    render(<Specialist api={specialistApi} onBack={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: /Ta'mirlash/ }));
    expect(
      screen.getByRole("heading", { name: "Taklifni tahrirlash" }),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText(/Huquqiy maslahat/), {
      target: { value: "Tezkor ta'mirlash" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Saqlash" }));
    await waitFor(() =>
      expect(specialistApi.updateSpecialistOffer).toHaveBeenCalledWith(
        2,
        expect.objectContaining({ name: "Tezkor ta'mirlash" }),
      ),
    );
  });
});
