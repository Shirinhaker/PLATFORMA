import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
        unit: "dona",
        note: "Issiq non",
        image_url: "",
        group_name: "Oziq-ovqat",
        queue_enabled: false,
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

  it("uses the direction action guard and the exact sticky cart copy", async () => {
    const user = userEvent.setup();
    const onAddCartItem = vi.fn();
    const onBookQueue = vi.fn();
    const onOpenCart = vi.fn();
    const getPublicProfile = vi.fn().mockResolvedValue({
      kind: "business",
      public_id: "b_shifo",
      name: "Shifo",
      public_username: "",
      description: "",
      direction: "Tibbiy xizmatlar",
      activity_type: "Klinika",
      address: "",
      phone: "",
      image_url: "",
      crop_x: 50,
      crop_y: 50,
      crop_zoom: 1,
      followers_count: 0,
      specialist: null,
      items: [{
        kind: "service",
        public_id: "s_qabul",
        name: "Qabul",
        price_text: "20 000 so'm",
        unit: "marta",
        note: "",
        image_url: "",
        group_name: "",
        queue_enabled: true,
        queue_provider_count: 1,
      }, {
        kind: "product",
        public_id: "p_dori",
        name: "Dori",
        price_text: "10 000 so'm",
        unit: "dona",
        note: "",
        image_url: "",
        group_name: "",
        queue_enabled: false,
      }],
      listings: [],
    });
    render(
      <PublicProfileV1656
        authenticated
        cart={{
          provider_public_id: "b_shifo",
          provider_name: "Shifo",
          items: {
            p_dori: {
              public_id: "p_dori",
              kind: "product",
              name: "Dori",
              price_text: "10 000 so'm",
              unit: "dona",
              qty: 2,
            },
          },
        }}
        kind="business"
        publicId="b_shifo"
        getPublicProfile={getPublicProfile}
        onAddCartItem={onAddCartItem}
        onBookQueue={onBookQueue}
        onOpenCart={onOpenCart}
      />,
    );

    expect(await screen.findByRole("button", { name: "Navbat olish" }))
      .toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Navbat olish" }));
    expect(onBookQueue).toHaveBeenCalledWith({
      businessPublicId: "b_shifo",
      itemPublicId: "s_qabul",
      serviceName: "Qabul",
      direction: "Tibbiy xizmatlar",
    });
    expect(screen.getByRole("button", { name: "✓ Savatda: 2" }))
      .toBeInTheDocument();
    expect(document.getElementById("bizCartBarTotal"))
      .toHaveTextContent("20 000 so'm");
    await user.click(screen.getByRole("button", { name: "✓ Savatda: 2" }));
    expect(onAddCartItem).toHaveBeenCalledWith(
      expect.objectContaining({ public_id: "p_dori" }),
      { public_id: "b_shifo", name: "Shifo" },
    );
    await user.click(screen.getByRole("button", { name: /🛒 Savatcha: 1 ta/ }));
    expect(onOpenCart).toHaveBeenCalledOnce();
  });

  it("checks the provider count before the login guard with exact v1656 copy", async () => {
    const user = userEvent.setup();
    const onBookQueue = vi.fn();
    const onNeedLogin = vi.fn();
    const onQueueMessage = vi.fn();
    const getPublicProfile = vi.fn().mockResolvedValue({
      kind: "business",
      public_id: "b_shifo",
      name: "Shifo",
      public_username: "",
      description: "",
      direction: "Tibbiy xizmatlar",
      activity_type: "Klinika",
      address: "",
      phone: "",
      image_url: "",
      crop_x: 50,
      crop_y: 50,
      crop_zoom: 1,
      followers_count: 0,
      specialist: null,
      items: [{
        kind: "service",
        public_id: "s_qabul",
        name: "Qabul",
        price_text: "",
        unit: "marta",
        note: "",
        image_url: "",
        group_name: "",
        queue_enabled: true,
        queue_provider_count: 0,
      }],
      listings: [],
    });

    render(
      <PublicProfileV1656
        kind="business"
        publicId="b_shifo"
        getPublicProfile={getPublicProfile}
        onBookQueue={onBookQueue}
        onNeedLogin={onNeedLogin}
        onQueueMessage={onQueueMessage}
      />,
    );

    await user.click(await screen.findByRole("button", { name: "Navbat olish" }));
    expect(onQueueMessage).toHaveBeenCalledWith("Shifokor hali biriktirilmagan.");
    expect(onNeedLogin).not.toHaveBeenCalled();
    expect(onBookQueue).not.toHaveBeenCalled();
  });
});
