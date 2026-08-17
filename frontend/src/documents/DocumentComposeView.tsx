import type { DocumentDirection } from "../api/types";
import { DocumentsFeedback, ScreenHeader } from "./DocumentsShared";
import { DOCUMENT_TYPES } from "./templates";
import type { DocumentsController } from "./useDocumentsController";

export function DocumentComposeView({
  controller,
}: {
  controller: DocumentsController;
}) {
  const {
    busy,
    changeComposeDirection,
    compose,
    copy,
    counterparties,
    director,
    error,
    firmName,
    generateTemplate,
    notice,
    saveNewDocument,
    setCompose,
    setDirector,
    setFirmName,
    setTaxId,
    setView,
    taxId,
  } = controller;

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
        <DocumentsFeedback error={error} notice={notice} />
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
