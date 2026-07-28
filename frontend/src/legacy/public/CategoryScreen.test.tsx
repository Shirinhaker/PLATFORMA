import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { CategoryScreen } from "./CategoryScreen";

describe("CategoryScreen", () => {
  it("shows the selected direction and all matching activity types", () => {
    render(<CategoryScreen categoryId="education" />);

    expect(
      screen.getByRole("heading", { name: "Ta’lim faoliyati" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "O‘quv markazi" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Imtihonga tayyorlash" }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("button")).toHaveLength(12);
  });

  it("leaves Back navigation to the parent shell", () => {
    render(<CategoryScreen categoryId="education" />);

    expect(screen.queryByRole("button", { name: "Orqaga" }))
      .not.toBeInTheDocument();
  });

  it("honestly marks an activity type as not migrated yet", async () => {
    render(<CategoryScreen categoryId="education" />);

    await userEvent.click(
      screen.getByRole("button", { name: "O‘quv markazi" }),
    );

    expect(
      screen.getByText(
        "O‘quv markazi natijalari keyingi migratsiya bosqichida ulanadi.",
      ),
    ).toBeInTheDocument();
  });

  it("shows an honest empty state for an unknown direction", () => {
    render(<CategoryScreen categoryId="unknown" />);

    expect(screen.getByText("Yo‘nalish topilmadi")).toBeInTheDocument();
  });
});
