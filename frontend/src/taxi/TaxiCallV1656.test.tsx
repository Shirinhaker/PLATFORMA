import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TaxiCallV1656 } from "./TaxiCallV1656";

const leaflet = vi.hoisted(() => {
  const state = { center: { lat: 41.3111, lng: 69.2797 }, zoom: 14 };
  const handlers: Record<string, () => void> = {};
  const markerLayer = { addTo: vi.fn(() => markerLayer) };
  const routeLayer = { addTo: vi.fn(() => routeLayer) };
  const map = {
    fitBounds: vi.fn((bounds: [[number, number], [number, number]]) => {
      state.center = {
        lat: (bounds[0][0] + bounds[1][0]) / 2,
        lng: (bounds[0][1] + bounds[1][1]) / 2,
      };
      return map;
    }),
    getCenter: vi.fn(() => ({ ...state.center })),
    invalidateSize: vi.fn(),
    on: vi.fn((event: string, handler: () => void) => {
      handlers[event] = handler;
      return map;
    }),
    remove: vi.fn(),
    removeLayer: vi.fn(),
    setView: vi.fn((point: [number, number]) => {
      state.center = { lat: point[0], lng: point[1] };
      return map;
    }),
  };
  const tileLayer = { addTo: vi.fn(() => tileLayer) };
  return {
    divIcon: vi.fn((options: unknown) => options),
    geoJSON: vi.fn(() => routeLayer),
    handlers,
    map,
    mapFactory: vi.fn(() => map),
    marker: vi.fn(() => markerLayer),
    markerLayer,
    routeLayer,
    state,
    tileLayer,
    tileLayerFactory: vi.fn(() => tileLayer),
  };
});

vi.mock("leaflet", () => ({
  default: {
    divIcon: leaflet.divIcon,
    geoJSON: leaflet.geoJSON,
    map: leaflet.mapFactory,
    marker: leaflet.marker,
    tileLayer: leaflet.tileLayerFactory,
  },
}));

const pricing = {
  pricing: {
    taxi: { base: 5000, per_km: 2000, min: 9000 },
    dostavka: { base: 10000, per_km: 2500, min: 15000 },
  },
  commission: 1000,
};

let geolocationSuccess: PositionCallback;

