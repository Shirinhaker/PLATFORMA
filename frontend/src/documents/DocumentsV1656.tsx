import { useCallback, useEffect, useMemo, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  BusinessDocument,
  BusinessDocumentWrite,
  BusinessProfile,
  DocumentCounterparty,
  DocumentCounterpartyWrite,
  DocumentDirection,
} from "../api/types";
import { DOCUMENT_TYPES, generateDocumentTemplate } from "./templates";
import "./DocumentsV1656.css";

export type DocumentsApi = Pick<
  ApiClient,
  | "getDocumentCounterparties"
  | "createDocumentCounterparty"
  | "updateDocumentCounterparty"
  | "deleteDocumentCounterparty"
  | "getDocuments"
  | "getDocument"
  | "createDocument"
  | "updateDocument"
  | "deleteDocument"
  | "sendDocument"
  | "respondDocument"
  | "updateBusinessProfile"
>;

type Props = {
  api: DocumentsApi;
  profile: BusinessProfile;
  initialView: "profile" | "center";
  canManageCounterparties: boolean;
  onProfile: (profile: BusinessProfile) => void;
  onBack: () => void;
};

type View =
  | "profile"
  | "center"
  | "counterparties"
  | "counterparty-form"
  | "compose"
  | "list"
  | "document";

const EMPTY_COUNTERPARTY: DocumentCounterpartyWrite = {
  name: "",
  ctype: "Yetkazib beruvchi",
  director: "",
  phone: "",
  address: "",
  inn: "",
  account: "",
  bank: "",
  mfo: "",
  note: "",
};

const DIRECTION_TEXT: Record<DocumentDirection, string> = {
  ichki: "Ichki",
  chiquvchi: "Chiquvchi",
  kiruvchi: "Kiruvchi",
};

const STATUS_CLASS: Record<string, string> = {
  yuborilgan: "sent",
  kutilmoqda: "waiting",
  "qabul qilindi": "accepted",
  "rad etildi": "rejected",
};

