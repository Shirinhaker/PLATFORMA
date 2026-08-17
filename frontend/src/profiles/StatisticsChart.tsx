import type { StatisticsTrend } from "../api/types";

export type Metric = "rev" | "exp" | "profit";

export const METRIC_LABELS: Record<Metric, string> = {
  rev: "Tushum",
  exp: "Xarajat",
  profit: "Foyda",
};

export function money(value: number) {
  return Number(value || 0).toLocaleString("uz-UZ");
}

function metricValue(item: StatisticsTrend, metric: Metric) {
  return metric === "rev" ? item.rev : metric === "exp" ? item.exp : item.profit;
}

function maxAbsolute(items: StatisticsTrend[], metric: Metric) {
  let maximum = 1;
  for (const item of items) {
    const value = Math.abs(metricValue(item, metric));
    if (value > maximum) maximum = value;
  }
  return maximum;
}

export function StatisticsBars({
  items,
  metric,
}: {
  items: StatisticsTrend[];
  metric: Metric;
}) {
  const width = 340;
  const height = 130;
  const horizontalPadding = 6;
  const labelHeight = 16;
  const chartHeight = height - labelHeight;
  const hasNegative = metric === "profit" && items.some((item) => item.profit < 0);
  const zeroY = hasNegative ? chartHeight / 2 : chartHeight;
  const maxBarHeight = hasNegative ? chartHeight / 2 - 2 : chartHeight - 2;
  const maximum = maxAbsolute(items, metric);
  const bandWidth = (width - horizontalPadding * 2) / Math.max(1, items.length);
  const labelStep = Math.max(1, Math.ceil(items.length / 8));

  return (
    <svg
      className="statistics-v1656__chart"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`${METRIC_LABELS[metric]} grafigi`}
    >
      {hasNegative ? (
        <line
          x1={horizontalPadding}
          y1={zeroY}
          x2={width - horizontalPadding}
          y2={zeroY}
          className="statistics-v1656__zero"
        />
      ) : null}
      {items.map((item, index) => {
        const value = metricValue(item, metric);
        const barHeight = Math.max(
          1,
          Math.round((Math.abs(value) / maximum) * maxBarHeight),
        );
        const x = horizontalPadding + index * bandWidth + bandWidth * 0.14;
        const y = value >= 0 ? zeroY - barHeight : zeroY;
        const showLabel = index % labelStep === 0 || index === items.length - 1;
        return (
          <g key={`${item.label}-${index}`}>
            <rect
              x={x}
              y={y}
              width={bandWidth * 0.72}
              height={barHeight}
              rx="2"
              className={`statistics-v1656__bar statistics-v1656__bar--${metric}${value < 0 ? " statistics-v1656__bar--negative" : ""}`}
            >
              <title>
                {item.label}: {money(value)}
              </title>
            </rect>
            {showLabel ? (
              <text
                x={horizontalPadding + index * bandWidth + bandWidth / 2}
                y={height - 3}
                textAnchor="middle"
              >
                {item.label}
              </text>
            ) : null}
          </g>
        );
      })}
    </svg>
  );
}
