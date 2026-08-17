import { useEffect, useRef, useState } from "react";

import type { ApiClient } from "../api/client";
import type { StatisticsPeriod, StatisticsReport } from "../api/types";
import { METRIC_LABELS, StatisticsBars, money, type Metric } from "./StatisticsChart";
import "./Statistics.css";

export type StatisticsApi = Pick<ApiClient, "getStatistics" | "getStatisticsNav">;

const PERIODS: Array<{ key: StatisticsPeriod; label: string }> = [
  { key: "kun", label: "Kun" },
  { key: "hafta", label: "Hafta" },
  { key: "oy", label: "Oy" },
  { key: "chorak", label: "Chorak" },
  { key: "yarim", label: "Yarim yil" },
  { key: "yil", label: "Yil" },
];

const EMPTY_REPORT: StatisticsReport = {
  period: "oy",
  anchor: "",
  label: "",
  revenue: 0,
  cash_in: 0,
  cogs: 0,
  gross_profit: 0,
  expenses: 0,
  inventory_purchases: 0,
  profit: 0,
  qarzpay: 0,
  pay: { naqd: 0, karta: 0, qarz: 0, order: 0 },
  exp_by_cat: {},
  trend: [],
  top_products: [],
  low_stock: [],
  source_split: {
    internal: { count: 0, total: 0 },
    external: { count: 0, total: 0 },
    manual: { count: 0, total: 0 },
  },
  cashiers: [],
  waiters: [],
  sales_count: 0,
  can_next: false,
};

function quantity(value: number) {
  return Number(value || 0).toLocaleString("uz-UZ", {
    maximumFractionDigits: 3,
  });
}

function message(error: unknown) {
  return error instanceof Error ? error.message : "Statistikani yuklab bo‘lmadi.";
}

function ProgressRow({
  label,
  value,
  maximum,
  color,
}: {
  label: string;
  value: number;
  maximum: number;
  color: string;
}) {
  const width = Math.round((value / Math.max(1, maximum)) * 100);
  return (
    <div className="statistics-v1656__progress-row">
      <div>
        <span>{label}</span>
        <b>{money(value)}</b>
      </div>
      <i>
        <span style={{ width: `${width}%`, background: color }} />
      </i>
    </div>
  );
}

function maximumOf(values: number[]) {
  let maximum = 1;
  for (const value of values) {
    if (value > maximum) maximum = value;
  }
  return maximum;
}

