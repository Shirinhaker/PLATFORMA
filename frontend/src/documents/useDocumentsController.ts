import { useCallback, useEffect, useMemo, useState } from "react";

import type {
  BusinessDocument,
  BusinessDocumentWrite,
  DocumentCounterparty,
  DocumentCounterpartyWrite,
  DocumentDirection,
} from "../api/types";
import {
  copyText,
  EMPTY_COUNTERPARTY,
  errorText,
  today,
  type DocumentsProps,
  type DocumentsView,
} from "./DocumentsShared";
import { DOCUMENT_TYPES, generateDocumentTemplate } from "./templates";

export function useDocumentsController({
  api,
  profile,
  initialView,
  canManageCounterparties,
  onProfile,
  onBack,
}: DocumentsProps) {
  const [view, setView] = useState<DocumentsView>(initialView);
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

  return {
    view,
    setView,
    direction,
    counterparties,
    counterpartyTypes,
    counterparty,
    counterpartyForm,
    setCounterpartyForm,
    documents,
    selected,
    setSelected,
    profileForm,
    setProfileForm,
    compose,
    setCompose,
    firmName,
    setFirmName,
    director,
    setDirector,
    taxId,
    setTaxId,
    receiverInn,
    setReceiverInn,
    loading,
    busy,
    error,
    notice,
    canManageCounterparties,
    onBack,
    openList,
    openCompose,
    openCounterparty,
    saveProfile,
    saveCounterparty,
    removeCounterparty,
    changeComposeDirection,
    generateTemplate,
    saveNewDocument,
    openDocument,
    saveSelected,
    removeSelected,
    sendSelected,
    respond,
    copy,
  };
}

export type DocumentsController = ReturnType<typeof useDocumentsController>;
