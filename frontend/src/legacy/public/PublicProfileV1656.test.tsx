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
      queue_total: 3,
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
        today_queue_count: 3,
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
    expect(screen.getByText("👥 Bugungi jami navbat: 3 ta"))
      .toBeInTheDocument();
    expect(screen.getByText("👥 Bugungi navbat: 3 ta"))
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

  it("shows v1656 course metadata and opens enrollment only while admission is open", async () => {
    const user = userEvent.setup();
    const onEnrollCourse = vi.fn();
    const getPublicProfile = vi.fn().mockResolvedValue({
      kind: "business",
      public_id: "b_english",
      name: "English House",
      public_username: "",
      description: "",
      direction: "Ta'lim faoliyati",
      activity_type: "O'quv markazi",
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
        public_id: "s_english",
        name: "Ingliz tili",
        price_text: "500 000 so'm",
        unit: "oy",
        note: "Haftada 3 kun",
        image_url: "",
        group_name: "",
        queue_enabled: false,
        course_mode: "hybrid",
        course_duration: "3 oy",
        lesson_duration: 90,
        age_from: 12,
        age_to: 18,
        course_level: "beginner",
        enrollment_status: "open",
      }, {
        kind: "service",
        public_id: "s_math",
        name: "Matematika",
        price_text: "",
        unit: "oy",
        note: "",
        image_url: "",
        group_name: "",
        queue_enabled: false,
        course_mode: "offline",
        course_duration: "",
        lesson_duration: 60,
        age_from: 0,
        age_to: 0,
        course_level: "all",
        enrollment_status: "closed",
      }],
      listings: [],
    });

    render(
      <PublicProfileV1656
        authenticated
        kind="business"
        publicId="b_english"
        getPublicProfile={getPublicProfile}
        onEnrollCourse={onEnrollCourse}
      />,
    );

    expect(await screen.findByText("Aralash · 3 oy · 90 daqiqa"))
      .toBeInTheDocument();
    expect(screen.getByText("Yosh: 12–18")).toBeInTheDocument();
    expect(screen.getByText("Qabul ochiq")).toBeInTheDocument();
    expect(screen.getByText("Qabul yopiq")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Kursga yozilish" }))
      .toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Kursga yozilish" }));
    expect(onEnrollCourse).toHaveBeenCalledWith({
      itemPublicId: "s_english",
      courseName: "Ingliz tili",
    });
  });

  it("sends guests to login before opening the course form", async () => {
    const user = userEvent.setup();
    const onEnrollCourse = vi.fn();
    const onNeedCourseLogin = vi.fn();
    const getPublicProfile = vi.fn().mockResolvedValue({
      kind: "business",
      public_id: "b_english",
      name: "English House",
      public_username: "",
      description: "",
      direction: "Ta'lim faoliyati",
      activity_type: "O'quv markazi",
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
        public_id: "s_english",
        name: "Ingliz tili",
        price_text: "",
        unit: "oy",
        note: "",
        image_url: "",
        group_name: "",
        queue_enabled: false,
        enrollment_status: "open",
      }],
      listings: [],
    });

    render(
      <PublicProfileV1656
        kind="business"
        publicId="b_english"
        getPublicProfile={getPublicProfile}
        onEnrollCourse={onEnrollCourse}
        onNeedCourseLogin={onNeedCourseLogin}
      />,
    );

    await user.click(await screen.findByRole("button", {
      name: "Kursga yozilish",
    }));
    expect(onNeedCourseLogin).toHaveBeenCalledOnce();
    expect(onEnrollCourse).not.toHaveBeenCalled();
  });
});
