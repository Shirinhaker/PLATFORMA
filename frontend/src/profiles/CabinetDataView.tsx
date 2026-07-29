import "./Cabinet.css";


type RecordValue = Record<string, unknown>;

const FIELD_LABELS: Record<string, string> = {
  title: "Nomi",
  name: "Nomi",
  item_name: "Mahsulot/xizmat",
  status: "Holati",
  phone: "Telefon",
  price: "Narxi",
  price_text: "Narxi",
  total_amount: "Jami",
  amount: "Summa",
  qty: "Miqdor",
  note: "Izoh",
  descr: "Tavsif",
  description: "Tavsif",
  address: "Manzil",
  cat: "Toifa",
  kind: "Turi",
  created_at: "Yaratilgan",
  updated_at: "Yangilangan",
};


function present(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Ha" : "Yo‘q";
  if (typeof value === "number") return String(value);
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}


function headingEntry(row: RecordValue, index: number) {
  for (const key of ["title", "name", "item_name"] as const) {
    const value = row[key];
    if (value !== null && value !== undefined && value !== "") {
      return { key, value };
    }
  }
  return { key: "", value: `#${row.id ?? index + 1}` };
}


function usefulEntries(row: RecordValue, headingKey: string) {
  const preferred = Object.keys(FIELD_LABELS)
    .filter((key) => key !== headingKey && key in row)
    .map((key) => [key, row[key]] as const);
  if (preferred.length) return preferred.slice(0, 7);
  return Object.entries(row)
    .filter(([key]) => (
      key !== headingKey
      && !key.includes("hash")
      && !key.includes("token")
    ))
    .slice(0, 7);
}


export function CabinetDataView({
  title,
  rows,
  onBack,
}: {
  title: string;
  rows: unknown;
  onBack: () => void;
}) {
  const list = Array.isArray(rows) ? rows : [];
  return (
    <main className="cabinet-data-view">
      <header className="cabinet-data-view__heading">
        <button type="button" onClick={onBack}>← Kabinetga qaytish</button>
        <div>
          <h1>{title}</h1>
          <p>{list.length} ta haqiqiy yozuv</p>
        </div>
      </header>
      {!list.length ? (
        <div className="cabinet-data-view__empty">
          Bu bo‘limda hozircha ma’lumot yo‘q.
        </div>
      ) : (
        <div className="cabinet-data-view__list">
          {list.map((item, index) => {
            const row = item && typeof item === "object"
              ? item as RecordValue
              : { value: item };
            const heading = headingEntry(row, index);
            return (
              <article key={String(row.id ?? index)}>
                <strong>{present(heading.value)}</strong>
                <dl>
                  {usefulEntries(row, heading.key).map(([key, value]) => (
                    <div key={key}>
                      <dt>{FIELD_LABELS[key] ?? key}</dt>
                      <dd>{present(value)}</dd>
                    </div>
                  ))}
                </dl>
              </article>
            );
          })}
        </div>
      )}
    </main>
  );
}
