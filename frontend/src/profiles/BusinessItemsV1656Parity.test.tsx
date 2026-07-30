import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ItemsEditorView } from "./BusinessOnlineEditingViews";


const shared = {
  busy: false,
  form: null,
  draft: {},
  setForm: vi.fn(),
  setDraft: vi.fn(),
  create: vi.fn().mockResolvedValue(undefined),
  patch: vi.fn().mockResolvedValue(undefined),
  remove: vi.fn().mockResolvedValue(undefined),
  action: vi.fn().mockResolvedValue(undefined),
};


describe("v1656 mahsulot va xizmatlar pariteti", () => {
  it("guruhlar va Guruhsiz yozuvlarni alohida gorizontal sectionlarda ko‘rsatadi", async () => {
    const user = userEvent.setup();
    render(
      <ItemsEditorView
        {...shared}
        groups={[{ id: 1, name: "gighi", kind: "product" }]}
        rows={[
          {
            id: 11,
            name: "ingiliz tili",
            kind: "service",
            group_id: 1,
            price: 350000,
            description: "",
          },
          {
            id: 12,
            name: "banan",
            kind: "product",
            group_id: null,
            price: 25000,
            description: "",
          },
          {
            id: 13,
            name: "stomatolog",
            kind: "service",
            group_id: null,
            price: 0,
            description: "",
          },
        ]}
        query=""
        setQuery={vi.fn()}
        kind="all"
        setKind={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "gighi" })).toBeInTheDocument();
    expect(screen.getByText("Mahsulot guruhi · 1 ta")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Guruhsiz" })).toBeInTheDocument();
    expect(screen.getByText("Guruhlanmagan · 2 ta")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Tovar qo‘shish" })).toHaveLength(2);
    expect(screen.getByText("Narx kelishiladi")).toBeInTheDocument();
    expect(screen.getAllByText("Xizmat")).toHaveLength(2);
    expect(screen.getAllByText("Izoh yo‘q")).toHaveLength(3);

    await user.click(screen.getByRole("button", { name: "stomatolog amallari" }));
    expect(screen.getByRole("button", { name: "Tahrirlash" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yashirish" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "O‘chirish" })).toBeInTheDocument();
  });
});
