import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PublicProfileV1656 } from "./PublicProfileV1656";


describe("PublicProfileV1656", () => {
  it("renders the v1656 public business profile returned by its public id", async () => {
    const getPublicProfile = vi.fn().mockResolvedValue({
      kind: "business",
      public_id: "b_turon",
      name: "Turon savdo",
      public_username: "turonsavdo",
      description: "Sifatli mahsulotlar",
      direction: "Savdo",
      activity_type: "Do‘kon",
      address: "Qumqo‘rg‘on",
      phone: "+998901234567",
      image_url: "/media/turon.webp",
      crop_x: 50,
      crop_y: 50,
      crop_zoom: 1,
      followers_count: 17,
      specialist: null,
      items: [{
        kind: "product",
        public_id: "p_non",
        name: "Non",
        price_text: "4 000 so‘m",
        note: "Issiq non",
        image_url: "",
        group_name: "Oziq-ovqat",
      }],
      listings: [{
        public_id: "l_un",
        title: "Un sotiladi",
        price_text: "Kelishiladi",
        description: "50 kg",
        address: "Qumqo‘rg‘on",
        image_url: "",
      }],
    });

    render(
      <PublicProfileV1656
        kind="business"
        publicId="b_turon"
        getPublicProfile={getPublicProfile}
      />,
    );

    expect(await screen.findByText("Turon savdo")).toBeInTheDocument();
    expect(screen.getByText("Savdo · Do‘kon")).toBeInTheDocument();
    expect(screen.getByText("📍 Qumqo‘rg‘on")).toBeInTheDocument();
    expect(screen.getByText("📞 +998901234567")).toBeInTheDocument();
    expect(screen.getByText("17 obunachi")).toBeInTheDocument();
    expect(screen.getByText("Sifatli mahsulotlar")).toBeInTheDocument();
    expect(screen.getByText("Mahsulot va xizmatlar")).toBeInTheDocument();
    expect(screen.getByText("Non")).toBeInTheDocument();
    expect(screen.getByText("E'lonlari")).toBeInTheDocument();
    expect(screen.getByText("Un sotiladi")).toBeInTheDocument();
    expect(getPublicProfile).toHaveBeenCalledWith("business", "b_turon");
  });
});
