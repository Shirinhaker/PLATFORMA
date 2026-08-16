// `BusinessOnlineViews.tsx` dan ajratildi.
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../../api/business-online-types";
import { money } from "../business-profile-config";
import { recordId, recordText, subscriptionDate, subscriptionPlanName } from "./shared";

export function SubscriptionsView({
  rows,
  duration,
  setDuration,
  busy,
  openPayment,
}: {
  rows: BusinessOnlineRecord[];
  duration: number;
  setDuration: (value: number) => void;
  busy: boolean;
  /** Tarif tanlanganda to'lov oynasini ochadi (v1656 oqimi). */
  openPayment: (plan: "plus" | "pro") => void;
}) {
  const current = [...rows]
    .reverse()
    .find((row) => ["active", "approved"].includes(recordText(row, "status")));
  const currentPlan =
    recordText(current ?? {}, "plan", "plan_code", "tariff", "name") || "free";
  const plans = [
    {
      key: "free",
      icon: "🌱",
      name: "Bepul",
      caption: "Asosiy biznes profil uchun",
      benefits: [
        "Biznes profilidan foydalanish",
        "Mahsulot va xizmatlarni cheksiz joylash",
      ],
    },
    {
      key: "plus",
      icon: "✨",
      name: "Plus",
      caption: "Yaqin mijozlarga ko‘rinish",
      benefits: [
        "Bepul tarifdagi barcha imkoniyatlar",
        "Mahsulot yoki xizmatlarni “Sizga yaqin” bo‘limiga chiqarish huquqi",
      ],
    },
    {
      key: "pro",
      icon: "💎",
      name: "Pro",
      caption: "Hudud bo‘yicha keng ko‘rinish",
      benefits: [
        "Plus tarifdagi barcha imkoniyatlar",
        "Biznes metkasini xaritada ko‘rsatish huquqi",
      ],
    },
  ];
  const paid = currentPlan !== "free";
  const history = rows.filter((row) => row !== current);
  return (
    <section className="subscription-shell">
      <div className="subscription-demo-note">
        <span>🧾</span>
        <div>
          <b>To‘lov tartibi</b>
          <br />
          Plus yoki Pro tarifini tanlang, kvitansiyani yuboring. Tarif administrator
          tasdiqlagandan keyin faollashadi.
        </div>
      </div>
      <div className="subscription-current">
        <div className="subscription-current-top">
          <div className="subscription-current-copy">
            <div className="subscription-current-label">Joriy tarif</div>
            <div className="subscription-current-name">
              {subscriptionPlanName(currentPlan)}
            </div>
          </div>
          <span className="subscription-current-badge">Faol</span>
        </div>
        <div className="subscription-current-dates">
          <div className="subscription-date">
            <span>Boshlangan sana</span>
            <b>
              {current
                ? current.starts_at
                  ? subscriptionDate(current.starts_at)
                  : "—"
                : "Avtomatik Bepul"}
            </b>
          </div>
          <div className="subscription-date">
            <span>Tugash sanasi</span>
            <b>{paid ? subscriptionDate(current?.expires_at) : "Muddatsiz"}</b>
          </div>
        </div>
      </div>
      <div className="subscription-section-title">
        <h3>Muddatni tanlang</h3>
        <p>Plus va Pro uchun</p>
      </div>
      <div className="subscription-duration" role="group" aria-label="Obuna muddati">
        {[1, 3, 12].map((month) => (
          <button
            type="button"
            key={month}
            className={duration === month ? "on" : ""}
            aria-pressed={duration === month}
            disabled={busy}
            onClick={() => setDuration(month)}
          >
            {month} oy
          </button>
        ))}
      </div>
      <div className="subscription-section-title">
        <h3>Tariflar</h3>
        <p>Mahsulot va xizmatlarni joylash cheksiz</p>
      </div>
      <div className="subscription-plan-grid">
        {plans.map((plan) => (
          <article
            className={
              currentPlan === plan.key
                ? "subscription-plan-card current"
                : "subscription-plan-card"
            }
            data-plan={plan.key}
            key={plan.key}
          >
            <div className="subscription-plan-top">
              <div className="subscription-plan-copy">
                <div className="subscription-plan-icon">{plan.icon}</div>
                <div>
                  <div className="subscription-plan-name">{plan.name}</div>
                  <div className="subscription-plan-caption">{plan.caption}</div>
                </div>
              </div>
              <span className="subscription-current-pill">Joriy</span>
            </div>
            <ul className="subscription-benefits">
              {plan.benefits.map((benefit) => (
                <li key={benefit}>{benefit}</li>
              ))}
            </ul>
            <button
              type="button"
              className="subscription-action"
              disabled={busy || plan.key === "free"}
              onClick={() => openPayment(plan.key as "plus" | "pro")}
            >
              {plan.key === "free"
                ? currentPlan === "free"
                  ? "Joriy bepul tarif"
                  : "Bepul tarif avtomatik"
                : currentPlan === plan.key
                  ? "Muddatni uzaytirish"
                  : `${plan.name} uchun to‘lov qilish`}
            </button>
          </article>
        ))}
      </div>
      <div className="subscription-section-title">
        <h3>Obuna tarixi</h3>
        <p>Avvalgi tariflar</p>
      </div>
      <div className="subscription-history">
        {history.length ? (
          history.map((row, index) => {
            const status =
              recordText(row, "status") === "expired"
                ? "Muddati tugagan"
                : "Almashtirilgan";
            return (
              <div
                className="subscription-history-row"
                key={String(recordId(row, index))}
              >
                <div>
                  <b>
                    {subscriptionPlanName(
                      recordText(row, "plan", "plan_code", "tariff"),
                    )}
                  </b>
                  <p>
                    {subscriptionDate(row.starts_at)} —{" "}
                    {row.expires_at ? subscriptionDate(row.expires_at) : "Muddatsiz"}
                    {row.duration_months ? ` · ${Number(row.duration_months)} oy` : ""}
                  </p>
                </div>
                <span className="subscription-history-status">{status}</span>
              </div>
            );
          })
        ) : (
          <div className="subscription-state">
            <h3>Tarix hozircha bo‘sh</h3>
            <p>
              Tarif almashtirilganda yoki muddati tugaganda avvalgi obunalar shu yerda
              ko‘rinadi.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