export function Statistics({
  api,
  onBack,
}: {
  api: StatisticsApi;
  onBack: () => void;
}) {
  const [period, setPeriod] = useState<StatisticsPeriod>("oy");
  const [anchor, setAnchor] = useState("");
  const [metric, setMetric] = useState<Metric>("rev");
  const [data, setData] = useState<StatisticsReport>(EMPTY_REPORT);
  const [loading, setLoading] = useState(true);
  const [navigating, setNavigating] = useState(false);
  const [error, setError] = useState("");
  const requestVersion = useRef(0);
  const navigationVersion = useRef(0);

  useEffect(() => {
    const version = ++requestVersion.current;
    setLoading(true);
    setError("");
    api
      .getStatistics(period, anchor)
      .then((value) => {
        if (requestVersion.current === version) setData(value);
      })
      .catch((reason) => {
        if (requestVersion.current === version) setError(message(reason));
      })
      .finally(() => {
        if (requestVersion.current === version) setLoading(false);
      });
    return () => {
      if (requestVersion.current === version) requestVersion.current += 1;
    };
  }, [api, period, anchor]);

  async function navigate(direction: -1 | 1) {
    const version = ++navigationVersion.current;
    setNavigating(true);
    setError("");
    try {
      const result = await api.getStatisticsNav(period, direction, anchor);
      if (navigationVersion.current === version) setAnchor(result.anchor);
    } catch (reason) {
      if (navigationVersion.current === version) setError(message(reason));
    } finally {
      if (navigationVersion.current === version) setNavigating(false);
    }
  }

  const paymentMaximum = maximumOf([
    data.pay.naqd,
    data.pay.karta,
    data.pay.qarz,
    data.pay.order,
  ]);
  const sourceMaximum = maximumOf([
    data.source_split.internal.total,
    data.source_split.external.total,
    data.source_split.manual.total,
  ]);
  const productMaximum = maximumOf(data.top_products.map((item) => item.total));
  const profitClass = data.profit >= 0 ? "positive" : "negative";

  return (
    <main className="statistics-v1656">
      <header className="statistics-v1656__heading">
        <button type="button" onClick={onBack}>
          ← Kabinetga qaytish
        </button>
        <div>
          <h1>Statistika</h1>
          <p>Tushum, xarajat, foyda va tovarlar</p>
        </div>
      </header>

      <nav className="statistics-v1656__periods" aria-label="Statistika davri">
        {PERIODS.map((option) => (
          <button
            type="button"
            key={option.key}
            className={period === option.key ? "active" : ""}
            onClick={() => {
              navigationVersion.current += 1;
              setNavigating(false);
              setPeriod(option.key);
              setAnchor("");
            }}
          >
            {option.label}
          </button>
        ))}
      </nav>

      <nav className="statistics-v1656__navigation" aria-label="Davr navigatsiyasi">
        <button
          type="button"
          aria-label="Oldingi davr"
          disabled={navigating}
          onClick={() => void navigate(-1)}
        >
          ←
        </button>
        <b>{data.label || "—"}</b>
        <button
          type="button"
          aria-label="Keyingi davr"
          disabled={navigating}
          style={{ visibility: data.can_next ? "visible" : "hidden" }}
          onClick={() => void navigate(1)}
        >
          →
        </button>
      </nav>

      {error ? (
        <p className="statistics-v1656__error" role="alert">
          {error}
        </p>
      ) : null}
      {loading ? <p className="statistics-v1656__empty">Yuklanmoqda…</p> : null}

      {!loading ? (
        <>
          <section
            className="statistics-v1656__financial"
            aria-label="Moliyaviy natijalar"
          >
            <article>
              <small>Haqiqiy pul tushumi</small>
              <strong className="positive">{money(data.cash_in)}</strong>
            </article>
            <article>
              <small>Jami savdo</small>
              <strong>{money(data.revenue)}</strong>
            </article>
            <article>
              <small>FIFO sotuv tannarxi</small>
              <strong className="cost">{money(data.cogs)}</strong>
            </article>
            <article>
              <small>Yalpi foyda</small>
              <strong>{money(data.gross_profit)}</strong>
            </article>
            <article>
              <small>Operatsion xarajat</small>
              <strong className="negative">{money(data.expenses)}</strong>
            </article>
            <article>
              <small>Xomashyo xaridi</small>
              <strong className="purchase">{money(data.inventory_purchases)}</strong>
            </article>
            <article className="statistics-v1656__profit">
              <small>Sof foyda (savdo − FIFO tannarx − operatsion xarajat)</small>
              <strong className={profitClass}>{money(data.profit)} so'm</strong>
              {data.qarzpay ? (
                <p>
                  Qarzdan qaytgan pul: {money(data.qarzpay)} — haqiqiy tushumga
                  qo‘shildi
                </p>
              ) : null}
            </article>
          </section>

          <section className="statistics-v1656__panel">
            <nav className="statistics-v1656__metrics" aria-label="Grafik ko‘rsatkichi">
              {(Object.keys(METRIC_LABELS) as Metric[]).map((key) => (
                <button
                  type="button"
                  key={key}
                  className={metric === key ? "active" : ""}
                  onClick={() => setMetric(key)}
                >
                  {METRIC_LABELS[key]}
                </button>
              ))}
            </nav>
            {data.trend.length ? (
              <StatisticsBars items={data.trend} metric={metric} />
            ) : (
              <p className="statistics-v1656__empty">Ma’lumot yo‘q</p>
            )}
          </section>

          <section className="statistics-v1656__panel">
            <h2>To‘lov turlari</h2>
            <ProgressRow
              label="Naqd"
              value={data.pay.naqd}
              maximum={paymentMaximum}
              color="#188038"
            />
            <ProgressRow
              label="Karta"
              value={data.pay.karta}
              maximum={paymentMaximum}
              color="#1a73e8"
            />
            <ProgressRow
              label="Qarz (sotildi)"
              value={data.pay.qarz}
              maximum={paymentMaximum}
              color="#e6a100"
            />
            <ProgressRow
              label="Buyurtma"
              value={data.pay.order}
              maximum={paymentMaximum}
              color="#8e44ad"
            />
          </section>

          <section className="statistics-v1656__panel">
            <h2>🍽️ Savdo manbalari</h2>
            <ProgressRow
              label={`Ichki buyurtma · ${data.source_split.internal.count} ta`}
              value={data.source_split.internal.total}
              maximum={sourceMaximum}
              color="#16a34a"
            />
            <ProgressRow
              label={`Tashqi buyurtma · ${data.source_split.external.count} ta`}
              value={data.source_split.external.total}
              maximum={sourceMaximum}
              color="#2563eb"
            />
            <ProgressRow
              label={`Kassa savdosi · ${data.source_split.manual.count} ta`}
              value={data.source_split.manual.total}
              maximum={sourceMaximum}
              color="#8b5cf6"
            />
          </section>

          {data.top_products.length ? (
            <section className="statistics-v1656__panel statistics-v1656__products">
              <h2>🛒 Eng ko‘p sotilganlar</h2>
              {data.top_products.map((product) => (
                <article key={`${product.name}-${product.unit}`}>
                  <div>
                    <span>{product.name}</span>
                    <b>{money(product.total)}</b>
                  </div>
                  <i>
                    <span
                      style={{
                        width: `${Math.round((product.total / productMaximum) * 100)}%`,
                      }}
                    />
                  </i>
                  <small>
                    {quantity(product.qty)} {product.unit || "dona"} sotildi
                    {product.margin !== null ? ` · foyda ${money(product.margin)}` : ""}
                  </small>
                </article>
              ))}
            </section>
          ) : null}

          {data.low_stock.length ? (
            <section className="statistics-v1656__panel statistics-v1656__stock">
              <h2>📦 Kam qolgan tovarlar</h2>
              {data.low_stock.map((item) => (
                <div key={item.name}>
                  <span>{item.name}</span>
                  <b
                    className={
                      item.stock_qty < 0
                        ? "negative"
                        : item.stock_qty <= 5
                          ? "cost"
                          : ""
                    }
                  >
                    {quantity(item.stock_qty)} {item.unit || "dona"}
                  </b>
                </div>
              ))}
            </section>
          ) : null}

          {data.waiters.length ? (
            <section className="statistics-v1656__panel statistics-v1656__employees">
              <h2>🧑‍🍳 Ofitsiantlar</h2>
              {data.waiters.map((item) => (
                <div key={item.name}>
                  <span>
                    {item.name} · {item.orders} ta
                  </span>
                  <b>{money(item.total)}</b>
                </div>
              ))}
            </section>
          ) : null}

          {data.cashiers.length ? (
            <section className="statistics-v1656__panel statistics-v1656__employees">
              <h2>🧾 Kassirlar</h2>
              {data.cashiers.map((item) => (
                <div key={item.name}>
                  <span>
                    {item.name} · {item.checks} ta chek
                  </span>
                  <b>{money(item.total)}</b>
                </div>
              ))}
            </section>
          ) : null}
        </>
      ) : null}
    </main>
  );
}
