import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CrudEditorView } from "./BusinessOnlineEditingViews";
import {
  MessagesView,
  NotificationsView,
  OrdersView,
  PaymentsView,
  ReviewsView,
} from "./BusinessOnlineViews";


function actions() {
  return {
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
}


describe("Claude review v1656 interaktiv pariteti", () => {
  it("rad etilgan to'lov uchun kvitansiya tanlaydi va qayta yuboradi", async () => {
    const user = userEvent.setup();
    const resubmit = vi.fn().mockResolvedValue(undefined);
    const { container } = render(
      <PaymentsView
        rows={[{ id: 8, status: "rejected", amount: 149000 }]}
        loading={false}
        refresh={vi.fn()}
        resubmit={resubmit}
      />,
    );
    const file = new File(["receipt"], "chek.png", { type: "image/png" });
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;

    expect(input).toHaveAttribute("accept", "image/jpeg,image/png,image/webp");
    await user.upload(input, file);
    expect(screen.getByRole("button", { name: "Kvitansiya tanlandi ✅" }))
      .toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Qayta yuborish" }));

    expect(resubmit).toHaveBeenCalledWith(8, file);
  });

  it("xabar menyusida javob, nusxa, tahrirlash va tasdiqli o'chirishni bajaradi", async () => {
    const user = userEvent.setup();
    const setValue = vi.fn();
    const send = vi.fn().mockResolvedValue(undefined);
    const edit = vi.fn().mockResolvedValue(undefined);
    const remove = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
    const { rerender } = render(
      <MessagesView
        rows={[{
          id: 3,
          target_id: 9,
          target_kind: "user",
          name: "Ali",
          text: "Salom",
          sender_kind: "business",
        }]}
        value="Javob matni"
        setValue={setValue}
        busy={false}
        send={send}
        edit={edit}
        remove={remove}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Ali/ }));
    await user.click(screen.getByRole("button", { name: "Xabar amallari" }));
    const menu = screen.getByRole("menu");
    expect(within(menu).getByRole("button", { name: "↩️ Javob berish" }))
      .toBeInTheDocument();
    expect(within(menu).getByRole("button", { name: "📋 Nusxalash" }))
      .toBeInTheDocument();
    expect(within(menu).getByRole("button", { name: "✏️ Tahrirlash" }))
      .toBeInTheDocument();
    expect(within(menu).getByRole("button", { name: "🗑 O‘chirish" }))
      .toBeInTheDocument();

    await user.click(within(menu).getByRole("button", { name: "↩️ Javob berish" }));
    expect(screen.getByText("Javob berilyapti")).toHaveClass("order-chat-state", "on");
    await user.click(screen.getByRole("button", { name: "Yuborish" }));
    expect(send).toHaveBeenCalledWith(
      { id: "9", kind: "user" },
      "Javob matni",
      3,
    );

    rerender(
      <MessagesView
        rows={[{
          id: 3,
          target_id: 9,
          target_kind: "user",
          name: "Ali",
          text: "Salom",
          sender_kind: "business",
        }]}
        value="Tahrirlangan"
        setValue={setValue}
        busy={false}
        send={send}
        edit={edit}
        remove={remove}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Xabar amallari" }));
    await user.click(screen.getByRole("button", { name: "✏️ Tahrirlash" }));
    expect(setValue).toHaveBeenCalledWith("Salom");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    expect(edit).toHaveBeenCalledWith(3, "Tahrirlangan");

    await user.click(screen.getByRole("button", { name: "Xabar amallari" }));
    await user.click(screen.getByRole("button", { name: "🗑 O‘chirish" }));
    expect(remove).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toHaveTextContent("Bu xabar o‘chirilsinmi?");
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "O‘chirish" }));
    expect(remove).toHaveBeenCalledWith(3);
  });

  it("bildirishnoma filtrlarini ro'yxatdan ko'rsatadi, yaratadi va tasdiq bilan o'chiradi", async () => {
    const user = userEvent.setup();
    const createFilter = vi.fn().mockResolvedValue(undefined);
    const removeFilter = vi.fn().mockResolvedValue(undefined);
    render(
      <NotificationsView
        rows={[]}
        filters={[{ id: 14, cat: "uy", district: "Qumqo‘rg‘on", keyword: "hovli" }]}
        busy={false}
        markAll={vi.fn().mockResolvedValue(undefined)}
        markOne={vi.fn().mockResolvedValue(undefined)}
        createFilter={createFilter}
        removeFilter={removeFilter}
      />,
    );

    expect(screen.getByText("Uy-joy")).toBeInTheDocument();
    expect(screen.getByText("Qumqo‘rg‘on · «hovli»")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "➕ Yangi filtr qo'shish" }));
    expect(screen.getByText("Faqat sizga kerakli e'lonlar haqida xabar olasiz."))
      .toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Tur (majburiy)"), "ish");
    await user.type(screen.getByLabelText("Viloyat — ixtiyoriy"), "Surxondaryo");
    await user.type(screen.getByLabelText("Tuman — ixtiyoriy"), "Qumqo‘rg‘on");
    await user.type(screen.getByLabelText("Kalit so'z — ixtiyoriy"), "dasturchi");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    expect(createFilter).toHaveBeenCalledWith(expect.objectContaining({
      cat: "ish",
      region: "Surxondaryo",
      district: "Qumqo‘rg‘on",
      keyword: "dasturchi",
    }));
    await user.click(screen.getByRole("button", { name: "Filtrni o'chirish" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("Bu filtrni o'chirasizmi?");
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "O'chirish" }));
    expect(removeFilter).toHaveBeenCalledWith(14);
  });

  it("istoriya ko'rish oynasi, joylash formasi va aniq o'chirish matnini ishlatadi", async () => {
    const user = userEvent.setup();
    const shared = actions();
    const { rerender } = render(
      <CrudEditorView
        {...shared}
        resource="stories"
        rows={[{
          id: 6,
          caption: "Bugungi ish",
          state: "active",
          media_type: "photo",
          media_url: "/story.jpg",
          created_at: 1_722_211_200,
          expires_at: 4_102_444_800,
        }]}
        addLabel="+ Istoriya"
        empty="Hozircha istoriya yo‘q."
        fields={["caption", "media_type", "media_url"]}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Ko‘rish" }));
    expect(screen.getByRole("dialog", { name: "Istoriya" }))
      .toHaveTextContent("Bugungi ish");
    await user.click(screen.getByRole("button", { name: "Istoriyani yopish" }));
    await user.click(screen.getByRole("button", { name: "O‘chirish" }));
    expect(screen.getByRole("dialog")).toHaveTextContent(
      "Istoriya va uning media fayli butunlay o‘chiriladi.",
    );
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Bekor qilish" }));

    rerender(
      <CrudEditorView
        {...shared}
        resource="stories"
        rows={[]}
        addLabel="+ Istoriya"
        empty="Hozircha istoriya yo‘q."
        fields={["caption", "media_type", "media_url"]}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Istoriya joylash" }));
    expect(screen.getByRole("dialog", { name: "Istoriya joylash" }))
      .toBeInTheDocument();
    expect(screen.getByLabelText("Istoriya media fayli"))
      .toHaveAttribute(
        "accept",
        "image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm",
      );
    const storyFile = new File(["story"], "story.jpg", { type: "image/jpeg" });
    await user.upload(screen.getByLabelText("Istoriya media fayli"), storyFile);
    await user.type(screen.getByPlaceholderText("Istoriya haqida qisqa yozing"), "Yangi istoriya");
    await user.click(screen.getByRole("button", { name: "Joylash" }));
    expect(shared.create).toHaveBeenCalledWith("stories", expect.objectContaining({
      caption: "Yangi istoriya",
      media_file: "story.jpg",
      media_type: "photo",
    }));
  });

  it("buyurtmaning to'lov muammosi va topshirish amallarini bajaradi", async () => {
    const user = userEvent.setup();
    const action = vi.fn().mockResolvedValue(undefined);
    const { rerender } = render(
      <OrdersView
        rows={[{
          id: 44,
          title: "Buyurtma",
          status: "accepted",
          payment_status: "submitted",
        }]}
        filter="new"
        setFilter={vi.fn()}
        busy={false}
        setStatus={vi.fn().mockResolvedValue(undefined)}
        action={action}
      />,
    );
    await user.click(screen.getByRole("button", { name: "⚠️ To'lov muammosi" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("To'lov bo'yicha muammo");
    await user.type(screen.getByLabelText("Izoh"), "Chek o'qilmaydi");
    await user.click(screen.getByRole("button", { name: "Muammoli buyurtmaga o'tkazish" }));
    expect(action).toHaveBeenCalledWith(44, "report_problem", expect.objectContaining({
      reason: "not_received",
      note: "Chek o'qilmaydi",
    }));

    rerender(
      <OrdersView
        rows={[{ id: 45, title: "Dostavka", status: "handoff_waiting_seller", order_type: "delivery" }]}
        filter="new"
        setFilter={vi.fn()}
        busy={false}
        setStatus={vi.fn().mockResolvedValue(undefined)}
        action={action}
      />,
    );
    await user.click(screen.getByRole("button", { name: "📦 Dostavkachiga topshirdim" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("Buyurtma qarshi tomonga topshirildimi?");
    await user.click(screen.getByRole("button", { name: "Ha, topshirdim" }));
    expect(action).toHaveBeenCalledWith(45, "handoff");
  });

  it("muammoli buyurtmada sabab va izohni monolit matni bilan ko'rsatadi", async () => {
    render(
      <OrdersView
        rows={[{
          id: 46,
          title: "Muammoli buyurtma",
          status: "accepted",
          problem_open: 1,
          problem_reason: "receipt_unreadable",
          problem_note: "Rasm juda xira",
        }]}
        filter="active"
        setFilter={vi.fn()}
        busy={false}
        setStatus={vi.fn().mockResolvedValue(undefined)}
        action={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.getByText("⚠️ To'lov aniqlashtirilmoqda"))
      .toBeInTheDocument();
    expect(screen.getByText("Chek rasmi o'qilmaydi"))
      .toBeInTheDocument();
    expect(screen.getByText("Izoh: Rasm juda xira"))
      .toBeInTheDocument();
  });

  it("push sozlamasini server holatidan ko'rsatadi va o'zgarishni saqlaydi", async () => {
    const user = userEvent.setup();
    const savePushPreference = vi.fn().mockResolvedValue(undefined);
    render(
      <NotificationsView
        rows={[]}
        filters={[]}
        pushPreference={{ enabled: 0, orders_enabled: 0 }}
        busy={false}
        markAll={vi.fn().mockResolvedValue(undefined)}
        markOne={vi.fn().mockResolvedValue(undefined)}
        savePushPreference={savePushPreference}
      />,
    );

    const checkbox = screen.getByRole("checkbox", { name: "Yoqilgan" });
    expect(checkbox).not.toBeChecked();
    await user.click(checkbox);
    expect(savePushPreference).toHaveBeenCalledWith(true);
  });

  it("e'lon joylashuvini va reklamaning majburiy maydonlarini tekshiradi", async () => {
    const user = userEvent.setup();
    const listing = actions();
    const { rerender } = render(
      <CrudEditorView
        {...listing}
        resource="listings"
        rows={[]}
        addLabel="+ E’lon"
        empty="Hozircha e’lon yo‘q."
        fields={["title"]}
      />,
    );
    await user.click(screen.getByRole("button", { name: "+ E'lon joylash" }));
    await user.type(screen.getByLabelText("Sarlavha"), "Uy sotiladi");
    await user.click(screen.getByRole("button", { name: "Joylash" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Iltimos, e'lon joyini xaritada belgilang (📍 Xaritada joy belgilash).",
    );
    expect(listing.create).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "📍 Xaritada joy belgilash" }));
    expect(document.querySelector('[data-screen="pickloc"]')).toBeInTheDocument();
    expect(screen.queryByLabelText("Kenglik")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Uzunlik")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Bekor qilish" }));

    const advertisement = actions();
    rerender(
      <CrudEditorView
        {...advertisement}
        resource="advertisements"
        rows={[]}
        addLabel="+ Reklama"
        empty="Hozircha reklama yo‘q."
        fields={["title", "caption"]}
      />,
    );
    await user.click(screen.getByRole("button", { name: "+ Reklama joylashtirish" }));
    await user.click(screen.getByRole("button", { name: "Reklamani joylashtirish" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Reklama rasmini tanlang.");
    expect(advertisement.create).not.toHaveBeenCalled();
    await user.upload(
      screen.getByLabelText("Kompyuter uchun rasm"),
      new File(["banner"], "banner.webp", { type: "image/webp" }),
    );
    await user.type(screen.getByLabelText("Reklama sarlavhasi"), "Yozgi aksiya");
    await user.selectOptions(screen.getByLabelText("Hudud darajasi"), "republic");
    await user.click(screen.getByRole("button", { name: "+ Hududni qo'shish" }));
    await user.click(screen.getByRole("button", { name: "Reklamani joylashtirish" }));
    expect(advertisement.create).toHaveBeenCalledWith(
      "advertisements",
      expect.objectContaining({
        image_file: "banner.webp",
        title: "Yozgi aksiya",
        targets: [{ level: "republic", region: "", district: "" }],
      }),
    );
  });

  it("reklama hududlarini katalogdan tanlaydi va narxni backend orqali jonli hisoblaydi", async () => {
    const user = userEvent.setup();
    const advertisement = actions();
    const quoteAdvertisement = vi.fn().mockResolvedValue({
      district_count: 172,
      hours_per_day: 24,
      duration_days: 1,
      district_hour_rate: 20_000,
      billable_district_hours: 4_128,
      total: 82_560_000,
      currency: "UZS",
    });
    render(
      <CrudEditorView
        {...advertisement}
        resource="advertisements"
        rows={[]}
        addLabel="+ Reklama"
        empty="Hozircha reklama yo‘q."
        fields={["title", "caption"]}
        quoteAdvertisement={quoteAdvertisement}
      />,
    );

    await user.click(screen.getByRole("button", { name: "+ Reklama joylashtirish" }));
    expect(screen.getByLabelText("Reklama viloyati").tagName).toBe("SELECT");
    expect(screen.getByLabelText("Reklama tumani").tagName).toBe("SELECT");
    await user.selectOptions(screen.getByLabelText("Hudud darajasi"), "republic");
    await user.click(screen.getByRole("button", { name: "+ Hududni qo'shish" }));

    await waitFor(() => expect(quoteAdvertisement).toHaveBeenCalledWith({
      targets: [{ level: "republic", region: "", district: "" }],
      duration_days: 1,
      daily_all_day: true,
      daily_start: "19:00",
      daily_end: "21:00",
    }));
    expect(await screen.findByText(/82[\s\u00a0]560[\s\u00a0]000 so'm/))
      .toBeInTheDocument();
    expect(screen.getByText(/172 tuman × 24 soat × 1 kun ×/))
      .toBeInTheDocument();
  });

  it("mijoz reytingini monolit kabi doim beshta yulduz bilan ko'rsatadi", () => {
    render(
      <ReviewsView
        rows={[{ id: 4, stars: 3, comment: "Yaxshi" }]}
        ratingSum={3}
        ratingCount={1}
        replyId={null}
        reply=""
        setReplyId={vi.fn()}
        setReply={vi.fn()}
        busy={false}
        save={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    const stars = screen.getByLabelText("5 dan 3 baho");
    expect(stars).toHaveTextContent("★★★★★");
    expect(stars.querySelectorAll(".rv-star")).toHaveLength(5);
  });
});
