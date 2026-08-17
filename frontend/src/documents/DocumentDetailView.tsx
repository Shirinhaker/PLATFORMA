import {
  DIRECTION_TEXT,
  DocumentsFeedback,
  ScreenHeader,
  StatusBadge,
} from "./DocumentsShared";
import type { DocumentsController } from "./useDocumentsController";

export function DocumentDetailView({
  controller,
}: {
  controller: DocumentsController;
}) {
  const {
    busy,
    copy,
    direction,
    error,
    notice,
    openList,
    receiverInn,
    removeSelected,
    respond,
    saveSelected,
    selected,
    sendSelected,
    setReceiverInn,
    setSelected,
  } = controller;

  if (!selected) {
    return (
      <main className="documents-v1656">
        <ScreenHeader title="Hujjat" onBack={() => openList(direction)} />
        <DocumentsFeedback error={error} notice={notice} />
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
      <DocumentsFeedback error={error} notice={notice} />
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
