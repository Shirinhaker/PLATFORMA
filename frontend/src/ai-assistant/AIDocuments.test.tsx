import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AIDocuments } from "./AIDocuments";

const fixture = () => ({
  askAIDocument: vi.fn().mockResolvedValue({ answer: "10 kun, 2-band" }),
  generateAIDocumentDraft: vi.fn().mockResolvedValue({
    source: "openai",
    title: "Taklif",
    body: "Qoralama",
    direction: "chiquvchi",
    doc_type: "Taklif",
    number: "",
    doc_date: "2026-09-26",
  }),
  createDocument: vi.fn().mockResolvedValue({ ok: true, id: 10 }),
});
async function upload() {
  fireEvent.change(screen.getByLabelText("Hujjat tanlash"), {
    target: { files: [new File(["10 kun"], "shartnoma.txt", { type: "text/plain" })] },
  });
  await screen.findByText("shartnoma.txt");
}

describe("AI documents", () => {
  it("sends selected document and follow-up history; removing file clears context", async () => {
    const api = fixture();
    render(<AIDocuments api={api} />);
    await upload();
    fireEvent.change(screen.getByLabelText("Hujjat bo'yicha savol"), {
      target: { value: "Muddati?" },
    });
    fireEvent.click(screen.getByText("Hujjatdan javob olish"));
    await screen.findByText("10 kun, 2-band");
    expect(api.askAIDocument.mock.calls[0]?.[0]).toMatchObject({
      attachment: { name: "shartnoma.txt", data: btoa("10 kun") },
      history: [],
    });
    fireEvent.change(screen.getByLabelText("Hujjat bo'yicha savol"), {
      target: { value: "Qaysi band?" },
    });
    fireEvent.click(screen.getByText("Hujjatdan javob olish"));
    await waitFor(() => expect(api.askAIDocument).toHaveBeenCalledTimes(2));
    expect(api.askAIDocument.mock.calls[1]?.[0].history).toHaveLength(2);
    await waitFor(() =>
      expect(screen.getByText("Faylni olib tashlash")).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByText("Faylni olib tashlash"));
    expect(screen.queryByText("shartnoma.txt")).not.toBeInTheDocument();
    expect(screen.getByText("Hujjatdan javob olish")).toBeDisabled();
  });
  it("rejects unsupported files without calling AI", async () => {
    const api = fixture();
    render(<AIDocuments api={api} />);
    fireEvent.change(screen.getByLabelText("Hujjat tanlash"), {
      target: { files: [new File(["abc"], "x.exe")] },
    });
    expect(await screen.findByRole("alert")).toHaveTextContent("2 MB");
    expect(api.askAIDocument).not.toHaveBeenCalled();
  });
  it("preserves question and file on error for retry", async () => {
    const api = fixture();
    api.askAIDocument.mockRejectedValueOnce(new Error("AI vaqtincha ishlamayapti"));
    render(<AIDocuments api={api} />);
    await upload();
    fireEvent.change(screen.getByLabelText("Hujjat bo'yicha savol"), {
      target: { value: "Muddati?" },
    });
    fireEvent.click(screen.getByText("Hujjatdan javob olish"));
    expect(await screen.findByRole("alert")).toHaveTextContent("AI vaqtincha");
    expect(screen.getByLabelText("Hujjat bo'yicha savol")).toHaveValue("Muddati?");
    expect(screen.getByText("shartnoma.txt")).toBeInTheDocument();
  });
  it("only saves edited draft after explicit confirmation, once", async () => {
    const api = fixture();
    render(<AIDocuments api={api} />);
    fireEvent.change(screen.getByLabelText("Hujjat topshirig'i"), {
      target: { value: "Taklif yoz" },
    });
    fireEvent.click(screen.getByText("Qoralama yaratish"));
    const body = await screen.findByLabelText("Qoralama matni");
    expect(api.createDocument).not.toHaveBeenCalled();
    fireEvent.change(body, { target: { value: "Tekshirilgan matn" } });
    fireEvent.click(screen.getByText("Tekshirdim — Hujjatlarga saqlash"));
    await screen.findByText(/Hujjat saqlandi/);
    expect(api.createDocument).toHaveBeenCalledWith(
      expect.objectContaining({ body: "Tekshirilgan matn", direction: "chiquvchi" }),
    );
    expect(screen.getByText("Tekshirdim — Hujjatlarga saqlash")).toBeDisabled();
  });
});
