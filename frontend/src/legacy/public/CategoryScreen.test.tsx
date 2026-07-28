import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CategoryScreen } from "./CategoryScreen";


describe("CategoryScreen", () => {
  it("loads matching businesses after an activity type is selected", async () => {
    const user = userEvent.setup();
    const searchPublic = vi.fn().mockResolvedValue({
      items: [{
        kind: "business",
        public_id: "b_shop",
        name: "Koprik Market",
        public_username: "",
        description: "",
        direction: "Savdo",
        activity_type: "Oziq-ovqat do‘koni",
        region: "",
        district: "",
        mahalla: "",
        image_url: "",
      }],
      page: 1,
      page_size: 20,
      total: 1,
      pages: 1,
    });

    render(
      <CategoryScreen
        categoryId="trade"
        searchPublic={searchPublic}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: /Oziq-ovqat do‘koni/ }),
    );

    await waitFor(() => {
      expect(searchPublic).toHaveBeenCalledWith({
        result_type: "business",
        direction: "Savdo",
        activity_type: "Oziq-ovqat do‘koni",
        page: 1,
        page_size: 20,
      });
    });
    expect(await screen.findByText("Koprik Market")).toBeInTheDocument();
  });
});
