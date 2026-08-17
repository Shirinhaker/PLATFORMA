import {
  DocumentsFeedback,
  preview,
  ScreenHeader,
  StatusBadge,
} from "./DocumentsShared";
import type { DocumentsController } from "./useDocumentsController";

export function DocumentListView({ controller }: { controller: DocumentsController }) {
  const {
    direction,
    documents,
    error,
    loading,
    notice,
    openCompose,
    openDocument,
    setView,
  } = controller;
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
      <DocumentsFeedback error={error} notice={notice} />
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
              {[row.number ? `№ ${row.number}` : "", row.doc_date, row.contractor_name]
                .filter(Boolean)
                .join(" · ")}
            </small>
            {row.status ? <StatusBadge status={row.status} /> : null}
            {direction !== "kiruvchi" && preview(row.body) ? (
              <small className="documents-v1656__preview">{preview(row.body)}...</small>
            ) : null}
          </button>
        ))}
      </section>
    </main>
  );
}
