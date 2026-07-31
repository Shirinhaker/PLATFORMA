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

const groups = [{ id: 1, name: "gighi", kind: "product" }];
const rows = [
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
];

function renderView(overrides: Partial<Parameters<typeof ItemsEditorView>[0]> = {}) {
  return render(
    <ItemsEditorView
      {...shared}
      groups={groups}
      rows={rows}
      query=""
      setQuery={vi.fn()}
      kind="all"
      setKind={vi.fn()}
      {...overrides}
    />,
  );
}


describe("v1656 mahsulot va xizmatlar pariteti", () => {
  it("guruhlar va Guruhsiz yozuvlarni aynan monolit sectionlarida ko‘rsatadi", async () => {
    const user = userEvent.setup();
    renderView();

    expect(screen.getByRole("heading", { name: "gighi" })).toBeInTheDocument();
    expect(screen.getByText("Mahsulot guruhi · 1 ta")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Guruhsiz" })).toBeInTheDocument();
    expect(screen.getByText("Guruh tanlanmagan · 2 ta")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Tovar qo‘shish" })).toHaveLength(2);
    expect(screen.getByText("Narx kelishiladi")).toBeInTheDocument();
    expect(screen.getAllByText("Xizmat")).toHaveLength(2);
    expect(screen.getAllByText("Izoh yo‘q")).toHaveLength(3);

    await user.click(screen.getByRole("button", { name: "stomatolog amallari" }));
    expect(screen.getByRole("button", { name: "Tahrirlash" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Guruhini o‘zgartirish" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "O‘chirish" })).toBeInTheDocument();
  });

  it("guruh menyusida monolitdagi nomlarni ko‘rsatadi", async () => {
    const user = userEvent.setup();
    renderView();

    await user.click(screen.getByRole("button", { name: "gighi amallari" }));
    expect(screen.getByRole("button", { name: "Nomini o‘zgartirish" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "O‘chirish" })).toBeInTheDocument();
  });

  it("qidiruv paytida monolit kabi qo‘shish tugmalarini yashiradi", () => {
    renderView({ query: "stomatolog" });

    expect(screen.queryByRole("button", { name: "+ Guruh qo‘shish" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Tovar qo‘shish" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "gighi" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Guruhsiz" })).toBeInTheDocument();
    expect(screen.getByText("Guruh tanlanmagan · 1 ta")).toBeInTheDocument();
  });
});
