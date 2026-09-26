import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { HomeScreen } from "./HomeScreen";

describe("Bosh sahifadagi tarmoq xatolaridan tiklanish", () => {
  it("reports each failed section and retries only the selected request", async () => {
    const getHomeMap = vi.fn().mockRejectedValue(new Error("network"));
    const getDistrictOffers = vi
      .fn()
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValue({ items: [], needs_district: false });
    const getFollowedProfiles = vi.fn().mockRejectedValue(new Error("network"));
    render(
      <HomeScreen
        authenticated
        currentDistrict="Qumqo‘rg‘on"
        getHomeMap={getHomeMap}
        getDistrictOffers={getDistrictOffers}
        getFollowedProfiles={getFollowedProfiles}
        onOpenCatalog={vi.fn()}
        onOpenLocation={vi.fn()}
      />,
    );
    expect(
      await screen.findByRole("button", {
        name: "Qayta urinish: Xaritadagi profillar",
      }),
    ).toBeInTheDocument();
    await userEvent.click(
      await screen.findByRole("button", { name: "Qayta urinish: Hududiy takliflar" }),
    );
    await waitFor(() => expect(getDistrictOffers).toHaveBeenCalledTimes(2));
    expect(
      screen.queryByRole("button", { name: "Qayta urinish: Hududiy takliflar" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Qayta urinish: Kuzatilayotgan profillar" }),
    ).toBeInTheDocument();
    expect(getHomeMap).toHaveBeenCalledTimes(1);
    expect(getFollowedProfiles).toHaveBeenCalledTimes(1);
  });
  it("does not label successful empty data as a network failure", async () => {
    const getDistrictOffers = vi
      .fn()
      .mockResolvedValue({ items: [], needs_district: false });
    render(
      <HomeScreen
        currentDistrict="Qumqo‘rg‘on"
        getDistrictOffers={getDistrictOffers}
        onOpenCatalog={vi.fn()}
        onOpenLocation={vi.fn()}
      />,
    );
    await waitFor(() => expect(getDistrictOffers).toHaveBeenCalledOnce());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