function errorText(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

function today() {
  const date = new Date();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

function preview(body: string) {
  return body.replace(/\s+/g, " ").trim().slice(0, 60);
}

async function copyText(value: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const area = document.createElement("textarea");
  area.value = value;
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  document.execCommand("copy");
  area.remove();
}

function StatusBadge({ status }: { status: string }) {
  if (!status) return null;
  return (
    <span className={`documents-v1656__status ${STATUS_CLASS[status] ?? ""}`}>
      {status}
    </span>
  );
}

function ScreenHeader({ title, onBack }: { title: string; onBack: () => void }) {
  return (
    <header className="documents-v1656__header">
      <button type="button" className="documents-v1656__back" onClick={onBack}>
        <span className="documents-v1656__sr-only">Orqaga</span>←
      </button>
      <h1>{title}</h1>
    </header>
  );
}

export function DocumentsV1656({
  api,
  profile,
  initialView,
  canManageCounterparties,
  onProfile,
  onBack,
}: Props) {
  const [view, setView] = useState<View>(initialView);
  const [direction, setDirection] = useState<DocumentDirection>("ichki");
  const [counterparties, setCounterparties] = useState<DocumentCounterparty[]>([]);
  const [counterpartyTypes, setCounterpartyTypes] = useState([
    "Yetkazib beruvchi",
    "Mijoz",
    "Hamkor",
    "Boshqa",
  ]);
  const [counterparty, setCounterparty] = useState<DocumentCounterparty | null>(null);
  const [counterpartyForm, setCounterpartyForm] = useState(EMPTY_COUNTERPARTY);
  const [documents, setDocuments] = useState<BusinessDocument[]>([]);
  const [selected, setSelected] = useState<BusinessDocument | null>(null);
  const [profileForm, setProfileForm] = useState({
    director: profile.director,
    tax_id: profile.tax_id,
  });
  const [compose, setCompose] = useState<BusinessDocumentWrite>({
    direction: "ichki",
    doc_type: DOCUMENT_TYPES.ichki[0] ?? "Buyruq",
    title: "",
    number: "",
    doc_date: today(),
    contractor_id: null,
    body: "",
  });
  const [firmName, setFirmName] = useState(profile.name);
  const [director, setDirector] = useState(profile.director);
  const [taxId, setTaxId] = useState(profile.tax_id);
  const [receiverInn, setReceiverInn] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const selectedCounterparty = useMemo(
    () => counterparties.find((row) => row.id === compose.contractor_id),
    [compose.contractor_id, counterparties],
  );

  const loadCounterparties = useCallback(async () => {
    const result = await api.getDocumentCounterparties();
    setCounterparties(result.counterparties);
    if (result.types.length) setCounterpartyTypes(result.types);
  }, [api]);

  const loadDocuments = useCallback(
    async (nextDirection: DocumentDirection) => {
      const result = await api.getDocuments(nextDirection);
      setDocuments(result.documents);
    },
    [api],
  );

  useEffect(() => {
    if (view !== "counterparties" && view !== "compose") return;
    let active = true;
    setLoading(true);
    setError("");
    loadCounterparties()
      .catch((reason) => {
        if (active) setError(errorText(reason));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [loadCounterparties, view]);

  useEffect(() => {
    if (view !== "list") return;
    let active = true;
    setLoading(true);
    setError("");
    loadDocuments(direction)
      .catch((reason) => {
        if (active) setError(errorText(reason));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [direction, loadDocuments, view]);

  function clearMessage() {
    setError("");
    setNotice("");
  }

  function openList(nextDirection: DocumentDirection, keepNotice = false) {
    if (!keepNotice) clearMessage();
    setDirection(nextDirection);
    setDocuments([]);
    setView("list");
  }

  function openCompose(nextDirection: DocumentDirection = "ichki") {
    clearMessage();
    setCompose({
      direction: nextDirection,
      doc_type: DOCUMENT_TYPES[nextDirection][0] ?? "Erkin shakldagi hujjat",
      title: "",
      number: "",
      doc_date: today(),
      contractor_id: null,
      body: "",
    });
    setFirmName(profile.name);
    setDirector(profile.director);
    setTaxId(profile.tax_id);
    setView("compose");
  }

  function openCounterparty(row?: DocumentCounterparty) {
    clearMessage();
    setCounterparty(row ?? null);
    setCounterpartyForm(
      row
        ? {
            name: row.name,
            ctype: row.ctype,
            director: row.director,
            phone: row.phone,
            address: row.address,
            inn: row.inn,
            account: row.account,
            bank: row.bank,
            mfo: row.mfo,
            note: row.note,
          }
        : { ...EMPTY_COUNTERPARTY },
    );
    setView("counterparty-form");
  }

  async function saveProfile() {
    clearMessage();
    if (profileForm.tax_id && profileForm.tax_id.replace(/\D/g, "").length < 9) {
      setError("STIR raqamini to'g'ri kiriting (kamida 9 raqam).");
      return;
    }
    setBusy(true);
    try {
      const updated = await api.updateBusinessProfile(profileForm);
      onProfile(updated);
      setNotice("Hujjat ma'lumotlari saqlandi ✅");
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function saveCounterparty() {
    clearMessage();
    if (!counterpartyForm.name.trim()) {
      setError("Kontragent nomini kiriting.");
      return;
    }
    setBusy(true);
    try {
      if (counterparty) {
        await api.updateDocumentCounterparty(counterparty.id, counterpartyForm);
        setNotice("Saqlandi ✅");
      } else {
        await api.createDocumentCounterparty(counterpartyForm);
        setNotice("Qo'shildi ✅");
      }
      await loadCounterparties();
      setView("counterparties");
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function removeCounterparty() {
    if (!counterparty || !window.confirm("Bu kontragent o'chirilsinmi?")) return;
    clearMessage();
    setBusy(true);
    try {
      await api.deleteDocumentCounterparty(counterparty.id);
      await loadCounterparties();
      setNotice("O'chirildi");
      setView("counterparties");
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  function changeComposeDirection(nextDirection: DocumentDirection) {
    setCompose((current) => ({
      ...current,
      direction: nextDirection,
      doc_type: DOCUMENT_TYPES[nextDirection][0] ?? "Erkin shakldagi hujjat",
      contractor_id: nextDirection === "chiquvchi" ? current.contractor_id : null,
    }));
  }

  function generateTemplate() {
    clearMessage();
    if (
      compose.body.trim() &&
      !window.confirm("Matn maydonida yozuv bor. Shablon bilan almashtirilsinmi?")
    )
      return;
    setCompose((current) => ({
      ...current,
      body: generateDocumentTemplate(current.doc_type, {
        firm: firmName,
        director,
        date: current.doc_date,
        number: current.number,
        title: current.title,
        taxId,
        counterparty: selectedCounterparty,
      }),
    }));
  }

  async function saveNewDocument() {
    clearMessage();
    if (!compose.body.trim()) {
      setError("Avval shablonni yuklang va matnni to'ldiring.");
      return;
    }
    setBusy(true);
    try {
      await api.createDocument(compose);
      setNotice("Hujjat saqlandi ✅");
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function openDocument(row: BusinessDocument) {
    clearMessage();
    setLoading(true);
    try {
      const detail = await api.getDocument(row.id);
      setSelected(detail);
      setReceiverInn(detail.receiver_inn);
      setView("document");
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setLoading(false);
    }
  }

  async function saveSelected() {
    if (!selected) return;
    clearMessage();
    if (!selected.body.trim()) {
      setError("Matn bo'sh bo'lishi mumkin emas.");
      return;
    }
    setBusy(true);
    try {
      const body: BusinessDocumentWrite = {
        direction: selected.direction,
        doc_type: selected.doc_type,
        title: selected.title,
        number: selected.number,
        doc_date: selected.doc_date,
        contractor_id: selected.contractor_id,
        body: selected.body,
      };
      await api.updateDocument(selected.id, body);
      setNotice("Saqlandi ✅");
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function removeSelected() {
    if (!selected || !window.confirm("Bu hujjat o'chirilsinmi?")) return;
    clearMessage();
    setBusy(true);
    try {
      await api.deleteDocument(selected.id);
      setNotice("O'chirildi");
      openList(selected.direction === "chiquvchi" ? "chiquvchi" : "ichki", true);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function sendSelected() {
    if (!selected) return;
    clearMessage();
    if (receiverInn.replace(/\D/g, "").length < 9) {
      setError("STIR raqamini to'g'ri kiriting (kamida 9 raqam).");
      return;
    }
    if (!window.confirm(`Hujjat STIR ${receiverInn} raqamli firmaga yuborilsinmi?`)) {
      return;
    }
    setBusy(true);
    try {
      const result = await api.sendDocument(selected.id, receiverInn);
      setNotice(`Yuborildi ✅ (${result.receiver_name || "firma"})`);
      openList("chiquvchi", true);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function respond(action: "qabul" | "rad") {
    if (!selected) return;
    if (action === "rad" && !window.confirm("Hujjat rad etilsinmi?")) return;
    clearMessage();
    setBusy(true);
    try {
      await api.respondDocument(selected.id, action);
      setNotice(action === "qabul" ? "Qabul qilindi ✅" : "Rad etildi");
      openList("kiruvchi", true);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function copy(value: string) {
    clearMessage();
    if (!value.trim()) {
      setError("Matn bo'sh.");
      return;
    }
    try {
      await copyText(value);
      setNotice("Nusxa olindi ✅");
    } catch {
      setError("Nusxa olib bo‘lmadi.");
    }
  }

  const feedback = (
    <>
      {error ? (
        <p className="documents-v1656__error" role="alert">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p className="documents-v1656__notice" role="status">
          {notice}
        </p>
      ) : null}
    </>
  );

  if (view === "profile") {
    return (
      <main className="documents-v1656">
        <ScreenHeader title="Mening hujjatlarim" onBack={onBack} />
        <section className="documents-v1656__form">
          <p className="documents-v1656__info">
            Bu ma'lumotlar shartnoma, dalolatnoma, hisob va boshqa rasmiy hujjatlarda
            avtomatik ishlatiladi.
          </p>
          <label>
            Rahbar F.I.Sh.
            <input
              value={profileForm.director}
              placeholder="Masalan: Aliyev Vali Akramovich"
              onChange={(event) =>
                setProfileForm((current) => ({
                  ...current,
                  director: event.target.value,
                }))
              }
            />
          </label>
          <label>
            STIR (INN)
            <input
              value={profileForm.tax_id}
              inputMode="numeric"
              maxLength={20}
              placeholder="9 xonali soliq raqami"
              onChange={(event) =>
                setProfileForm((current) => ({
                  ...current,
                  tax_id: event.target.value,
                }))
              }
            />
          </label>
          {feedback}
          <button
            type="button"
            className="documents-v1656__primary"
            disabled={busy}
            onClick={saveProfile}
          >
            Saqlash
          </button>
        </section>
      </main>
    );
  }

  if (view === "center") {
    const cards: Array<{
      icon: string;
      title: string;
      text: string;
      action: () => void;
    }> = [
      {
        icon: "🤝",
        title: "Kontragentlar",
        text: "Hamkorlar bazasi",
        action: () => setView("counterparties"),
      },
      {
        icon: "📥",
        title: "Kiruvchi",
        text: "Kelgan hujjatlar",
        action: () => openList("kiruvchi"),
      },
      {
        icon: "📤",
        title: "Chiquvchi",
        text: "Yuborilgan hujjatlar",
        action: () => openList("chiquvchi"),
      },
      {
        icon: "📋",
        title: "Ichki",
        text: "Firma ichki hujjatlari",
        action: () => openList("ichki"),
      },
      {
        icon: "✍️",
        title: "Hujjat yaratish",
        text: "Tayyor shablon asosida",
        action: () => openCompose(),
      },
    ];
    return (
      <main className="documents-v1656">
        <ScreenHeader title="Hujjatlar" onBack={onBack} />
        <section className="documents-v1656__menu">
          {cards.map((card) => (
            <button type="button" key={card.title} onClick={card.action}>
              <span>{card.icon}</span>
              <span>
                <b>{card.title}</b>
                <small>{card.text}</small>
              </span>
              <span aria-hidden="true">›</span>
            </button>
          ))}
        </section>
      </main>
    );
  }

  if (view === "counterparties") {
    return (
      <main className="documents-v1656">
        <ScreenHeader title="Kontragentlar" onBack={() => setView("center")} />
        <section className="documents-v1656__total">
          <small>Kontragentlar</small>
          <strong>{counterparties.length}</strong>
        </section>
        {canManageCounterparties ? (
          <button
            type="button"
            className="documents-v1656__primary"
            onClick={() => openCounterparty()}
          >
            + Kontragent qo'shish
          </button>
        ) : null}
        {feedback}
        {loading ? <p>Yuklanmoqda...</p> : null}
        {!loading && !counterparties.length ? (
          <p className="documents-v1656__empty">
            Hozircha kontragent yo'q. "+ Kontragent qo'shish" bilan qo'shing.
          </p>
        ) : null}
        <section className="documents-v1656__list">
          {counterparties.map((row) => {
            const content = (
              <>
                <b>{row.name}</b>
                {row.ctype || row.phone ? (
                  <small>{[row.ctype, row.phone].filter(Boolean).join(" · ")}</small>
                ) : null}
                {row.director ? <small>Rahbar: {row.director}</small> : null}
                {row.inn || row.account ? (
                  <small>
                    {[
                      row.inn ? `STIR: ${row.inn}` : "",
                      row.account ? `h/r: ${row.account}` : "",
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </small>
                ) : null}
                {row.bank ? (
                  <small>
                    {row.bank}
                    {row.mfo ? ` (MFO ${row.mfo})` : ""}
                  </small>
                ) : null}
              </>
            );
            return canManageCounterparties ? (
              <button type="button" key={row.id} onClick={() => openCounterparty(row)}>
                {content}
              </button>
            ) : (
              <article key={row.id}>{content}</article>
            );
          })}
        </section>
      </main>
    );
  }

  if (view === "counterparty-form") {
    const fields: Array<{
      key: keyof DocumentCounterpartyWrite;
      label: string;
      placeholder: string;
      inputMode?: "numeric" | "tel";
    }> = [
      {
        key: "name",
        label: "Nomi (firma yoki shaxs)",
        placeholder: "Masalan: Olma Savdo MChJ",
      },
      { key: "director", label: "Rahbari", placeholder: "Ism-familiya" },
      { key: "phone", label: "Telefon", placeholder: "+998 ...", inputMode: "tel" },
      { key: "address", label: "Manzil", placeholder: "Viloyat, tuman, ko'cha" },
      {
        key: "inn",
        label: "STIR (INN)",
        placeholder: "9 xonali",
        inputMode: "numeric",
      },
      {
        key: "account",
        label: "Hisob raqami",
        placeholder: "20208...",
        inputMode: "numeric",
      },
      { key: "bank", label: "Bank nomi", placeholder: "Masalan: Ipoteka Bank" },
      { key: "mfo", label: "MFO kodi", placeholder: "5 xonali", inputMode: "numeric" },
      { key: "note", label: "Izoh", placeholder: "Ixtiyoriy" },
    ];
    return (
      <main className="documents-v1656">
        <ScreenHeader title="Kontragent" onBack={() => setView("counterparties")} />
        <section className="documents-v1656__form">
          <label>
            Nomi (firma yoki shaxs)
            <input
              value={counterpartyForm.name}
              placeholder="Masalan: Olma Savdo MChJ"
              onChange={(event) =>
                setCounterpartyForm((current) => ({
                  ...current,
                  name: event.target.value,
                }))
              }
            />
          </label>
          <label>
            Turi
            <select
              value={counterpartyForm.ctype}
              onChange={(event) =>
                setCounterpartyForm((current) => ({
                  ...current,
                  ctype: event.target.value,
                }))
              }
            >
              {counterpartyTypes.map((type) => (
                <option key={type}>{type}</option>
              ))}
            </select>
          </label>
          {fields
            .filter((field) => field.key !== "name")
            .map((field) => (
              <label key={field.key}>
                {field.label}
                <input
                  value={counterpartyForm[field.key]}
                  inputMode={field.inputMode}
                  placeholder={field.placeholder}
                  onChange={(event) =>
                    setCounterpartyForm((current) => ({
                      ...current,
                      [field.key]: event.target.value,
                    }))
                  }
                />
              </label>
            ))}
          {feedback}
          <button
            type="button"
            className="documents-v1656__primary"
            disabled={busy}
            onClick={saveCounterparty}
          >
            Saqlash
          </button>
          {counterparty ? (
            <button
              type="button"
              className="documents-v1656__soft"
              disabled={busy}
              onClick={removeCounterparty}
            >
              O'chirish
            </button>
          ) : null}
        </section>
      </main>
    );
  }

  if (view === "compose") {
    return (
      <main className="documents-v1656">
        <ScreenHeader title="Hujjat yaratish" onBack={() => setView("center")} />
        <section className="documents-v1656__form">
          <label>
            1. Yo'nalish
            <select
              value={compose.direction}
              onChange={(event) =>
                changeComposeDirection(event.target.value as DocumentDirection)
              }
            >
              <option value="ichki">📋 Ichki hujjat</option>
              <option value="chiquvchi">📤 Chiquvchi hujjat</option>
              <option value="kiruvchi">📥 Kiruvchi hujjat</option>
            </select>
          </label>
          <label>
            2. Hujjat turi
            <select
              value={compose.doc_type}
              onChange={(event) =>
                setCompose((current) => ({ ...current, doc_type: event.target.value }))
              }
            >
              {DOCUMENT_TYPES[compose.direction].map((type) => (
                <option key={type}>{type}</option>
              ))}
            </select>
          </label>
          <label>
            Sarlavha (ixtiyoriy)
            <input
              value={compose.title}
              placeholder="Masalan: Ta'til to'g'risida"
              onChange={(event) =>
                setCompose((current) => ({ ...current, title: event.target.value }))
              }
            />
          </label>
          <div className="documents-v1656__pair">
            <label>
              Raqami
              <input
                value={compose.number}
                placeholder="№"
                onChange={(event) =>
                  setCompose((current) => ({ ...current, number: event.target.value }))
                }
              />
            </label>
            <label>
              Sana
              <input
                type="date"
                value={compose.doc_date}
                onChange={(event) =>
                  setCompose((current) => ({
                    ...current,
                    doc_date: event.target.value,
                  }))
                }
              />
            </label>
          </div>
          <label>
            Firma nomi
            <input
              value={firmName}
              placeholder="Firma nomi"
              onChange={(event) => setFirmName(event.target.value)}
            />
          </label>
          <label>
            Rahbar F.I.Sh.
            <input
              value={director}
              placeholder="Rahbar"
              onChange={(event) => setDirector(event.target.value)}
            />
          </label>
          <label>
            Firma STIR (INN)
            <input
              value={taxId}
              inputMode="numeric"
              placeholder="9 xonali"
              onChange={(event) => setTaxId(event.target.value)}
            />
          </label>
          {compose.direction === "chiquvchi" ? (
            <label>
              Kontragent (kimga)
              <select
                value={compose.contractor_id ?? 0}
                onChange={(event) =>
                  setCompose((current) => ({
                    ...current,
                    contractor_id: Number(event.target.value) || null,
                  }))
                }
              >
                <option value={0}>— tanlanmagan —</option>
                {counterparties.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <button
            type="button"
            className="documents-v1656__soft"
            onClick={generateTemplate}
          >
            📄 Shablonni yuklash
          </button>
          <label>
            Hujjat matni
            <textarea
              rows={16}
              value={compose.body}
              placeholder="Yuqoridan tur tanlab «Shablonni yuklash» tugmasini bosing — tayyor andoza shu yerga chiqadi. So'ng to'ldiring."
              onChange={(event) =>
                setCompose((current) => ({ ...current, body: event.target.value }))
              }
            />
          </label>
          {feedback}
          <button
            type="button"
            className="documents-v1656__primary"
            disabled={busy}
            onClick={saveNewDocument}
          >
            💾 Hujjatni saqlash
          </button>
          <button
            type="button"
            className="documents-v1656__soft"
            onClick={() => copy(compose.body)}
          >
            📋 Nusxa olish
          </button>
        </section>
      </main>
    );
  }

  if (view === "list") {
    const title =
      direction === "kiruvchi"
        ? "Kiruvchi hujjatlar"
        : direction === "chiquvchi"
          ? "Chiquvchi hujjatlar"
          : "Ichki hujjatlar";
    return (
      <main className="documents-v1656">
        <ScreenHeader title={title} onBack={() => setView("center")} />
        {direction !== "kiruvchi" ? (
          <button
            type="button"
            className="documents-v1656__primary"
            onClick={() => openCompose(direction)}
          >
            + Yangi {direction === "ichki" ? "ichki" : "chiquvchi"} hujjat
          </button>
        ) : null}
        {feedback}
        {loading ? <p>Yuklanmoqda...</p> : null}
        {!loading && !documents.length ? (
          <p className="documents-v1656__empty">
            {direction === "kiruvchi"
              ? "Kiruvchi hujjat yo'q. Boshqa firmalar sizning STIR raqamingizga hujjat yuborsa, shu yerda ko'rinadi."
              : 'Hozircha hujjat yo\'q. "+ Yangi" bilan yarating.'}
          </p>
        ) : null}
        <section className="documents-v1656__list">
          {documents.map((row) => (
            <button type="button" key={row.id} onClick={() => openDocument(row)}>
              <b>
                {row.doc_type || "Hujjat"}
                {row.title ? ` — ${row.title}` : ""}
              </b>
              {direction === "kiruvchi" ? (
                <small>Yuboruvchi: {row.sender_name || "?"}</small>
              ) : null}
              <small>
                {[
                  row.number ? `№ ${row.number}` : "",
                  row.doc_date,
                  row.contractor_name,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </small>
              {row.status ? <StatusBadge status={row.status} /> : null}
              {direction !== "kiruvchi" && preview(row.body) ? (
                <small className="documents-v1656__preview">
                  {preview(row.body)}...
                </small>
              ) : null}
            </button>
          ))}
        </section>
      </main>
    );
  }

  if (!selected) {
    return (
      <main className="documents-v1656">
        <ScreenHeader title="Hujjat" onBack={() => openList(direction)} />
        {feedback}
      </main>
    );
  }

  const incoming = selected.direction === "kiruvchi";
  return (
    <main className="documents-v1656">
      <ScreenHeader title="Hujjat" onBack={() => openList(selected.direction)} />
      <section className="documents-v1656__document-head">
        <b>
          {selected.doc_type || "Hujjat"}
          {selected.title ? ` — ${selected.title}` : ""}
        </b>
        <small>
          {incoming
            ? `Kiruvchi · Yuboruvchi: ${selected.sender_name || "?"}`
            : DIRECTION_TEXT[selected.direction]}
          {selected.number ? ` · № ${selected.number}` : ""}
          {selected.doc_date ? ` · ${selected.doc_date}` : ""}
          {selected.contractor_name ? ` · ${selected.contractor_name}` : ""}
        </small>
        <StatusBadge status={selected.status} />
      </section>
      <textarea
        className="documents-v1656__body"
        rows={16}
        readOnly={incoming}
        aria-label="Hujjat matni"
        value={selected.body}
        onChange={(event) => setSelected({ ...selected, body: event.target.value })}
      />
      {selected.direction === "chiquvchi" ? (
        <section className="documents-v1656__send">
          <b>📤 Boshqa firmaga yuborish</b>
          <small>
            Qabul qiluvchi firmaning STIR (INN) raqamini kiriting. Hujjat unda
            «Kiruvchi» bo'lib ko'rinadi.
          </small>
          <div>
            <input
              aria-label="Qabul qiluvchi STIR"
              value={receiverInn}
              inputMode="numeric"
              placeholder="STIR (9 xonali)"
              onChange={(event) => setReceiverInn(event.target.value)}
            />
            <button type="button" disabled={busy} onClick={sendSelected}>
              Yuborish
            </button>
          </div>
          {selected.status ? (
            <small>
              Holat: <StatusBadge status={selected.status} />
            </small>
          ) : null}
        </section>
      ) : null}
      {feedback}
      {!incoming ? (
        <>
          <button
            type="button"
            className="documents-v1656__primary"
            disabled={busy}
            onClick={saveSelected}
          >
            💾 O'zgarishni saqlash
          </button>
          <button
            type="button"
            className="documents-v1656__soft"
            onClick={() => copy(selected.body)}
          >
            📋 Nusxa olish
          </button>
          <button
            type="button"
            className="documents-v1656__soft documents-v1656__danger"
            disabled={busy}
            onClick={removeSelected}
          >
            🗑️ O'chirish
          </button>
        </>
      ) : (
        <>
          <button
            type="button"
            className="documents-v1656__soft"
            onClick={() => copy(selected.body)}
          >
            📋 Nusxa olish
          </button>
          {selected.status === "kutilmoqda" ? (
            <section className="documents-v1656__actions">
              <button
                type="button"
                className="documents-v1656__primary"
                disabled={busy}
                onClick={() => respond("qabul")}
              >
                ✅ Qabul qilish
              </button>
              <button
                type="button"
                className="documents-v1656__soft documents-v1656__danger"
                disabled={busy}
                onClick={() => respond("rad")}
              >
                ❌ Rad etish
              </button>
            </section>
          ) : null}
        </>
      )}
    </main>
  );
}
