import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { HomeMapV1656 } from "./HomeMapV1656";


describe("HomeMapV1656", () => {
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
});
