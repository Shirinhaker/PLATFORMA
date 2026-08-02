import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { OrderCreate, OrderCreateResponse, PublicProfileItem } from "../api/types";
import { CartV1656 } from "./CartV1656";
import {
  addCartItem,
  cartLineCount,
  cartReceiptTotal,
  type CartState,
  setCartItemQuantity,
  setCartItemSum,
} from "./order-store";


const leaflet = vi.hoisted(() => {
  const state = { center: { lat: 37.82, lng: 67.58 }, zoom: 15 };
  const listeners: Record<string, () => void> = {};
  const map = {
    getCenter: vi.fn(() => ({ ...state.center })),
    getZoom: vi.fn(() => state.zoom),
    invalidateSize: vi.fn(),
    on: vi.fn((name: string, listener: () => void) => {
      listeners[name] = listener;
      return map;
    }),
    remove: vi.fn(),
    setView: vi.fn((point: [number, number] | { lat: number; lng: number }, zoom: number) => {
      state.center = Array.isArray(point)
        ? { lat: point[0], lng: point[1] }
        : { ...point };
      state.zoom = zoom;
      return map;
    }),
  };
  const tileLayer = { addTo: vi.fn() };
  return {
    listeners,
    map,
    mapFactory: vi.fn(() => map),
    state,
    tileLayerFactory: vi.fn(() => tileLayer),
  };
});

vi.mock("leaflet", () => ({
  default: {
    map: leaflet.mapFactory,
    tileLayer: leaflet.tileLayerFactory,
  },
}));


const non: PublicProfileItem = {
  kind: "product",
  public_id: "p_non",
  name: "Non",
  price_text: "20 000 so'm",
  unit: "dona",
  note: "Issiq non",
  image_url: "",
  group_name: "Oziq-ovqat",
  queue_enabled: false,
};

const sut: PublicProfileItem = {
  ...non,
  public_id: "p_sut",
  name: "Sut",
  price_text: "12 000 so'm",
  unit: "litr",
};

function oneStoreCart(): CartState {
  return addCartItem({}, {
    public_id: "b_turon",
    name: "Turon savdo",
  }, non);
}

function StatefulCart({
  initial = oneStoreCart(),
  createOrder = vi.fn().mockResolvedValue({ id: 91 }),
}: {
  initial?: CartState;
  createOrder?: (body: OrderCreate) => Promise<OrderCreateResponse>;
}) {
  const [carts, setCarts] = useState(initial);
  return (
    <CartV1656
      authenticated
      carts={carts}
      createOrder={createOrder}
      customer={{
        phone: "+998901234567",
        address: "Surxondaryo, Qumqo‘rg‘on",
      }}
      homePoint={{ latitude: 37.82, longitude: 67.58 }}
      onCartsChange={setCarts}
      onNeedLogin={vi.fn()}
      onOrderSent={vi.fn()}
    />
  );
}


beforeEach(() => {
  leaflet.state.center = { lat: 37.82, lng: 67.58 };
  leaflet.state.zoom = 15;
  Object.keys(leaflet.listeners).forEach((key) => delete leaflet.listeners[key]);
  vi.clearAllMocks();
});


describe("v1656 savat state parity", () => {
  it("keeps a separate receipt for every business and counts distinct lines", () => {
    let carts = oneStoreCart();
    carts = addCartItem(carts, { public_id: "b_turon", name: "Turon savdo" }, sut);
    carts = addCartItem(carts, { public_id: "b_muhr", name: "Muhr" }, non);

    expect(Object.keys(carts)).toEqual(["b_turon", "b_muhr"]);
    expect(cartLineCount(carts)).toBe(3);
    expect(carts.b_turon?.items.p_non?.qty).toBe(1);
    expect(carts.b_muhr?.items.p_non?.qty).toBe(1);
  });

  it("updates amount from quantity and quantity from amount", () => {
    let carts = oneStoreCart();
    carts = setCartItemQuantity(carts, "b_turon", "p_non", 3);
    expect(cartReceiptTotal(carts.b_turon!)).toBe(60_000);

    carts = setCartItemSum(carts, "b_turon", "p_non", 100_000);
    expect(carts.b_turon?.items.p_non?.qty).toBe(5);
    expect(cartReceiptTotal(carts.b_turon!)).toBe(100_000);
  });

  it("uses fractional steps only for v1656 fractional units and removes zero", () => {
    let carts = addCartItem({}, { public_id: "b_turon", name: "Turon" }, sut);
    carts = setCartItemQuantity(carts, "b_turon", "p_sut", 1.5, true);
    expect(carts.b_turon?.items.p_sut?.qty).toBe(1.5);

    carts = setCartItemQuantity(carts, "b_turon", "p_sut", 0, true);
    expect(carts.b_turon?.items.p_sut).toBeUndefined();

    carts = setCartItemQuantity(oneStoreCart(), "b_turon", "p_non", 5_000, true);
    expect(carts.b_turon?.items.p_non?.qty).toBe(999);
  });
});


