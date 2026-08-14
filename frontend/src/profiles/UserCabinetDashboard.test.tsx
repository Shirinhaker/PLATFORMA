import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { UserProfile } from "../api/types";
import {
  isActiveUserOrder,
  UserCabinetDashboard,
} from "./UserCabinetDashboard";


const sections = [
  {
    caption: "Qiziqishlaringizni belgilang",
    icon: "🔔",
    label: "Bildirishnomalarim",
    view: "notifications",
  },
] as const;


function profile(): UserProfile {
  return {
    name: "bunyod",
    district: "Qumqo‘rg‘on tumani",
    region: "Surxondaryo viloyati",
    followers_count: 1,
    following_count: 2,
    has_business: true,
    avatar_url: "",
    avatar_x: 50,
    avatar_y: 50,
    avatar_zoom: 1,
    dashboard_snapshot: {
      active_orders: 2,
      following: 2,
      saved: 0,
      unread: 5,
    },
    cabinet_payload: {
      orders: [
        { status: "done" },
        { status: "pending" },
        { status: "new", problem_open: 1 },
      ],
      saved: [],
      notifications: [
        {
          actor_kind: "business",
          actor_id: 3,
          is_read: 0,
          resolved_at: 0,
        },
        {
          actor_kind: "user",
          actor_id: 7,
          is_read: 1,
          resolved_at: 0,
        },
      ],
    },
    recent_activity: [],
  } as unknown as UserProfile;
}


describe("modular user dashboard parity", () => {
  it("uses the exact modular active-order predicate", () => {
    expect(isActiveUserOrder({ status: "new" })).toBe(true);
    expect(isActiveUserOrder({ status: "pickup_waiting_customer" })).toBe(true);
    expect(isActiveUserOrder({ status: "new", problem_open: 1 })).toBe(false);
    expect(isActiveUserOrder({ status: "done" })).toBe(false);
    expect(isActiveUserOrder({ status: "pending" })).toBe(false);
  });

  it("does not show stale snapshot or business-actor counts in user cabinet", () => {
    render(
      <UserCabinetDashboard
        busy={false}
        error=""
        messageUnread={0}
        notificationUnread={5}
        orderUnread={{ product: 0, service: 0 }}
        profile={profile()}
        sections={sections}
        onNavigate={vi.fn()}
        onOpenBusiness={vi.fn()}
        onSwitchBusiness={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", {
      name: /Faol buyurtmalar 0 Joriy buyurtmalar/,
    })).toBeInTheDocument();
    expect(screen.getByRole("button", {
      name: /Bildirishnomalar 0 O‘qilmagan xabarlar/,
    })).toBeInTheDocument();
    expect(screen.getByRole("button", {
      name: "🏪 Biznes kabinetga o‘tish",
    })).toBeInTheDocument();
    expect(screen.queryByText("5")).not.toBeInTheDocument();
  });
});
