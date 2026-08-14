import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ReviewListRead } from "../api/types";
import {
  PublicReviewsV1656,
  ReceivedReviewsV1656,
  type ReviewsApi,
} from "./ReviewsV1656";


const review = {
  id: 11,
  stars: 5,
  comment: "Juda yaxshi xizmat",
  user_name: "Ali",
  created_at: "2026-08-10T08:00:00Z",
  owner_reply: "Rahmat",
  owner_replied_at: "2026-08-10T09:00:00Z",
};

const publicList: ReviewListRead = {
  reviews: [review],
  avg: 5,
  count: 1,
  can_review: true,
  my_review: null,
};


function api(overrides: Partial<ReviewsApi> = {}): ReviewsApi {
  return {
    getReviews: vi.fn().mockResolvedValue(publicList),
    saveReview: vi.fn().mockResolvedValue({ ok: true, avg: 5, count: 1 }),
    deleteReview: vi.fn().mockResolvedValue({ ok: true, avg: 0, count: 0 }),
    getReceivedReviews: vi.fn().mockResolvedValue(publicList),
    replyToReview: vi.fn().mockResolvedValue(review),
    ...overrides,
  };
}


describe("v1656 baholar va fikrlar", () => {
  it("shows public average, customer review and owner reply", async () => {
    render(
      <PublicReviewsV1656
        api={api()}
        targetKind="business"
        targetPublicId="b_0123456789abcdef"
      />,
    );

    expect(await screen.findByRole("heading", { name: "Baholar va fikrlar" }))
      .toBeInTheDocument();
    expect(screen.getByText("5.0")).toBeInTheDocument();
    expect(screen.getByText("(1 ta fikr)")).toBeInTheDocument();
    expect(screen.getByText("Juda yaxshi xizmat")).toBeInTheDocument();
    expect(screen.getByText("Mutaxassis javobi")).toBeInTheDocument();
  });

  it("requires a selected star and saves a v1656 customer review", async () => {
    const client = api();
    const user = userEvent.setup();
    render(
      <PublicReviewsV1656
        api={client}
        targetKind="specialist"
        targetPublicId="u_0123456789abcdef"
      />,
    );

    await screen.findByText("Baho bering");
    await user.click(screen.getByRole("button", { name: "5 yulduz" }));
    await user.type(screen.getByPlaceholderText("Fikringiz (ixtiyoriy)"), "A’lo");
    await user.click(screen.getByRole("button", { name: "Yuborish" }));

    await waitFor(() => expect(client.saveReview).toHaveBeenCalledWith({
      target_kind: "specialist",
      target_public_id: "u_0123456789abcdef",
      stars: 5,
      comment: "A’lo",
    }));
  });

  it("lets the owner reply without exposing customer review deletion", async () => {
    const client = api();
    const user = userEvent.setup();
    render(<ReceivedReviewsV1656 api={client} onBack={vi.fn()} />);

    expect(await screen.findByText("Juda yaxshi xizmat")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /fikrni o‘chirish/i }))
      .not.toBeInTheDocument();
    const reply = screen.getByPlaceholderText("Mijozga javob yozing...");
    await user.clear(reply);
    await user.type(reply, "Yana kutib qolamiz");
    await user.click(screen.getByRole("button", { name: "Javobni yangilash" }));

    await waitFor(() => expect(client.replyToReview)
      .toHaveBeenCalledWith(11, "Yana kutib qolamiz"));
  });
});