describe("v1656 Savat screen parity", () => {
  it("shows the exact empty and multiple-store copy", () => {
    const { rerender } = render(
      <CartV1656
        authenticated
        carts={{}}
        createOrder={vi.fn()}
        onCartsChange={vi.fn()}
        onNeedLogin={vi.fn()}
      />,
    );
    expect(screen.getByRole("heading", { name: "Savatcha bo'sh" }))
      .toBeInTheDocument();
    expect(screen.getByText("Do'kon sahifasidan mahsulot qo'shing."))
      .toBeInTheDocument();

    const twoStores = addCartItem(
      oneStoreCart(),
      { public_id: "b_muhr", name: "Muhr" },
      sut,
    );
    rerender(
      <CartV1656
        authenticated
        carts={twoStores}
        createOrder={vi.fn()}
        onCartsChange={vi.fn()}
        onNeedLogin={vi.fn()}
      />,
    );
    expect(screen.getByText(
      "Har do'kon uchun alohida chek. Har birini alohida buyurtma qilasiz.",
    )).toBeInTheDocument();
  });

  it("keeps quantity and sum inputs live-linked without losing focus", async () => {
    const user = userEvent.setup();
    render(<StatefulCart />);

    const quantity = screen.getByLabelText("Non miqdori");
    const sum = screen.getByLabelText("Non summasi");
    await user.clear(quantity);
    expect(quantity).toHaveValue("");
    await user.type(quantity, "3");
    expect(sum).toHaveValue("60000");
    expect(quantity).toHaveFocus();

    await user.clear(sum);
    await user.type(sum, "100000");
    expect(quantity).toHaveValue("5");
    expect(sum).toHaveFocus();
  });

  it("asks with the exact v1656 confirmation before clearing a receipt", async () => {
    const user = userEvent.setup();
    render(<StatefulCart />);

    await user.click(screen.getByRole("button", { name: "Chekni tozalash" }));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("Bu do'kon cheki tozalansinmi?");
    expect(within(dialog).getByRole("button", { name: "Tozalash" }))
      .toHaveClass("acf-ok", "danger");
    await user.click(within(dialog).getByRole("button", { name: "Bekor qilish" }));
    expect(screen.getByText("Non")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Chekni tozalash" }));
    await user.click(within(screen.getByRole("dialog")).getByRole(
      "button",
      { name: "Tozalash" },
    ));
    expect(screen.getByRole("heading", { name: "Savatcha bo'sh" }))
      .toBeInTheDocument();
  });

  it("submits getCenter coordinates and clears only the successful business", async () => {
    const user = userEvent.setup();
    const createOrder = vi.fn().mockResolvedValue({ id: 91 });
    const initial = addCartItem(
      oneStoreCart(),
      { public_id: "b_muhr", name: "Muhr" },
      sut,
    );
    render(<StatefulCart initial={initial} createOrder={createOrder} />);

    const turonReceipt = screen.getByText("🏪 Turon savdo").closest(".panel-card");
    expect(turonReceipt).not.toBeNull();
    await user.click(within(turonReceipt as HTMLElement).getByRole(
      "button",
      { name: "Buyurtma qilish" },
    ));

    expect(screen.getByText("Buyurtma berish")).toBeInTheDocument();
    expect(screen.getByText(
      "Turon savdo — tanlangan mahsulot/xizmatlar bo‘yicha",
    )).toBeInTheDocument();
    await waitFor(() => expect(leaflet.mapFactory).toHaveBeenCalled());
    const mapNode = document.getElementById("orderMap");
    const pin = document.querySelector(".order-center-pin");
    expect(mapNode?.contains(pin)).toBe(false);
    expect(mapNode?.nextElementSibling).toBe(pin);

    leaflet.state.center = { lat: 37.838933, lng: 67.583453 };
    leaflet.listeners.moveend?.();
    expect(await screen.findByText(
      "✅ Metka belgilandi: 37.838933, 67.583453",
    )).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "✅ Buyurtma yuborish" }));

    await waitFor(() => expect(createOrder).toHaveBeenCalledWith({
      provider_kind: "business",
      provider_public_id: "b_turon",
      items: [{ public_id: "p_non", qty: 1 }],
      listing_public_id: "",
      title: "Buyurtma: Turon savdo",
      phone: "+998901234567",
      order_type: "delivery",
      address: "Surxondaryo, Qumqo‘rg‘on",
      desired_time: "",
      delivery_lat: 37.838933,
      delivery_lng: 67.583453,
      note: "",
    }));
    expect(screen.queryByText("🏪 Turon savdo")).not.toBeInTheDocument();
    expect(screen.getByText("🏪 Muhr")).toBeInTheDocument();
  });

  it("starts the delivery map from the selected district when coordinates are absent", async () => {
    const user = userEvent.setup();
    render(
      <CartV1656
        authenticated
        carts={oneStoreCart()}
        createOrder={vi.fn()}
        customer={{ phone: "+998901234567", address: "Qumqo‘rg‘on" }}
        homeLocation={{
          region: "Surxondaryo viloyati",
          district: "Qumqo‘rg‘on tumani",
          neighborhood: "",
          latitude: null,
          longitude: null,
        }}
        onCartsChange={vi.fn()}
        onNeedLogin={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Buyurtma qilish" }));

    await waitFor(() => expect(leaflet.map.setView).toHaveBeenCalledWith(
      [37.834, 67.585],
      15,
    ));
  });

  it("switches pickup and booking fields exactly like v1656", async () => {
    const user = userEvent.setup();
    render(<StatefulCart />);
    await user.click(screen.getByRole("button", { name: "Buyurtma qilish" }));

    await user.click(screen.getByRole("button", { name: /🏪 Olib ketish/ }));
    expect(screen.queryByLabelText("Yetkazib berish manzili")).not.toBeInTheDocument();
    expect(screen.getByText("Qachonga kerak? — ixtiyoriy")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /🗓 Navbat \/ qabulga yozilish/ }));
    expect(screen.getByText(
      "Qaysi vaqtga yozilmoqchisiz? — ixtiyoriy",
    )).toBeInTheDocument();
  });

  it("shows the exact phone and delivery-point validation messages", async () => {
    const user = userEvent.setup();
    const [carts, setCarts] = [oneStoreCart(), vi.fn()];
    const { unmount } = render(
      <CartV1656
        authenticated
        carts={carts}
        createOrder={vi.fn()}
        customer={{ phone: "", address: "" }}
        onCartsChange={setCarts}
        onNeedLogin={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Buyurtma qilish" }));
    await user.click(screen.getByRole("button", { name: "✅ Buyurtma yuborish" }));
    expect(screen.getByRole("alert"))
      .toHaveTextContent("Telefon raqam kiritish kerak.");
    expect(screen.getByLabelText("Aloqa telefon raqami *")).toHaveFocus();
    unmount();

    render(
      <CartV1656
        authenticated
        carts={oneStoreCart()}
        createOrder={vi.fn()}
        customer={{ phone: "+998901234567", address: "" }}
        onCartsChange={vi.fn()}
        onNeedLogin={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Buyurtma qilish" }));
    await user.click(screen.getByRole("button", { name: "✅ Buyurtma yuborish" }));
    expect(screen.getByRole("alert"))
      .toHaveTextContent("Yetkazib berish joyini xaritada belgilang.");
  });

  it("retains the receipt when the create API fails", async () => {
    const user = userEvent.setup();
    const createOrder = vi.fn().mockRejectedValue(new Error("Server xatosi"));
    render(<StatefulCart createOrder={createOrder} />);
    await user.click(screen.getByRole("button", { name: "Buyurtma qilish" }));
    await user.click(screen.getByRole("button", { name: /🏪 Olib ketish/ }));
    await user.click(screen.getByRole("button", { name: "✅ Buyurtma yuborish" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Server xatosi");
    expect(screen.getByText("Non")).toBeInTheDocument();
  });
});