beforeEach(() => {
  leaflet.state.center = { lat: 41.3111, lng: 69.2797 };
  for (const event of Object.keys(leaflet.handlers)) delete leaflet.handlers[event];
  vi.clearAllMocks();
  Object.defineProperty(navigator, "geolocation", {
    configurable: true,
    value: {
      getCurrentPosition: vi.fn((success: PositionCallback) => {
        geolocationSuccess = success;
      }),
    },
  });
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      json: vi.fn().mockResolvedValue({ routes: [] }),
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("TaxiCallV1656", () => {
  it("opens for a guest but asks for login only when ordering", async () => {
    const onNeedLogin = vi.fn();
    const createTaxiRide = vi.fn();
    render(
      <TaxiCallV1656
        api={{ createTaxiRide, getTaxiPricing: vi.fn().mockResolvedValue(pricing) }}
        authenticated={false}
        center={{ latitude: 41.3111, longitude: 69.2797 }}
        district="Qumqo'rg'on"
        onBack={vi.fn()}
        onNeedLogin={onNeedLogin}
      />,
    );

    expect(screen.getByRole("button", { name: "Zakaz qilish" })).toBeInTheDocument();
    expect(screen.getByText(/Qumqo'rg'on/)).toBeInTheDocument();
    const panel = document.getElementById("callPanel");
    const map = document.querySelector(".taxi-call-v1656__map-wrap");
    expect(panel).not.toBeNull();
    expect(map).not.toBeNull();
    expect(
      panel!.compareDocumentPosition(map!) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Zakaz qilish" }));

    expect(onNeedLogin).toHaveBeenCalledWith("Zakaz qilish");
    expect(createTaxiRide).not.toHaveBeenCalled();
  });

  it("keeps the exact Taxi and Dostavka fields", async () => {
    render(
      <TaxiCallV1656
        api={{
          createTaxiRide: vi.fn(),
          getTaxiPricing: vi.fn().mockResolvedValue(pricing),
        }}
        authenticated={false}
        center={{ latitude: 41.3111, longitude: 69.2797 }}
        onBack={vi.fn()}
        onNeedLogin={vi.fn()}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "📦 Dostavka" }));
    expect(screen.getByRole("group", { name: "Mashina turi" })).toBeInTheDocument();
    expect(
      screen.queryByRole("combobox", { name: "Mashina turi" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yengil yuk" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await userEvent.click(screen.getByRole("button", { name: "Katta yuk" }));
    expect(screen.getByRole("button", { name: "Katta yuk" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByLabelText("Yuk turi")).toHaveAttribute(
      "placeholder",
      "Masalan: mebel, quti, texnika",
    );
    expect(
      screen.getByRole("button", { name: "Joriy joylashuvni olish" }),
    ).toHaveTextContent("📍 GPS");
    expect(screen.getByRole("button", { name: "🗣 O'zim aytaman" })).toBeInTheDocument();
  });

  it("lets the explicit GPS button replace a manual place", async () => {
    render(
      <TaxiCallV1656
        api={{ getTaxiPricing: vi.fn().mockResolvedValue(pricing) }}
        authenticated={false}
        center={{ latitude: 41.3111, longitude: 69.2797 }}
        onBack={vi.fn()}
        onNeedLogin={vi.fn()}
      />,
    );
    await waitFor(() => expect(leaflet.mapFactory).toHaveBeenCalled());

    act(() => {
      leaflet.handlers.dragstart?.();
      leaflet.state.center = { lat: 37.838933, lng: 67.583453 };
      leaflet.handlers.moveend?.();
    });
    await userEvent.click(
      screen.getByRole("button", { name: "Joriy joylashuvni olish" }),
    );
    act(() => {
      geolocationSuccess({
        coords: { latitude: 40.5, longitude: 66.75 },
      } as GeolocationPosition);
    });

    expect(leaflet.map.setView).toHaveBeenCalledWith([40.5, 66.75]);
    expect(screen.getByText("📍 Joriy manzilim")).toBeInTheDocument();
  });

  it("does not let a delayed GPS response replace a manually selected place", async () => {
    render(
      <TaxiCallV1656
        api={{ getTaxiPricing: vi.fn().mockResolvedValue(pricing) }}
        authenticated={false}
        center={{ latitude: 41.3111, longitude: 69.2797 }}
        onBack={vi.fn()}
        onNeedLogin={vi.fn()}
      />,
    );
    await waitFor(() => expect(leaflet.mapFactory).toHaveBeenCalled());

    act(() => {
      leaflet.handlers.dragstart?.();
      leaflet.state.center = { lat: 37.838933, lng: 67.583453 };
      leaflet.handlers.moveend?.();
    });
    expect(screen.getByText("37.83893, 67.58345")).toBeInTheDocument();

    act(() => {
      geolocationSuccess({
        coords: { latitude: 40.5, longitude: 66.75 },
      } as GeolocationPosition);
    });

    expect(leaflet.map.setView).not.toHaveBeenCalledWith([40.5, 66.75]);
    expect(leaflet.state.center).toEqual({ lat: 37.838933, lng: 67.583453 });
    expect(screen.getByText("37.83893, 67.58345")).toBeInTheDocument();
  });

  it("draws the route without moving the map away from the selected place", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        json: vi.fn().mockResolvedValue({
          routes: [
            {
              distance: 4200,
              duration: 600,
              geometry: { type: "LineString", coordinates: [] },
            },
          ],
        }),
      }),
    );
    render(
      <TaxiCallV1656
        api={{ getTaxiPricing: vi.fn().mockResolvedValue(pricing) }}
        authenticated={false}
        center={{ latitude: 41.3111, longitude: 69.2797 }}
        onBack={vi.fn()}
        onNeedLogin={vi.fn()}
      />,
    );
    await waitFor(() => expect(leaflet.mapFactory).toHaveBeenCalled());

    act(() => {
      leaflet.handlers.dragstart?.();
      leaflet.state.center = { lat: 37.838933, lng: 67.583453 };
      leaflet.handlers.moveend?.();
    });
    await waitFor(() => expect(leaflet.geoJSON).toHaveBeenCalled());

    expect(leaflet.map.fitBounds).not.toHaveBeenCalled();
    expect(leaflet.state.center).toEqual({ lat: 37.838933, lng: 67.583453 });
  });
});
