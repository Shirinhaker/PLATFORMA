import { DocumentsFeedback, ScreenHeader } from "./DocumentsShared";
import type { DocumentsController } from "./useDocumentsController";

type ViewProps = {
  controller: DocumentsController;
};

export function ProfileView({ controller }: ViewProps) {
  const { busy, error, notice, onBack, profileForm, saveProfile, setProfileForm } =
    controller;

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
        <DocumentsFeedback error={error} notice={notice} />
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

export function CenterView({ controller }: ViewProps) {
  const { onBack, openCompose, openList, setView } = controller;
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
