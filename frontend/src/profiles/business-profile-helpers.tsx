import type {
  BusinessProfile as BusinessProfileData,
  CabinetActivity,
  SessionIdentity,
} from "../api/types";
import {
  adaptMenuForDirection,
  isOnlineMenuVisibleForDirection,
  isService,
  type Menu,
  ONLINE_MENUS,
  payloadRows,
} from "./business-profile-config";

export type DataView = { title: string; rows: unknown[] };

export type Screen =
  | "cabinet"
  | "administration"
  | "profile"
  | "data"
  | "online"
  | "staff"
  | "cash"
  | "debt"
  | "expenses"
  | "warehouse"
  | "documents"
  | "ai-assistant"
  | "statistics"
  | "education-management"
  | "education-statistics"
  | "settings";

export const HEADER_ONLINE_VIEWS = new Set(["followers", "following"]);

export const MAIN_ONLINE_ORDER = [
  "profile",
  "subscriptions",
  "payments",
  "items",
  "dining-places",
  "medical-providers",
  "medical-queue",
  "education-enrollments",
  "orders",
  "service-orders",
  "messages",
  "reviews",
  "advertisements",
  "stories",
  "notifications",
] as const;

type MenuHubProps = {
  menus: Menu[];
  onBack: () => void;
  onOpen: (menu: Menu) => void;
};

export function BusinessCabinetMenuHub({ menus, onBack, onOpen }: MenuHubProps) {
  return (
    <main className="business-online business-cabinet-menu-hub">
      <header className="business-online__heading">
        <button type="button" onClick={onBack}>
          ← Kabinetga qaytish
        </button>
        <div>
          <h1>Ma’muriyat</h1>
        </div>
      </header>
      <section
        className="business-cabinet__menu-grid"
        aria-label="Ma’muriyat bo‘limlari"
      >
        {menus.map((menu) => (
          <button type="button" key={menu.view} onClick={() => onOpen(menu)}>
            <span>{menu.icon}</span>
            <span>
              <b>{menu.label}</b>
              <small>{menu.caption}</small>
            </span>
          </button>
        ))}
      </section>
    </main>
  );
}

export function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

export function activeCount(payload: Record<string, unknown>) {
  return payloadRows(payload, "orders").filter((row) => {
    const status = String(record(row).status ?? "");
    return ![
      "done",
      "delivered",
      "cancelled",
      "canceled",
      "rejected",
      "pickup_waiting_customer",
    ].includes(status);
  }).length;
}

export function activityLabel(row: CabinetActivity) {
  return row.kind === "order" ? `Buyurtma #${row.id} — ${row.title}` : row.title;
}

export function menuRows(profile: BusinessProfileData | null, menu: Menu): unknown[] {
  if (!profile || !menu.payload) return [];
  const rows = payloadRows(profile.cabinet_payload, menu.payload);
  if (menu.view === "service-orders") return rows.filter(isService);
  if (menu.view === "orders") return rows.filter((row) => !isService(row));
  if (menu.view === "education-enrollments") {
    return rows.filter((row) => String(record(row).status ?? "") === "new");
  }
  return rows;
}

const MENU_PERMISSIONS: Record<string, readonly string[]> = {
  items: ["items"],
  "dining-places": ["dining_places"],
  "dining-kitchen": ["kitchen"],
  "education-enrollments": ["education_enrollments"],
  "medical-providers": ["service_orders"],
  "medical-queue": ["service_orders"],
  listings: ["ads"],
  orders: ["buyurtma", "dining_internal", "dining_external", "kitchen"],
  "service-orders": ["service_orders"],
  messages: ["chats"],
  reviews: ["reviews"],
  advertisements: ["ads"],
  stories: ["ads"],
  notifications: ["notifications"],
  sales: ["kassa"],
  expenses: ["expenses"],
  subscriptions: [],
  debtors: ["debts"],
  warehouse: ["ombor", "production"],
  statistics: ["statistics"],
  "education-statistics": ["education_statistics"],
  reports: ["reports"],
  "my-documents": [],
  documents: ["documents"],
  "education-groups": ["education_groups"],
  "education-students": ["education_students"],
  "education-schedule": ["education_schedule"],
  "education-attendance": ["education_attendance"],
  "education-payments": ["education_payments"],
  "education-teachers": ["education_teachers"],
  "education-payroll": ["education_payroll"],
};

const OWNER_ONLY_VIEWS = new Set([
  "profile",
  "subscriptions",
  "payments",
  "followers",
  "following",
  "staff",
  "my-documents",
  "settings",
]);

export function canUseView(identity: SessionIdentity, view: string) {
  if (identity.actor_type !== "staff") return true;
  if (OWNER_ONLY_VIEWS.has(view)) return false;
  const required = MENU_PERMISSIONS[view];
  return Boolean(
    required?.some((permission) => (identity.permissions ?? []).includes(permission)),
  );
}

export function visibleMenus(
  profile: BusinessProfileData | null,
  menus: Menu[],
  identity: SessionIdentity,
) {
  if (!profile) return [];
  return menus
    .filter(
      (menu) =>
        canUseView(identity, menu.view) &&
        !menu.excludedDirections?.includes(profile.direction) &&
        (isOnlineMenu(menu)
          ? isOnlineMenuVisibleForDirection(menu, profile.direction)
          : !menu.directions || menu.directions.includes(profile.direction)),
    )
    .map((menu) => adaptMenuForDirection(menu, profile.direction));
}

export function dashboardMenuCards(
  onlineMenus: Menu[],
  systemMenus: Menu[],
  adminMenus: Menu[],
  directionMenus: Menu[],
  staff: boolean,
) {
  const online = MAIN_ONLINE_ORDER.map((view) =>
    onlineMenus.find((menu) => menu.view === view),
  ).filter((menu): menu is Menu => Boolean(menu));
  const systemCard = (view: string, label: string): Menu | null => {
    const menu = systemMenus.find((candidate) => candidate.view === view);
    return menu ? { ...menu, label } : null;
  };
  const base: Array<Menu | null> = [
    systemCard("sales", "Kassa"),
    systemCard("expenses", "Xarajatlar"),
    systemCard("debtors", "Qarz daftari"),
    systemCard("warehouse", "Ombor"),
    systemCard("statistics", "Statistika"),
    systemCard("reports", "Hisobotlar"),
  ];
  const represented = new Set(
    base.filter((menu): menu is Menu => Boolean(menu)).map((menu) => menu.view),
  );
  const system = [
    ...base.filter((menu): menu is Menu => Boolean(menu)),
    ...directionMenus.filter((menu) => !represented.has(menu.view)),
    ...[
      systemCard("ai-assistant", "AI yordamchi"),
      !staff && adminMenus.length
        ? {
            icon: "🛡️",
            label: "Ma'muriyat",
            caption: "Xodimlar va hujjatlar",
            view: "administration",
          }
        : null,
      !staff ? systemCard("settings", "Sozlamalar") : null,
    ].filter((menu): menu is Menu => Boolean(menu)),
  ];
  return { onlineMenuCards: online, systemMenuCards: system };
}

export function isOnlineMenu(menu: Menu) {
  return ONLINE_MENUS.some((candidate) => candidate.view === menu.view);
}
