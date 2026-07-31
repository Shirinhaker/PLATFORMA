import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  buildAddrText,
  BusinessLocationPickerV1656View,
  pickReturnScreen,
} from "./BusinessLocationPickerV1656View";
import { BusinessProfile } from "./BusinessProfile";


const leaflet = vi.hoisted(() => {
  const state = { center: { lat: 41.311, lng: 69.28 }, zoom: 14 };
  const map = {
    getCenter: vi.fn(() => ({ ...state.center })),
    getZoom: vi.fn(() => state.zoom),
    invalidateSize: vi.fn(),
    remove: vi.fn(),
    setView: vi.fn((
      point: [number, number] | { lat: number; lng: number },
      zoom: number,
    ) => {
      state.center = Array.isArray(point)
        ? { lat: point[0], lng: point[1] }
        : { ...point };
      state.zoom = zoom;
      return map;
    }),
  };
  const tileLayer = { addTo: vi.fn() };
  return {
    map,
    mapFactory: vi.fn(() => map),
    state,
    tileLayer,
    tileLayerFactory: vi.fn(() => tileLayer),
  };
});

vi.mock("leaflet", () => ({
  default: {
    map: leaflet.mapFactory,
    tileLayer: leaflet.tileLayerFactory,
  },
}));


beforeEach(() => {
  localStorage.clear();
  leaflet.state.center = { lat: 41.311, lng: 69.28 };
  leaflet.state.zoom = 14;
  vi.clearAllMocks();
});


