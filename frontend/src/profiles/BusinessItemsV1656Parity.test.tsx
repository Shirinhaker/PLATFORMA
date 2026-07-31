import { useState } from "react";
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
    unit: "kg",
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

function StatefulItemsView({
  initialForm = null,
  initialDraft = {},
  actions = {},
}: {
  initialForm?: string | null;
  initialDraft?: Record<string, unknown>;
  actions?: Partial<typeof shared>;
}) {
  const [form, setForm] = useState<string | null>(initialForm);
  const [draft, setDraft] = useState(initialDraft);
  return (
    <ItemsEditorView
      {...shared}
      {...actions}
      form={form}
      setForm={setForm}
      draft={draft}
      setDraft={setDraft}
      groups={groups}
      rows={rows}
      query=""
      setQuery={vi.fn()}
      kind="all"
      setKind={vi.fn()}
    />
  );
}


describe("v1656 mahsulot va xizmatlar pariteti", () => {
  it("guruhlar va Guruhsiz yozuvlarni aynan monolit sectionlarida ko'rsatadi", async () => {
    const user = userEvent.setup();
    renderView();

    expect(screen.getByRole("heading", { name: "gighi" })).toBeInTheDocument();
    expect(screen.getByText("Mahsulot guruhi · 1 ta")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Guruhsiz" })).toBeInTheDocument();
    expect(screen.getByText("Guruh tanlanmagan · 2 ta")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Tovar qo'shish" })).toHaveLength(2);
    expect(screen.getByText("25000 / kg")).toBeInTheDocument();
    expect(screen.getByText("Narx kelishiladi")).toBeInTheDocument();
    expect(screen.getAllByText("Xizmat")).toHaveLength(2);
    expect(screen.getAllByText("Izoh yo'q")).toHaveLength(3);

    await user.click(screen.getByRole("button", { name: "stomatolog amallari" }));
    expect(screen.getByRole("button", { name: "Tahrirlash" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Guruhini o'zgartirish" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "O'chirish" })).toBeInTheDocument();
  });

  it("guruh menyusida monolitdagi nomlarni ko'rsatadi", async () => {
    const user = userEvent.setup();
    renderView();

    await user.click(screen.getByRole("button", { name: "gighi amallari" }));
    expect(screen.getByRole("button", { name: "Nomini o'zgartirish" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "O'chirish" })).toBeInTheDocument();
  });

  it("qidiruv paytida monolit kabi qo'shish tugmalarini yashiradi", () => {
    renderView({ query: "stomatolog" });

    expect(screen.queryByRole("button", { name: "+ Guruh qo'shish" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Tovar qo'shish" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "gighi" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Guruhsiz" })).toBeInTheDocument();
    expect(screen.getByText("Guruh tanlanmagan · 1 ta")).toBeInTheDocument();
  });

  it("formatlangan narxni monolit kabi Narx kelishiladi bilan almashtirmaydi", () => {
    renderView({
      rows: [{
        id: 14,
        name: "Palov",
        kind: "product",
        group_id: null,
        price: "2 000 so'm",
        unit: "dona",
      }],
    });

    expect(screen.getByText("2 000 so'm")).toHaveClass("price");
    expect(screen.queryByText("Narx kelishiladi")).not.toBeInTheDocument();
  });

  it("bo'sh mahsulot nomida monolitdagi xatoni ko'rsatadi", async () => {
    const user = userEvent.setup();
    const create = vi.fn().mockResolvedValue(undefined);
    render(
      <StatefulItemsView
        initialForm="items:new"
        initialDraft={{ kind: "product", name: "" }}
        actions={{ create }}
      />,
    );

    expect(screen.getByText("Yangi mahsulot yoki xizmat").closest("section"))
      .toHaveClass("form-wrap");
    expect(screen.getByLabelText("Nomi")).toHaveClass("input");
    expect(screen.getByLabelText("Narxi"))
      .toHaveAttribute("placeholder", "Masalan: 2 000 so'm");
    expect(screen.getByRole("button", { name: "Saqlash" }))
      .toHaveClass("btn", "btn-primary", "btn-block");

    await user.click(screen.getByRole("button", { name: "Saqlash" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Nomi kiritilishi shart.");
    expect(create).not.toHaveBeenCalled();
  });

  it("bo'sh guruh nomida monolitdagi xatoni ko'rsatadi", async () => {
    const user = userEvent.setup();
    const create = vi.fn().mockResolvedValue(undefined);
    render(
      <StatefulItemsView
        initialForm="item_groups:new"
        initialDraft={{ kind: "product", name: "" }}
        actions={{ create }}
      />,
    );

    expect(screen.getByRole("dialog")).toHaveClass("order-sheet", "on");
    expect(screen.getByLabelText("Yopish")).toHaveClass("order-close");
    expect(screen.getByLabelText("Guruh nomi")).toHaveClass("input");

    await user.click(screen.getByRole("button", { name: "Saqlash" }));

    expect(screen.getByRole("alert"))
      .toHaveTextContent("Guruh nomi kiritilishi shart.");
    expect(create).not.toHaveBeenCalled();
  });

  it("tovarni faqat tasdiqlash oynasidan keyin o'chiradi", async () => {
    const user = userEvent.setup();
    const remove = vi.fn().mockResolvedValue(undefined);
    render(<StatefulItemsView actions={{ remove }} />);

    await user.click(screen.getByRole("button", { name: "banan amallari" }));
    await user.click(screen.getByRole("button", { name: "O'chirish" }));

    expect(remove).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toHaveTextContent("Tovarni o'chirish");
    expect(screen.getByRole("dialog")).toHaveTextContent("Bu tovar o'chirilsinmi?");

    await user.click(screen.getByRole("button", { name: "O'chirish" }));
    expect(remove).toHaveBeenCalledWith("items", 12);
  });

  it("guruhni ichidagi tovarlar haqidagi aniq ogohlantirishdan keyin o'chiradi", async () => {
    const user = userEvent.setup();
    const remove = vi.fn().mockResolvedValue(undefined);
    render(<StatefulItemsView actions={{ remove }} />);

    await user.click(screen.getByRole("button", { name: "gighi amallari" }));
    await user.click(screen.getByRole("button", { name: "O'chirish" }));

    expect(remove).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toHaveTextContent("Guruhni o'chirish");
    expect(screen.getByRole("dialog")).toHaveTextContent(
      "'gighi' guruhi o'chirilsinmi? Ichidagi tovarlar o'chmaydi, Guruhsiz bo'limiga o'tadi.",
    );

    await user.click(screen.getByRole("button", { name: "O'chirish" }));
    expect(remove).toHaveBeenCalledWith("item_groups", 1);
  });

  it("Guruhini o'zgartirish alohida guruh tanlash oynasini ochadi", async () => {
    const user = userEvent.setup();
    render(<StatefulItemsView />);

    await user.click(screen.getByRole("button", { name: "banan amallari" }));
    await user.click(screen.getByRole("button", { name: "Guruhini o'zgartirish" }));

    expect(screen.getByRole("dialog")).toHaveTextContent("Guruhini o'zgartirish");
    expect(screen.getByLabelText("Guruh")).toHaveValue("");
    expect(screen.queryByLabelText("Nomi")).not.toBeInTheDocument();
  });
});
