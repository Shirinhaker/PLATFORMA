import { useEffect, useRef, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  EducationStatisticsPeriod,
  EducationStatisticsReport,
} from "../api/types";
import "./EducationStatisticsV1656.css";


export type EducationStatisticsApi = Pick<ApiClient, "getEducationStatistics">;

const PERIODS: Array<{ key: EducationStatisticsPeriod; label: string }> = [
  { key: "day", label: "Kun" },
  { key: "month", label: "Oy" },
  { key: "year", label: "Yil" },
];

const MONTHS = [
  "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
  "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
];

function localIsoDate(value = new Date()) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function parseDate(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year || 2000, (month || 1) - 1, day || 1);
}

function shiftDate(
  period: EducationStatisticsPeriod,
  selectedDate: string,
  direction: -1 | 1,
) {
  const value = parseDate(selectedDate);
  if (period === "day") {
    value.setDate(value.getDate() + direction);
  } else if (period === "month") {
    value.setDate(1);
    value.setMonth(value.getMonth() + direction);
  } else {
    value.setMonth(0, 1);
    value.setFullYear(value.getFullYear() + direction);
  }
  return localIsoDate(value);
}

function periodLabel(period: EducationStatisticsPeriod, selectedDate: string) {
  const value = parseDate(selectedDate);
  if (period === "day") {
    return `${value.getDate()} ${MONTHS[value.getMonth()]} ${value.getFullYear()}`;
  }
  if (period === "year") return String(value.getFullYear());
  return `${MONTHS[value.getMonth()]} ${value.getFullYear()}`;
}

function money(value: number) {
  const amount = Math.trunc(Number(value || 0));
  const sign = amount < 0 ? "−" : "";
  return `${sign}${Math.abs(amount).toLocaleString("uz-UZ")} so'm`;
}

function message(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Statistikani yuklab bo'lmadi.";
}

function Metric({
  label,
  value,
  tone = "",
}: {
  label: string;
  value: string;
  tone?: "positive" | "negative" | "";
}) {
  return (
    <article className="education-statistics-v1656__metric">
      <small>{label}</small>
      <strong className={tone}>{value}</strong>
    </article>
  );
}

