import { fireEvent, render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { HomeMapV1656 } from "./HomeMapV1656";


describe("HomeMapV1656", () => {
  it("renders both followed business pins and opens the selected profile", async () => {
    const onOpenResult = vi.fn();
    render(
      <HomeMapV1656
        businesses={[
          {
            id: 41,
            public_id: "b_first",
            name: "Birinchi biznes",
            yon: "Savdo",
            tur: "Do‘kon",
            lat: 37.82,
            lng: 67.58,
            logo_file: "",
            logo_x: 50,
            logo_y: 50,
            logo_zoom: 1,
            address: "Qumqo‘rg‘on",
            source: "obuna",
          },
          {
            id: 42,
            public_id: "b_second",
            name: "Ikkinchi biznes",
            yon: "Savdo",
            tur: "Do‘kon",
            lat: 37.83,
            lng: 67.59,
            logo_file: "",
            logo_x: 50,
            logo_y: 50,
            logo_zoom: 1,
            address: "Qumqo‘rg‘on",
            source: "obuna",
          },
        ]}
        district="Qumqo‘rg‘on"
        resultItems={null}
        specialists={[]}
        onCloseResults={vi.fn()}
        onOpenResult={onOpenResult}
      />,
    );

    await waitFor(() => {
      expect(document.querySelectorAll(".leaflet-marker-pane .leaflet-pin"))
        .toHaveLength(2);
    });
    const pins = document.querySelectorAll(".leaflet-marker-pane .leaflet-pin");
    fireEvent.click(pins[1]!);

    expect(onOpenResult).toHaveBeenCalledWith("business", "b_second");
  });

  it("uses the exact direction pin and migrated logo crop", async () => {
    render(
      <HomeMapV1656
        businesses={[{
          id: 41,
          public_id: "b_41",
          name: "Nafis salon",
          yon: "Maishiy xizmatlar",
          tur: "Go‘zallik saloni",
          lat: 37.82,
          lng: 67.58,
          logo_file: "/media/logo.webp",
          logo_x: 62,
          logo_y: 48,
          logo_zoom: 1.2,
          address: "Qumqo‘rg‘on",
          source: "public",
        }]}
        center={{ latitude: 37.8, longitude: 67.6 }}
        district="Qumqo‘rg‘on"
        resultItems={null}
        specialists={[]}
        onCloseResults={vi.fn()}
        onOpenResult={vi.fn()}
      />,
    );

    expect(document.querySelector("#taxiBtn")).toHaveAttribute("hidden");
    expect(document.querySelector("#centerPin")).toHaveAttribute("hidden");

    await waitFor(() => {
      expect(document.querySelector(".leaflet-marker-pane .dot"))
        .toHaveStyle({ background: "#EC4899" });
    });
    expect(document.querySelector(".leaflet-marker-pane .pin-fallback"))
      .toHaveTextContent("💇");
    const image = document.querySelector<HTMLImageElement>(
      ".leaflet-marker-pane .dot img",
    );
    expect(image).toHaveAttribute("src", "/media/logo.webp");
    expect(image?.getAttribute("style")).toContain("width:120%");
    expect(image?.getAttribute("style")).toContain("left:-24.4%");
  });

  it("uses government specialist color, initial, avatar, and exact attribution", async () => {
    render(
      <HomeMapV1656
        businesses={[]}
        district="Qumqo‘rg‘on"
        resultItems={null}
        specialists={[{
          user_id: 71,
          public_id: "u_71",
          name: "Aziza Karimova",
          kasb: "Shifokor",
          is_gov: true,
          lat: 37.83,
          lng: 67.59,
          avatar_file: "/media/avatar.webp",
          avatar_x: 50,
          avatar_y: 50,
          avatar_zoom: 1,
          source: "obuna",
        }]}
        onCloseResults={vi.fn()}
        onOpenResult={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(document.querySelector(".leaflet-marker-pane .dot"))
        .toHaveStyle({ background: "#2563EB" });
    });
    expect(document.querySelector(".leaflet-marker-pane .pin-fallback"))
      .toHaveTextContent("A");
    expect(document.querySelector(".leaflet-marker-pane .dot img"))
      .toHaveAttribute("src", "/media/avatar.webp");
    expect(document.querySelector(
      ".leaflet-control-attribution a[href='https://www.openstreetmap.org/copyright']",
    )).toHaveTextContent("OpenStreetMap");
  });

  it("groups searched products by business and opens the business marker", async () => {
    const onOpenResult = vi.fn();
    const mapPoint = {
      business_public_id: "b_muhr",
      business_name: "Muhr",
      latitude: 37.8234,
      longitude: 67.5789,
    };
    render(
      <HomeMapV1656
        businesses={[]}
        district="Qumqo‘rg‘on"
        resultItems={[
          {
            kind: "service",
            public_id: "s_english",
            name: "ingliz tili",
            public_username: "",
            description: "",
            direction: "Ta'lim faoliyati",
            activity_type: "O'quv markazi",
            region: "Surxondaryo viloyati",
            district: "Qumqo'rg'on tumani",
            mahalla: "",
            image_url: "/media/muhr.webp",
            price_text: "350000",
            owner_label: "Muhr",
            map_point: mapPoint,
          },
          {
            kind: "product",
            public_id: "p_book",
            name: "Kitob",
            public_username: "",
            description: "",
            direction: "Ta'lim faoliyati",
            activity_type: "O'quv markazi",
            region: "Surxondaryo viloyati",
            district: "Qumqo'rg'on tumani",
            mahalla: "",
            image_url: "",
            price_text: "50000",
            owner_label: "Muhr",
            map_point: mapPoint,
          },
        ]}
        specialists={[]}
        onCloseResults={vi.fn()}
        onOpenResult={onOpenResult}
      />,
    );

    await waitFor(() => {
      expect(document.querySelectorAll(".leaflet-marker-pane .leaflet-pin"))
        .toHaveLength(1);
    });
    expect(document.querySelector(".leaflet-marker-pane .plabel"))
      .toHaveTextContent("Muhr35000050000");
    expect(document.querySelector(".leaflet-marker-pane .dot img"))
      .toHaveAttribute("src", "/media/muhr.webp");

    fireEvent.click(document.querySelector(".leaflet-marker-pane .leaflet-pin")!);
    expect(onOpenResult).toHaveBeenCalledWith("business", "b_muhr");
  });

  it("keeps a searched E'lon as its own marker and opens the E'lon", async () => {
    const onOpenResult = vi.fn();
    render(
      <HomeMapV1656
        businesses={[]}
        district="Qumqo‘rg‘on"
        resultItems={[{
          kind: "listing",
          public_id: "l_flat",
          name: "3 xonali kvartira",
          public_username: "",
          description: "Markazda",
          direction: "E'lonlar",
          activity_type: "Uy-joy",
          region: "Surxondaryo viloyati",
          district: "Qumqo'rg'on tumani",
          mahalla: "",
          image_url: "",
          price_text: "250 000 000 so'm",
          owner_label: "Muhr",
          map_point: {
            business_public_id: "b_muhr",
            business_name: "Muhr",
            latitude: 37.8234,
            longitude: 67.5789,
          },
        }]}
        specialists={[]}
        onCloseResults={vi.fn()}
        onOpenResult={onOpenResult}
      />,
    );

    await waitFor(() => {
      expect(document.querySelector(".leaflet-marker-pane .plabel"))
        .toHaveTextContent("3 xonali kvartira");
    });
    fireEvent.click(document.querySelector(".leaflet-marker-pane .leaflet-pin")!);

    expect(onOpenResult).toHaveBeenCalledWith("listing", "l_flat");
  });
});
