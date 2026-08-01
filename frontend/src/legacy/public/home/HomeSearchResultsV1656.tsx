import type { PublicSearchItem } from "../../../api/types";


interface HomeSearchResultsV1656Props {
  error: string;
  hasMore: boolean;
  items: PublicSearchItem[];
  loadingMore: boolean;
  pending: boolean;
  query: string;
  onLoadMore(): void;
  onOpenResult(item: PublicSearchItem): void;
}


function Chevron() {
  return (
    <span className="chev" aria-hidden="true">
      <svg viewBox="0 0 24 24">
        <path d="M9 18l6-6-6-6" />
      </svg>
    </span>
  );
}


function initials(name: string) {
  return (name || "?")
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word.charAt(0))
    .join("")
    .toUpperCase();
}


function ResultImage({ item, fallback }: {
  item: PublicSearchItem;
  fallback: string;
}) {
  return (
    <div className="li-thumb" style={{ background: "var(--primary-tint)" }}>
      {item.image_url ? (
        <img alt="" loading="lazy" src={item.image_url} />
      ) : (
        <span>{fallback}</span>
      )}
    </div>
  );
}


export function HomeSearchResultsV1656({
  error,
  hasMore,
  items,
  loadingMore,
  pending,
  query,
  onLoadMore,
  onOpenResult,
}: HomeSearchResultsV1656Props) {
  if (pending) {
    return (
      <div className="empty" style={{ padding: "30px 16px" }}>
        <h3>Qidirilmoqda…</h3>
        <p>Iltimos, biroz kuting.</p>
      </div>
    );
  }
  if (error) return <p className="elon-hint">{error}</p>;
  if (!items.length) {
    return (
      <div className="empty" style={{ padding: "30px 16px" }}>
        <h3>Hech narsa topilmadi</h3>
        <p>
          Barchasi · &quot;{query}&quot; bo&apos;yicha natija yo&apos;q. Boshqa
          so&apos;z bilan qidiring yoki katalogdan tanlang.
        </p>
      </div>
    );
  }

  const products = items.filter(
    (item) => item.kind === "product" || item.kind === "service",
  );
  const businesses = items.filter((item) => item.kind === "business");
  const users = items.filter((item) => item.kind === "user");

  return (
    <>
      {products.length ? (
        <>
          <div className="list-sub">🛍 Mahsulot va xizmatlar</div>
          {products.map((item) => (
            <button
              className="elon-item"
              key={`${item.kind}:${item.public_id}`}
              type="button"
              onClick={() => onOpenResult(item)}
            >
              <ResultImage
                fallback={item.kind === "service" ? "🧰" : "🛍️"}
                item={item}
              />
              <span className="li-main">
                <span className="li-title">{item.name}</span>
                <span className="li-meta">🏪 {item.owner_label || ""}</span>
              </span>
              <span className="iprice">{item.price_text || ""}</span>
            </button>
          ))}
        </>
      ) : null}

      {businesses.length ? (
        <>
          <div className="list-sub" style={{ marginTop: 6 }}>🏪 Bizneslar</div>
          {businesses.map((item) => (
            <button
              className="biz-card"
              key={item.public_id}
              type="button"
              onClick={() => onOpenResult(item)}
            >
              <span className="biz-logo">
                {item.image_url ? (
                  <img alt="" src={item.image_url} />
                ) : (
                  <span style={{ fontSize: 18 }}>🏪</span>
                )}
              </span>
              <span className="biz-main">
                <span className="biz-name">{item.name}</span>
                <span className="biz-meta">
                  <span className="cat">
                    {item.activity_type || item.direction || ""}
                  </span>
                </span>
              </span>
              <Chevron />
            </button>
          ))}
        </>
      ) : null}

      {users.length ? (
        <>
          <div className="list-sub" style={{ marginTop: 6 }}>
            🧑 Foydalanuvchilar
          </div>
          {users.map((item) => (
            <button
              className="biz-card"
              key={item.public_id}
              type="button"
              onClick={() => onOpenResult(item)}
            >
              <span
                className="biz-logo"
                style={{ background: "linear-gradient(135deg,#6a8dff,#9a6bff)" }}
              >
                {item.image_url ? (
                  <img alt="" src={item.image_url} />
                ) : (
                  <span style={{ color: "#fff", fontSize: 16, fontWeight: 800 }}>
                    {initials(item.name)}
                  </span>
                )}
              </span>
              <span className="biz-main">
                <span className="biz-name">{item.name || "Foydalanuvchi"}</span>
                <span className="biz-meta">
                  <span className="cat">@{item.public_username || ""}</span>
                </span>
              </span>
              <Chevron />
            </button>
          ))}
        </>
      ) : null}

      {hasMore ? (
        <button
          className="btn btn-soft btn-block"
          disabled={loadingMore}
          style={{ margin: "14px 0 6px" }}
          type="button"
          onClick={onLoadMore}
        >
          Yana ko&apos;rsatish
        </button>
      ) : null}
    </>
  );
}
