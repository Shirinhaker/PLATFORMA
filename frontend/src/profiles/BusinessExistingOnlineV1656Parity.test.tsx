import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CrudEditorView } from "./BusinessOnlineEditingViews";
import {
  MessagesView,
  NotificationsView,
  OrdersView,
  PaymentsView,
  PeopleView,
  ReviewsView,
  SubscriptionsView,
  isServiceOrder,
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


describe("v1656 mavjud Onlaynlashtirish ekranlari pariteti", () => {
  it("Obunalarim ekranini monolit matnlari, klasslari va holatlari bilan ko'rsatadi", () => {
    const { container } = render(
      <SubscriptionsView
        rows={[
          {
            id: 1,
            plan_code: "plus",
            status: "active",
            starts_at: 1_722_211_200,
            expires_at: 1_724_889_600,
          },
          {
            id: 2,
            plan: "free",
            status: "expired",
            starts_at: 1_719_619_200,
            expires_at: 1_722_211_200,
            duration_months: 1,
          },
        ]}
        duration={1}
        setDuration={vi.fn()}
        busy={false}
        openPayment={vi.fn()}
      />,
    );

    expect(container.firstElementChild).toHaveClass("subscription-shell");
    expect(screen.getByText(
      "Plus yoki Pro tarifini tanlang, kvitansiyani yuboring. Tarif administrator tasdiqlagandan keyin faollashadi.",
    )).toBeInTheDocument();
    expect(container.querySelector(".subscription-current-name"))
      .toHaveTextContent("Plus");
    expect(screen.getByText("Faol")).toHaveClass("subscription-current-badge");
    expect(screen.getByRole("button", { name: "1 oy" })).toHaveClass("on");
    expect(screen.getByRole("button", { name: "1 oy" }))
      .toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Bepul tarif avtomatik" }))
      .toBeDisabled();
    expect(screen.getByRole("button", { name: "Muddatni uzaytirish" }))
      .toBeEnabled();
    expect(screen.getByText(
      "Mahsulot yoki xizmatlarni “Sizga yaqin” bo‘limiga chiqarish huquqi",
    )).toBeInTheDocument();
    expect(screen.getByText("Avvalgi tariflar")).toBeInTheDocument();
    expect(container.querySelector(".subscription-history-row")).not.toBeNull();
  });

  it("To'lovlarim ekranini monolit kartasi va bo'sh holati bilan ko'rsatadi", () => {
    const { container, rerender } = render(
      <PaymentsView
        rows={[{
          id: 8,
          service_type: "subscription",
          plan_code: "pro",
          request_code: "PAY-8",
          amount: 149_000,
          status: "rejected",
          reason: "Chek aniq emas",
          created_at: 1_722_211_200,
        }]}
        loading={false}
        refresh={vi.fn()}
      />,
    );

    expect(container.querySelector(".form-wrap")).not.toBeNull();
    expect(screen.getByText("To‘lovlarim")).toHaveClass("lead");
    expect(screen.getByText(
      "Kvitansiya yuborilgan xizmatlar va administrator tekshiruvi holati.",
    )).toHaveClass("lead-sub");
    expect(screen.getByRole("button", { name: "Yangilash" }))
      .toHaveClass("btn", "btn-outline", "btn-block");
    expect(container.querySelector(".payment-card")).not.toBeNull();
    expect(screen.getByText("Pro obuna")).toBeInTheDocument();
    expect(screen.getByText("Rad etilgan")).toHaveClass("payment-status", "rejected");
    expect(screen.getByText("Chek aniq emas")).toHaveClass(
      "subscription-action-message",
      "error",
    );
    expect(screen.getByText("149 000 so'm")).toHaveClass("payment-card-amount");

    rerender(<PaymentsView rows={[]} loading={false} refresh={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "To‘lovlar yo‘q" }))
      .toBeInTheDocument();
    expect(screen.getByText("Yuborgan kvitansiyalaringiz shu yerda ko‘rinadi."))
      .toBeInTheDocument();
  });

  it("E'lonlar ro'yxati va formasini cab-elon etaloniga mos ko'rsatadi", async () => {
    const user = userEvent.setup();
    const shared = actions();
    const { container } = render(
      <CrudEditorView
        {...shared}
        resource="listings"
        rows={[{
          id: 12,
          title: "Biznes e'loni",
          price: "2 000 so'm",
          cat: "uy",
          visibility: "all",
          status: "active",
          media: [{ id: 1 }],
        }]}
        addLabel="+ E’lon"
        empty="Hozircha e’lon yo‘q."
        fields={["title", "description", "price", "category"]}
      />,
    );

    expect(container.querySelector(".ad-tabs")).not.toBeNull();
    expect(screen.getByRole("button", { name: "E'lonlarim" })).toHaveClass("ad-tab", "on");
    expect(screen.getByRole("button", { name: "+ E'lon joylash" }))
      .toHaveClass("btn", "btn-primary", "btn-block");
    expect(container.querySelector(".elon-item")).not.toBeNull();
    expect(screen.getByText("2 000 so'm")).toHaveClass("li-price");
    expect(screen.getByText("🌍 Butun platforma · Faol · 📎 1"))
      .toHaveClass("li-meta");

    await user.click(screen.getByRole("button", { name: "+ E'lon joylash" }));
    expect(screen.getByLabelText("Sarlavha"))
      .toHaveAttribute("placeholder", "Masalan: 3 xonali kvartira");
    expect(screen.getByLabelText("Narx"))
      .toHaveAttribute("placeholder", "Narx yoki «kelishilgan»");
    expect(screen.getByRole("button", { name: "📷 Galereya yoki papkadan tanlash" }))
      .toHaveClass("upload");
    expect(screen.getByRole("button", { name: "📍 Xaritada joy belgilash" }))
      .toHaveClass("upload");
    expect(screen.getByText("Butun platformaga")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Ish o'rinlari" }));
    expect(screen.getByRole("button", { name: "Ish o'rinlari" }))
      .toHaveClass("sort-chip", "on");
    expect(screen.getByRole("button", { name: "Uy-joy" }))
      .not.toHaveClass("on");
    await user.click(screen.getByRole("button", {
      name: /Faqat sahifam mehmonlariga/,
    }));
    expect(screen.getByRole("button", { name: /Faqat sahifam mehmonlariga/ }))
      .toHaveClass("vis-card", "on");
    expect(screen.getByRole("button", { name: /Butun platformaga/ }))
      .not.toHaveClass("on");
    expect(screen.getByRole("button", { name: "Joylash" }))
      .toHaveClass("btn", "btn-primary", "btn-block");
  });

  it("Reklamalar ro'yxatini cab-elon reklama tabi va aniq bekor qilish tasdig'i bilan ko'rsatadi", async () => {
    const user = userEvent.setup();
    const shared = actions();
    const { container } = render(
      <CrudEditorView
        {...shared}
        resource="advertisements"
        rows={[{
          id: 5,
          title: "Banner",
          status: "active",
          image_file: "/banner.jpg",
          targets: [{ level: "republic" }],
          price: 250_000,
          views: 12,
          clicks: 3,
          start_at: 1_722_211_200,
          duration_days: 3,
          daily_all_day: true,
        }]}
        addLabel="+ Reklama"
        empty="Hozircha reklama yo‘q."
        fields={["title", "caption"]}
      />,
    );

    expect(screen.getByRole("button", { name: "Reklamalarim" })).toHaveClass("ad-tab", "on");
    expect(screen.getByText(
      "Bosh sahifadagi banner reklama. Hudud, boshlanish vaqti va davomiyligini o'zingiz tanlaysiz.",
    )).toHaveClass("ad-info");
    expect(screen.getByRole("button", { name: "+ Reklama joylashtirish" }))
      .toHaveClass("btn", "btn-primary", "btn-block");
    expect(container.querySelector(".ad-own-card")).not.toBeNull();
    expect(screen.getByText("Faol")).toHaveClass("ad-status", "active");

    await user.click(screen.getByRole("button", { name: "Bekor qilish" }));
    expect(shared.remove).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog"))
      .toHaveTextContent("Reklama bekor qilinsinmi?");
  });

  it("Buyurtmalarni monolitdagi uch tab va order-card klasslari bilan ko'rsatadi", () => {
    const { container } = render(
      <OrdersView
        rows={[
          {
            id: 44,
            title: "Muhr",
            status: "new",
            order_category: "product",
            order_type: "delivery",
            customer_name: "Ali",
            is_unread: 1,
            created_at: 1_722_211_200,
            items: [{ id: 1, name: "Muhr", qty: 1, unit: "dona", line_total: 15_000 }],
            total_text: "15 000 so'm",
          },
          { id: 45, title: "Muammo", status: "accepted", problem_open: 1 },
          { id: 46, title: "Eski", status: "done" },
        ]}
        filter="new"
        setFilter={vi.fn()}
        busy={false}
        setStatus={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.getByRole("button", { name: /Buyurtmalar \(1\)/ }))
      .toHaveClass("seg-b", "on");
    expect(screen.getByRole("button", { name: "Muammoli (1)" })).toHaveClass("seg-b");
    expect(screen.getByRole("button", { name: /Yakunlangan \(1\)/ })).toHaveClass("seg-b");
    expect(container.querySelector(".item.order-card.order-new.order-unread"))
      .not.toBeNull();
    expect(screen.getByText("BUYURTMA №44")).toHaveClass("order-no-pill");
    expect(screen.getByText(/🕒 \d{2}\/\d{2}\/\d{4} · \d{2}:\d{2}/))
      .toHaveClass("idesc", "order-card-time");
    expect(screen.getByText("Mijoz: Ali")).toHaveClass("idesc");
    expect(screen.getByText("🔔 Yangi buyurtma")).toHaveClass("order-unread-pill");
    expect(screen.getByRole("button", { name: "Qabul qilish" })).toHaveClass("mini-btn");
    expect(screen.getByRole("button", { name: "Rad etish" })).toHaveClass("mini-btn");
  });

  it("xizmat buyurtmasini monolit kabi order_category bo'yicha ajratadi", () => {
    expect(isServiceOrder({
      order_category: "service",
      order_type: "delivery",
    })).toBe(true);
    expect(isServiceOrder({
      order_category: "product",
      order_type: "service",
    })).toBe(false);
  });

  it("Suhbatlar avval conversation ro'yxatini, keyin chat oynasini ko'rsatadi", async () => {
    const user = userEvent.setup();
    const send = vi.fn().mockResolvedValue(undefined);
    const { container } = render(
      <MessagesView
        rows={[{
          id: 3,
          target_id: 9,
          target_kind: "user",
          name: "Ali Valiyev",
          text: "Salom",
          last: "Salom",
          unread: 2,
          sender_kind: "user",
          created_at: 1_722_211_200,
        }]}
        value="Yuboriladigan xabar"
        setValue={vi.fn()}
        busy={false}
        send={send}
      />,
    );

    expect(container.querySelector(".conv")).not.toBeNull();
    expect(screen.getByText("Ali Valiyev")).toHaveClass("conv-name");
    expect(screen.getByText("Salom")).toHaveClass("conv-last");
    expect(screen.getByText("2")).toHaveClass("conv-badge");
    expect(screen.queryByPlaceholderText("Xabar yozing...")).not.toBeInTheDocument();

    await user.click(screen.getByText("Ali Valiyev"));
    expect(container.querySelector(".chat-compose")).not.toBeNull();
    expect(screen.getByPlaceholderText("Xabar yozing...")).toHaveClass("chat-input");
    expect(screen.getByRole("button", { name: "Yuborish" })).toHaveClass("chat-send");
    expect(screen.getByRole("button", { name: "Xabar amallari" }))
      .toHaveClass("order-msg-menu-btn");
    await user.click(screen.getByRole("button", { name: "Yuborish" }));
    expect(send).toHaveBeenCalledWith(
      { id: "9", kind: "user" },
      "Yuboriladigan xabar",
    );
  });

  it("Mijoz fikrlarini sp-review-card va monolit javob formasi bilan ko'rsatadi", () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const { container } = render(
      <ReviewsView
        rows={[{
          id: 4,
          user_name: "Ali",
          stars: 5,
          comment: "Yaxshi",
          owner_reply: "Rahmat",
          created_at: 1_722_211_200,
        }]}
        ratingSum={5}
        ratingCount={1}
        replyId={null}
        reply=""
        setReplyId={vi.fn()}
        setReply={vi.fn()}
        busy={false}
        save={save}
      />,
    );

    expect(screen.getByText("O'rtacha baho")).toHaveClass("idesc");
    expect(screen.getByText(
      "Mijoz fikrini o'chirib bo'lmaydi. Har bir fikrga javob berishingiz va javobingizni yangilashingiz mumkin.",
    )).toHaveClass("idesc");
    expect(container.querySelector(".sp-review-card")).not.toBeNull();
    expect(screen.getByText("Sizning javobingiz")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Mijozga javob yozing..."))
      .toHaveClass("textarea");
    expect(screen.getByRole("button", { name: "Javobni yangilash" }))
      .toHaveClass("btn", "btn-soft", "btn-block");
    screen.getByRole("button", { name: "Javobni yangilash" }).click();
    expect(save).toHaveBeenCalledWith(4, "Rahmat");
  });

  it("bo'sh mijoz javobida monolitdagi aniq xabarni ko'rsatadi", async () => {
    const user = userEvent.setup();
    const save = vi.fn().mockResolvedValue(undefined);
    render(
      <ReviewsView
        rows={[{ id: 4, user_name: "Ali", stars: 5, comment: "Yaxshi" }]}
        ratingSum={5}
        ratingCount={1}
        replyId={null}
        reply=""
        setReplyId={vi.fn()}
        setReply={vi.fn()}
        busy={false}
        save={save}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Javob berish" }));

    expect(screen.getByRole("alert"))
      .toHaveTextContent("Javob matnini kiriting.");
    expect(save).not.toHaveBeenCalled();
  });

  it("Istoriyalarni Faol/Arxiv tabi va my-story-card bilan ko'rsatadi", async () => {
    const user = userEvent.setup();
    const shared = actions();
    const { container } = render(
      <CrudEditorView
        {...shared}
        resource="stories"
        rows={[{
          id: 6,
          caption: "Bugungi ish",
          status: "active",
          state: "active",
          media_type: "photo",
          thumbnail_url: "/story.jpg",
          created_at: 1_722_211_200,
          expires_at: 4_102_444_800,
          view_count: 7,
        }]}
        addLabel="+ Istoriya"
        empty="Hozircha istoriya yo‘q."
        fields={["caption", "media_type", "media_url"]}
      />,
    );

    expect(container.querySelector(".my-stories-shell")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Faol" })).toHaveClass("ad-tab", "on");
    expect(screen.getByRole("button", { name: "Arxiv" })).toHaveClass("ad-tab");
    expect(container.querySelector(".my-story-card")).not.toBeNull();
    expect(screen.getByText("Bugungi ish")).toHaveClass("my-story-caption");
    expect(screen.getByText(/👁 7 ko‘rish/)).toHaveClass("my-story-meta");
    expect(screen.getByText(/^Faol · .* qoldi$/)).toHaveClass("my-story-state");
    expect(screen.getByRole("button", { name: "Ko‘rish" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "O‘chirish" })).toHaveClass("danger");

    await user.click(screen.getByRole("button", { name: "Arxiv" }));
    expect(screen.getByRole("heading", { name: "Arxiv hozircha bo‘sh" }))
      .toBeInTheDocument();
    expect(screen.getByText("24 soati tugagan istoriyalar shu yerda saqlanadi."))
      .toBeInTheDocument();
  });

  it("Bildirishnomalarni monolit bo'limlari va menu-card klassida ko'rsatadi", () => {
    const { container } = render(
      <NotificationsView
        rows={[{
          id: 7,
          title: "Yangi xabar",
          body: "Buyurtma yangilandi",
          is_read: 0,
          created_at: 1_722_211_200,
        }]}
        busy={false}
        markAll={vi.fn().mockResolvedValue(undefined)}
        markOne={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.getByText("Bildirishnomalarim")).toHaveClass("lead");
    expect(screen.getByText(
      "Buyurtma jarayonidagi muhim xabarlar shu yerda saqlanadi.",
    )).toHaveClass("lead-sub");
    expect(screen.getByText("📲 Push notification")).toBeInTheDocument();
    expect(screen.getByText("Mobil ilova qurilmasi ulanmagan."))
      .toHaveClass("elon-hint");
    expect(screen.getByRole("button", { name: "Barchasini o'qish" }))
      .toHaveClass("mini-btn");
    expect(container.querySelector(".menu-card")).not.toBeNull();
    expect(screen.getByText("Yangi xabar")).toBeInTheDocument();
    expect(screen.getByText("E'lon filtrlari")).toHaveClass("lead");
    expect(screen.getByRole("button", { name: "➕ Yangi filtr qo'shish" }))
      .toHaveClass("btn", "btn-primary", "btn-block");
  });

  it("Obunachilar va kuzatilayotganlarning aniq hisob va bo'sh holatlarini ko'rsatadi", () => {
    const { container, rerender } = render(
      <PeopleView
        kind="followers"
        rows={[{ id: 8, kind: "user", name: "Vali", info: "@vali" }]}
        busy={false}
      />,
    );

    expect(screen.getByText("1 ta obunachi")).toHaveClass("list-sub");
    expect(container.querySelector(".elon-item")).not.toBeNull();
    expect(screen.getByText("Vali")).toHaveClass("li-title");
    expect(screen.getByText("Foydalanuvchi · @vali")).toHaveClass("li-meta");

    rerender(<PeopleView kind="following" rows={[]} busy={false} />);
    const empty = screen.getByRole("heading", { name: "Kuzatayotganlar yo'q" })
      .closest(".empty");
    expect(empty).not.toBeNull();
    expect(within(empty as HTMLElement).getByText(
      "Biznes yoki mutaxassisni kuzatganingizda shu yerda ko'rinadi.",
    )).toBeInTheDocument();
  });
});