export function EducationStatisticsV1656({
  api,
  onBack,
}: {
  api: EducationStatisticsApi;
  onBack: () => void;
}) {
  const [period, setPeriod] = useState<EducationStatisticsPeriod>("month");
  const [selectedDate, setSelectedDate] = useState(() => localIsoDate());
  const [data, setData] = useState<EducationStatisticsReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const requestVersion = useRef(0);

  useEffect(() => {
    const version = ++requestVersion.current;
    setLoading(true);
    setError("");
    api.getEducationStatistics(period, selectedDate)
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
  }, [api, period, selectedDate]);

  const student = data?.student_finance;
  const teacher = data?.teacher_finance;
  const result = data?.result;
  const process = data?.education;

  return (
    <main className="education-statistics-v1656">
      <header className="education-statistics-v1656__heading">
        <button type="button" onClick={onBack}>← Kabinetga qaytish</button>
        <div>
          <h1>Ta'lim statistikasi</h1>
          <p>Davomat, to'lovlar, maosh va natija</p>
        </div>
      </header>

      <section className="education-statistics-v1656__intro">
        <b>Ta'lim boshqaruv paneli</b>
        <p>O'quv jarayoni va moliyaviy natijalar bitta joyda.</p>
      </section>

      <nav className="education-statistics-v1656__periods" aria-label="Ta'lim statistikasi davri">
        {PERIODS.map((option) => (
          <button
            type="button"
            key={option.key}
            className={period === option.key ? "active" : ""}
            onClick={() => setPeriod(option.key)}
          >{option.label}</button>
        ))}
      </nav>

      <nav className="education-statistics-v1656__navigation" aria-label="Davr navigatsiyasi">
        <button
          type="button"
          aria-label="Oldingi davr"
          onClick={() => setSelectedDate((value) => shiftDate(period, value, -1))}
        >‹</button>
        <div><b>{periodLabel(period, selectedDate)}</b><small>Tanlangan davr</small></div>
        <button
          type="button"
          aria-label="Keyingi davr"
          onClick={() => setSelectedDate((value) => shiftDate(period, value, 1))}
        >›</button>
      </nav>

      {error ? <p className="education-statistics-v1656__error" role="alert">{error}</p> : null}
      {loading ? <p className="education-statistics-v1656__loading">Statistika yuklanmoqda...</p> : null}

      {!loading && data ? (
        <div className="education-statistics-v1656__content">
          <section>
            <h2>Ta'lim jarayoni</h2>
            <div className="education-statistics-v1656__grid">
              <Metric label="Faol o'quvchilar" value={`${process?.active_students ?? 0} nafar`} />
              <Metric label="Faol guruhlar" value={`${process?.active_groups ?? 0} ta`} />
              <Metric label="Yangi yozilishlar" value={`${process?.new_enrollments ?? 0} ta`} />
              <Metric label="O'rtacha davomat" value={`${process?.attendance_percent ?? 0}%`} />
            </div>
          </section>

          <section>
            <h2>O'quvchi to'lovlari</h2>
            <div className="education-statistics-v1656__grid">
              <Metric label="Hisoblandi" value={money(student?.calculated ?? 0)} />
              <Metric label="Qabul qilindi" value={money(student?.paid ?? 0)} tone="positive" />
              <Metric label="Qarzdorlik" value={money(student?.debt ?? 0)} tone={(student?.debt ?? 0) > 0 ? "negative" : "positive"} />
            </div>
          </section>

          <section>
            <h2>O'qituvchi maoshi</h2>
            <div className="education-statistics-v1656__grid">
              <Metric label="Hisoblandi" value={money(teacher?.calculated ?? 0)} />
              <Metric label="To'landi" value={money(teacher?.paid ?? 0)} tone="positive" />
              <Metric label="To'lanmagan" value={money(teacher?.debt ?? 0)} tone={(teacher?.debt ?? 0) > 0 ? "negative" : "positive"} />
            </div>
          </section>

          <section>
            <h2>Yakuniy natija</h2>
            <div className="education-statistics-v1656__grid">
              <Metric label="Boshqa xarajatlar" value={money(result?.other_expenses ?? 0)} />
              <Metric
                label="Haqiqiy pul oqimi"
                value={`${(result?.cash_flow ?? 0) < 0 ? "Zarar" : "Qoldiq"} · ${money(result?.cash_flow ?? 0)}`}
                tone={(result?.cash_flow ?? 0) < 0 ? "negative" : "positive"}
              />
              <Metric
                label="Hisoblangan natija"
                value={`${(result?.accrual_result ?? 0) < 0 ? "Zarar" : "Foyda"} · ${money(result?.accrual_result ?? 0)}`}
                tone={(result?.accrual_result ?? 0) < 0 ? "negative" : "positive"}
              />
            </div>
          </section>

          <section>
            <h2>Guruhlar kesimi</h2>
            {data.groups.length ? (
              <div className="education-statistics-v1656__groups">
                {data.groups.map((group) => (
                  <article key={group.id}>
                    <header>
                      <div><b>{group.name || "Guruh"}</b><small>{group.active_students} o'quvchi · Davomat {group.attendance_percent}%</small></div>
                      <em>Qarz {money(group.debt)}</em>
                    </header>
                    <div>
                      <span>Hisoblandi<b>{money(group.calculated)}</b></span>
                      <span>Olindi<b className="positive">{money(group.paid)}</b></span>
                      <span>Qarz<b className={group.debt ? "negative" : "positive"}>{money(group.debt)}</b></span>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="education-statistics-v1656__empty">
                <h3>Guruhlar yo'q</h3>
                <p>Statistika uchun avval faol guruh yarating.</p>
              </div>
            )}
          </section>
        </div>
      ) : null}
    </main>
  );
}
