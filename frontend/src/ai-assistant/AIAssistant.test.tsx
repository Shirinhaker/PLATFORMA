import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AIAssistant } from "./AIAssistant";
import { SYSTEM_MENUS } from "../profiles/business-profile-config";


describe("AIAssistant", () => {
  it("loads history and sends a modular question", async () => {
    const api = {
      getAIChatHistory: vi.fn().mockResolvedValue({ history: [{ role: "assistant" as const, text: "Oldingi javob", created_at: "2026-08-10T10:00:00Z" }] }),
      sendAIChatMessage: vi.fn().mockResolvedValue({ answer: "Tushum 500 000 so'm" }),
    };
    render(<AIAssistant api={api} onBack={vi.fn()} />);
    expect(await screen.findByText("Oldingi javob")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Savol yozing"), { target: { value: "Bugun qanday?" } });
    fireEvent.click(screen.getByLabelText("Yuborish"));
    await waitFor(() => expect(api.sendAIChatMessage).toHaveBeenCalledWith("Bugun qanday?", false));
    expect(await screen.findByText("Tushum 500 000 so'm")).toBeInTheDocument();
    expect(screen.getByText("AI ma'lumotlarni o'qiydi va tushuntiradi. O'zi o'zgartirish kiritmaydi.")).toBeInTheDocument();
  });

  it("sends a quick chip", async () => {
    const api = { getAIChatHistory: vi.fn().mockResolvedValue({ history: [] }), sendAIChatMessage: vi.fn().mockResolvedValue({ answer: "Ombor yaxshi" }) };
    render(<AIAssistant api={api} onBack={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Ombor holati" }));
    await waitFor(() => expect(api.sendAIChatMessage).toHaveBeenCalledWith("Ombor holati", false));
  });

  it("keeps every modular label and quick chip letter-for-letter", async () => {
    const api = { getAIChatHistory: vi.fn().mockResolvedValue({ history: [] }), sendAIChatMessage: vi.fn() };
    render(<AIAssistant api={api} onBack={vi.fn()} />);

    expect(await screen.findByText("Savdo, ombor, qarz va buyurtmalar bo'yicha savol bering. Masalan: \"Bugun qanday?\"")).toBeInTheDocument();
    for (const chip of ["Bugungi xulosa", "Ombor holati", "Qarzlar qancha", "Eng ko'p sotilgan", "Buyurtmalar"]) {
      expect(screen.getByRole("button", { name: chip })).toHaveClass("seg-b");
    }
    expect(screen.getByLabelText("Savol yozing")).toHaveClass("chat-input");
    expect(screen.getByLabelText("Yuborish")).toHaveClass("chat-send");
    expect(SYSTEM_MENUS.find((menu) => menu.view === "ai-assistant")?.caption).toBe(
      "Savdo, ombor, qarz bo'yicha savol bering",
    );
  });

  it("shows a failed request in the assistant message stream like modular", async () => {
    const api = {
      getAIChatHistory: vi.fn().mockResolvedValue({ history: [] }),
      sendAIChatMessage: vi.fn().mockRejectedValue(new Error("Tarmoq ishlamayapti")),
    };
    render(<AIAssistant api={api} onBack={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Qarzlar qancha" }));

    expect(await screen.findByText("Xatolik: Tarmoq ishlamayapti")).toBeInTheDocument();
    expect(screen.getByText("Xatolik: Tarmoq ishlamayapti").parentElement).toHaveClass(
      "ai1656__row--assistant",
    );
  });
});
