import { useState } from "react";

import type { ApiClient } from "../api/client";
import type { SessionIdentity } from "../api/types";
import "./AccountSettings.css";


export type AccountSettingsApi = Pick<
  ApiClient,
  "getBusinessCredentials" | "updateBusinessCredentials"
>;

type SettingsApi = Partial<AccountSettingsApi>;
type SettingsScreen = "settings" | "credentials" | "help";

type Props = {
  api: SettingsApi;
  identity: SessionIdentity;
  onBack: () => void;
  onNotifications?: () => void;
  onLogout: () => void | Promise<void>;
  canManageBusinessCredentials?: boolean;
};

const FAQ_ITEMS = [
  {
    q: "Do'konimni qanday ochaman?",
    a: "Pastdagi menyudan \"Kabinet\" — \"Biznes ochish\" tugmasini bosing. Do'kon nomi, turi, manzilini kiriting. Ochilgach sizga firma login va parol beriladi — ularni saqlab qo'ying.",
  },
  {
    q: "Mahsulot qanday qo'shaman?",
    a: "Do'kon kabinetida \"Mahsulotlar\" bo'limiga kiring — \"+ Yangi\" tugmasi orqali nom, narx, o'lchov birligi va rasm qo'shing. Ombordagi qoldiqni ham shu yerda boshqarasiz.",
  },
  {
    q: "Buyurtmani qanday qabul qilaman?",
    a: "\"Buyurtmalar\" bo'limida yangi buyurtmalar ko'rinadi. \"Qabul qilish\" bosing, tayyor bo'lgach — yetkazib berish bo'lsa \"Tayyor bo'ldi\", so'ng \"Yakunlash\" tugmasini bosing.",
  },
  {
    q: "\"Tayyor bo'ldi\" nima qiladi?",
    a: "Yetkazib berish buyurtmasida \"Tayyor bo'ldi\" bosilganda, tizim avtomatik dostavka e'lonini beradi — dostavka haydovchilari do'koningizdan mijozgacha yetkazish uchun buyurtmani ko'radi va oladi.",
  },
  {
    q: "Xodimga login-parol qanday beraman?",
    a: "Kabinet — \"Ma'muriyat\" — \"Xodimlar\" — xodimni oching — \"Ilovaga kirish huquqi\"ni yoqing. Login-parol va ruxsat bo'limlarini (Kassa/Ombor/Buyurtma) belgilang. Xodimga firma logini, o'z logini va parolini bering.",
  },
  {
    q: "Xodim qanday kiradi?",
    a: "Kirish sahifasida \"Xodimlar uchun kirish\" tugmasini bossin. So'ng firma logini, o'z logini va parolini kiritib kiradi — faqat siz belgilagan bo'limlarni ko'radi.",
  },
  {
    q: "Do'kon login yoki parolini unutdim / o'zgartirmoqchiman",
    a: "Do'kon kabineti — \"Sozlamalar\" — \"Login va parol\" bo'limida firma loginini ko'rasiz va yangi login/parol o'rnatasiz.",
  },
  {
    q: "Mutaxassis bo'lib qanday ro'yxatdan o'taman?",
    a: "\"Kabinet\" — \"Mutaxasisligim\" bo'limiga kiring. Kasbingiz, narx va ma'lumotlarni to'ldiring, xaritada joylashuvingizni belgilang va \"Ko'rinaman\"ni yoqing. Shundan so'ng qidiruvda va xaritada chiqasiz.",
  },
  {
    q: "Taxi yoki dostavkani qanday chaqiraman?",
    a: "Bosh sahifadagi taxi tugmasini bosing. Qayerdan-qayerga, yuk turini kiriting va chaqiring. Yaqin haydovchilar buyurtmangizni ko'radi.",
  },
  {
    q: "Haydovchi bo'lib qanday ishlayman?",
    a: "Haydovchi kabinetiga kiring, xizmat turini (taxi/dostavka) tanlang va \"Bo'shman\" holatiga o'ting. Buyurtma kelganda qabul qiling — qabul qilgach avtomatik \"Bandman\" bo'lasiz, yakunlagach yana bo'sh.",
  },
  {
    q: "Baho va fikrni qanday qoldiraman?",
    a: "Do'kon yoki mutaxassis sahifasining pastida \"Baholar va fikrlar\" bo'limi bor. Faqat o'sha yerdan buyurtma bergan/xarid qilganlar yulduz (1-5) va izoh qoldira oladi.",
  },
  {
    q: "To'lov qanday ishlaydi?",
    a: "Do'kon o'z to'lov kartasini profilga qo'shsa, mijoz buyurtma berayotganda karta ma'lumotini ko'radi va o'zaro kelishuv asosida to'laydi. Onlayn to'lov tizimi keyingi bosqichda ulanadi.",
  },
  {
    q: "Havola (link) va QR nima uchun?",
    a: "Do'kon profilida havola va QR kod bor. Ularni ulashsangiz, boshqalar to'g'ridan-to'g'ri do'koningiz sahifasini ochadi.",
  },
  {
    q: "Qarz daftari nima?",
    a: "Kassada qarzga sotilgan savdolar \"Qarz daftari\"da saqlanadi. Kim, qancha qarzdorligini ko'rasiz va to'lov qilinganda belgilaysiz.",
  },
] as const;

