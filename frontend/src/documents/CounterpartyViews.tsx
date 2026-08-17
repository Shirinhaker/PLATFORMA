import type { DocumentCounterpartyWrite } from "../api/types";
import { DocumentsFeedback, ScreenHeader } from "./DocumentsShared";
import type { DocumentsController } from "./useDocumentsController";

type ViewProps = {
  controller: DocumentsController;
};

export function CounterpartyListView({ controller }: ViewProps) {
  const {
    canManageCounterparties,
    counterparties,
    error,
    loading,
    notice,
    openCounterparty,
    setView,
  } = controller;

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
      <DocumentsFeedback error={error} notice={notice} />
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

export function CounterpartyFormView({ controller }: ViewProps) {
  const {
    busy,
    counterparty,
    counterpartyForm,
    counterpartyTypes,
    error,
    notice,
    removeCounterparty,
    saveCounterparty,
    setCounterpartyForm,
    setView,
  } = controller;
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
        <DocumentsFeedback error={error} notice={notice} />
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