describe("v1656 pickloc parity", () => {
  it("builds the same readable address fallback as v1656", () => {
    expect(buildAddrText({
      city_district: "",
      county: "Qumqo‘rg‘on tumani",
      state: "Surxondaryo viloyati",
      road: "Beruniy ko‘chasi",
    })).toBe("Beruniy ko‘chasi, Qumqo‘rg‘on tumani, Surxondaryo viloyati");
  });

  it("keeps the pin tip at the container center while the map moves", async () => {
    render(
      <BusinessLocationPickerV1656View
        prefix="be"
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    await waitFor(() => expect(leaflet.mapFactory).toHaveBeenCalled());
    const mapNode = document.getElementById("pickMap");
    const pin = document.getElementById("pickPin");
    expect(mapNode).not.toBeNull();
    expect(pin).not.toBeNull();
    expect(mapNode?.contains(pin)).toBe(false);
    expect(mapNode?.nextElementSibling).toBe(pin);

    const before = {
      left: pin?.style.left,
      top: pin?.style.top,
      transform: pin?.style.transform,
    };
    leaflet.state.center = { lat: 37.8389334, lng: 67.5834525 };
    expect({
      left: pin?.style.left,
      top: pin?.style.top,
      transform: pin?.style.transform,
    }).toEqual(before);
    expect(before).toEqual({
      left: "50%",
      top: "50%",
      transform: "translate(-50%,-100%)",
    });
  });

  it("saves the current Leaflet center when the location is confirmed", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(
      <BusinessLocationPickerV1656View
        prefix="be"
        onCancel={vi.fn()}
        onConfirm={onConfirm}
      />,
    );
    await waitFor(() => expect(leaflet.mapFactory).toHaveBeenCalled());
    leaflet.state.center = { lat: 37.838933493659454, lng: 67.58345251326438 };

    await user.click(screen.getByRole("button", { name: "✅ Shu joyni tanlash" }));

    expect(onConfirm).toHaveBeenCalledWith(
      { latitude: 37.838933493659454, longitude: 67.58345251326438 },
      "cab-elon-form",
    );
  });

  it("invalidates after screen animation and viewport resize without shifting center", async () => {
    render(
      <BusinessLocationPickerV1656View
        prefix="ue"
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    await waitFor(() => expect(leaflet.mapFactory).toHaveBeenCalled());
    leaflet.state.center = { lat: 40.5, lng: 66.75 };
    const picker = document.querySelector('[data-screen="pickloc"]');
    expect(picker).not.toBeNull();

    fireEvent.animationEnd(picker as Element);
    await waitFor(() => expect(leaflet.map.invalidateSize).toHaveBeenCalledWith({
      pan: false,
    }));
    expect(leaflet.state.center).toEqual({ lat: 40.5, lng: 66.75 });

    const calls = leaflet.map.invalidateSize.mock.calls.length;
    fireEvent(window, new Event("resize"));
    await waitFor(() => expect(leaflet.map.invalidateSize.mock.calls.length)
      .toBeGreaterThan(calls));
    expect(leaflet.state.center).toEqual({ lat: 40.5, lng: 66.75 });
  });

  it.each([
    ["bp", "cab-profil"],
    ["be", "cab-elon-form"],
    ["ue", "ucab-elon-form"],
  ] as const)("returns %s to %s", async (prefix, expectedScreen) => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(
      <BusinessLocationPickerV1656View
        prefix={prefix}
        onCancel={onCancel}
        onConfirm={vi.fn()}
      />,
    );

    expect(pickReturnScreen(prefix)).toBe(expectedScreen);
    await user.click(screen.getByRole("button", { name: "Bekor qilish" }));
    expect(onCancel).toHaveBeenCalledWith(expectedScreen);
  });

  it("keeps the exact v1656 copy and button classes", () => {
    render(
      <BusinessLocationPickerV1656View
        prefix="bp"
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    expect(screen.getByText("Xaritani suring — markerni joyga to'g'rilang"))
      .toBeInTheDocument();
    expect(screen.getByRole("button", { name: "✅ Shu joyni tanlash" }))
      .toHaveClass("btn", "btn-primary", "btn-block");
    expect(screen.getByRole("button", { name: "Bekor qilish" }))
      .toHaveClass("btn", "btn-soft", "btn-block");
    expect(document.querySelector('[data-screen="pickloc"]'))
      .toHaveClass("screen", "active");
  });

  it("opens from cab-profil and saves bp center with its resolved address", async () => {
    const user = userEvent.setup();
    const identity = {
      account_id: 7,
      account_type: "business" as const,
      name: "Muhr",
      login: "b_muhr",
      csrf_token: "csrf",
      expires_at: "2026-08-30T00:00:00Z",
    };
    const profile = {
      account_id: 7,
      name: "Muhr",
      phone: "912377784",
      description: "",
      public_username: "muhr1",
      direction: "Savdo",
      activity_type: "Oziq-ovqat do'koni",
      address: "Eski manzil",
      latitude: 41.311,
      longitude: 69.28,
      work_hours: {},
      pay_card: "",
      pay_holder: "",
      pay_qr_object_key: "",
      pay_qr_url: "",
      director: "",
      tax_id: "",
      logo_object_key: "",
      logo_url: "",
      logo_x: 50,
      logo_y: 50,
      logo_zoom: 1,
      followers_count: 0,
      following_count: 0,
      rating_sum: 0,
      rating_count: 0,
      map_visible: true,
      dashboard_snapshot: {},
      recent_activity: [],
      cabinet_payload: {},
    };
    const updateBusinessProfile = vi.fn().mockImplementation(async (patch) => ({
      ...profile,
      ...patch,
    }));
    const client = {
      getSession: vi.fn().mockResolvedValue(identity),
      getBusinessProfile: vi.fn().mockResolvedValue(profile),
      updateBusinessProfile,
      reverseGeocode: vi.fn().mockResolvedValue({ address: "Yangi manzil" }),
      createUploadGrant: vi.fn(),
      uploadGrantedFile: vi.fn(),
      attachBusinessLogo: vi.fn().mockResolvedValue(profile),
      attachBusinessPaymentQr: vi.fn().mockResolvedValue(profile),
      switchCabinet: vi.fn(),
      logout: vi.fn(),
    };
    render(
      <BusinessProfile
        api={client}
        identity={identity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );

    await user.click(await screen.findByRole(
      "button",
      { name: /Profil \/ Mening sahifam/ },
    ));
    await user.click(screen.getByRole("button", { name: "📍 Xaritada joy belgilash" }));
    expect(document.querySelector('[data-screen="pickloc"]')).toBeInTheDocument();
    await waitFor(() => expect(leaflet.mapFactory).toHaveBeenCalled());
    leaflet.state.center = { lat: 37.838933493659454, lng: 67.58345251326438 };
    await user.click(screen.getByRole("button", { name: "✅ Shu joyni tanlash" }));

    await waitFor(() => expect(updateBusinessProfile).toHaveBeenCalledWith({
      latitude: 37.838933493659454,
      longitude: 67.58345251326438,
      address: "Yangi manzil",
      map_visible: true,
    }));
    expect(JSON.parse(localStorage.getItem("business_pick_point") ?? "{}"))
      .toEqual({ lat: 37.838933493659454, lng: 67.58345251326438 });
    expect(await screen.findByRole("heading", { name: "Profil / Mening sahifam" }))
      .toBeInTheDocument();
  });
});