function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

function supportsCredentials(api: SettingsApi): api is AccountSettingsApi {
  return typeof api.getBusinessCredentials === "function"
    && typeof api.updateBusinessCredentials === "function";
}

function Chevron() {
  return <span className="account-settings-modular__chevron" aria-hidden="true">›</span>;
}

export function AccountSettings({
  api,
  identity,
  onBack,
  onNotifications,
  onLogout,
  canManageBusinessCredentials,
}: Props) {
  const [screen, setScreen] = useState<SettingsScreen>("settings");
  const [login, setLogin] = useState(identity.login);
  const [newLogin, setNewLogin] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [repeatPassword, setRepeatPassword] = useState("");
  const [openFaqs, setOpenFaqs] = useState<Set<number>>(() => new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const owner = (canManageBusinessCredentials
    ?? identity.account_type === "business")
    && identity.actor_type !== "staff";

  function back() {
    setError("");
    setNotice("");
    if (screen === "settings") onBack();
    else setScreen("settings");
  }

  async function openCredentials() {
    setScreen("credentials");
    setError("");
    setNotice("");
    setNewLogin("");
    setNewPassword("");
    setRepeatPassword("");
    if (!owner || !supportsCredentials(api)) {
      setLogin("—");
      setNotice("Bu bo'lim do'kon egalari uchun.");
      return;
    }
    setBusy(true);
    try {
      const value = await api.getBusinessCredentials();
      setLogin(value.login);
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  async function saveCredentials(event: React.FormEvent) {
    event.preventDefault();
    const normalizedLogin = newLogin.trim().toLowerCase();
    const password = newPassword.trim();
    setError("");
    setNotice("");
    if (!normalizedLogin && !password) {
      setError("Yangi login yoki parol kiriting.");
      return;
    }
    if (password && password !== repeatPassword.trim()) {
      setError("Parollar mos kelmadi.");
      return;
    }
    if (!owner || !supportsCredentials(api)) {
      setError("Bu bo'lim do'kon egalari uchun.");
      return;
    }
    setBusy(true);
    try {
      const value = await api.updateBusinessCredentials({
        new_login: normalizedLogin,
        new_password: password,
      });
      setLogin(value.login);
      setNewLogin("");
      setNewPassword("");
      setRepeatPassword("");
      setNotice("Saqlandi ✅");
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  if (screen === "credentials") {
    return (
      <main className="account-settings-modular">
        <header className="account-settings-modular__topbar">
          <button type="button" aria-label="Sozlamalarga qaytish" onClick={back}>‹</button>
          <h1>Login va parol</h1>
        </header>
        <form className="account-settings-modular__form" onSubmit={saveCredentials}>
          <section className="account-settings-modular__login-card">
            <b>🏪 Firma logini</b>
            <strong>{busy ? "Yuklanmoqda…" : login || "—"}</strong>
            <p>
              Bu login va parol bilan boshqa qurilmadan ham do'kon kabinetiga
              kirasiz. Xodimlaringiz ham shu <b>firma logini</b>ni ishlatadi.
            </p>
          </section>
          <label>
            <span>Yangi login <small>(o'zgartirmoqchi bo'lsangiz)</small></span>
            <input
              autoComplete="off"
              placeholder="masalan: anvardokon"
              value={newLogin}
              disabled={busy || !owner}
              onChange={(event) => setNewLogin(
                event.currentTarget.value.toLowerCase().replace(/[^a-z0-9_]/g, ""),
              )}
            />
          </label>
          <label>
            <span>Yangi parol</span>
            <input
              type="password"
              autoComplete="new-password"
              placeholder="kamida 4 belgi (bo'sh qoldirsangiz o'zgarmaydi)"
              value={newPassword}
              disabled={busy || !owner}
              onChange={(event) => setNewPassword(event.currentTarget.value)}
            />
          </label>
          <label>
            <span>Yangi parolni takrorlang</span>
            <input
              type="password"
              autoComplete="new-password"
              placeholder="parolni yana kiriting"
              value={repeatPassword}
              disabled={busy || !owner}
              onChange={(event) => setRepeatPassword(event.currentTarget.value)}
            />
          </label>
          <p className="account-settings-modular__warning">
            ⚠️ Loginni o'zgartirsangiz, xodimlaringizga yangi firma loginini ayting.
          </p>
          {error && <p className="account-settings-modular__error" role="alert">{error}</p>}
          {notice && <p className="account-settings-modular__notice" role="status">{notice}</p>}
          <button
            type="submit"
            className="account-settings-modular__save"
            disabled={busy || !owner}
          >
            Saqlash
          </button>
        </form>
      </main>
    );
  }

  if (screen === "help") {
    return (
      <main className="account-settings-modular account-settings-modular--help">
        <header className="account-settings-modular__topbar">
          <button type="button" aria-label="Sozlamalarga qaytish" onClick={back}>‹</button>
          <h1>Yordam</h1>
        </header>
        <section className="account-settings-modular__faq-list">
          <p>Ko'p so'raladigan savollar. Savol ustiga bosing — javobi ochiladi.</p>
          {FAQ_ITEMS.map((item, index) => {
            const open = openFaqs.has(index);
            return (
              <article key={item.q} className="account-settings-modular__faq">
                <button
                  type="button"
                  aria-expanded={open}
                  onClick={() => setOpenFaqs((current) => {
                    const next = new Set(current);
                    if (next.has(index)) next.delete(index);
                    else next.add(index);
                    return next;
                  })}
                >
                  <b>{item.q}</b>
                  <span aria-hidden="true">▾</span>
                </button>
                {open && <p>{item.a}</p>}
              </article>
            );
          })}
        </section>
      </main>
    );
  }

  return (
    <main className="account-settings-modular">
      <header className="account-settings-modular__topbar">
        <button type="button" aria-label="Kabinetga qaytish" onClick={back}>‹</button>
        <h1>Sozlamalar</h1>
      </header>
      <section className="account-settings-modular__rows">
        <button type="button" onClick={() => void openCredentials()}>
          <span>🔑 Login va parol</span><Chevron />
        </button>
        <button type="button" onClick={() => window.alert("Til tanlash (namuna).") }>
          <span>🌐 Til — O'zbekcha</span><Chevron />
        </button>
        <button
          type="button"
          onClick={() => {
            if (onNotifications) onNotifications();
            else setNotice("Bildirishnomalar hozircha mavjud emas.");
          }}
        >
          <span>🔔 Bildirishnomalar</span><Chevron />
        </button>
        <button type="button" onClick={() => setScreen("help")}>
          <span>🆘 Yordam</span><Chevron />
        </button>
        <button
          type="button"
          className="account-settings-modular__danger"
          disabled={busy}
          onClick={() => void onLogout()}
        >
          <span>🚪 Tizimdan chiqish</span>
        </button>
        {notice && <p className="account-settings-modular__notice" role="status">{notice}</p>}
      </section>
    </main>
  );
}
