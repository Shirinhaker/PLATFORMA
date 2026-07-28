import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SessionStatus } from "./SessionStatus";


describe("SessionStatus", () => {
  it("announces a loading state", () => {
    render(<SessionStatus state="loading" />);
    expect(screen.getByRole("status")).toHaveTextContent("Yuklanmoqda…");
  });

  it("offers one working retry action for a network error", async () => {
    const onRetry = vi.fn();
    render(<SessionStatus state="error" onRetry={onRetry} />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Server bilan bog‘lanib bo‘lmadi.",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Qayta urinish" }),
    );
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
