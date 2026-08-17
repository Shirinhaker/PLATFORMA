import type { PublicProfileDetail } from "../../api/types";

type Specialist = NonNullable<PublicProfileDetail["specialist"]>;

export function PublicProfileSpecialistSections({
  specialist,
}: {
  specialist: Specialist;
}) {
  return (
    <>
      <section className="specialist-card">
        <b>{specialist.profession || "Mutaxasis"}</b>
        {specialist.description ? (
          <div className="idesc">{specialist.description}</div>
        ) : null}
      </section>
      {(specialist.credentials ?? []).length ? (
        <section className="public-profile-section public-specialist-section">
          <div className="sec-head">
            <h2>Tasdiqlovchi hujjatlar</h2>
            <span className="link">{specialist.credentials?.length} ta</span>
          </div>
          <div className="public-specialist-rail">
            {specialist.credentials?.map((item) => (
              <div className="sp-media-card" key={item.id}>
                <img alt="Tasdiqlovchi hujjat" loading="lazy" src={item.image_url} />
              </div>
            ))}
          </div>
        </section>
      ) : null}
      {(specialist.offers ?? []).length ? (
        <section className="public-profile-section public-specialist-section">
          <div className="sec-head">
            <h2>Xizmatlar va mahsulotlar</h2>
            <span className="link">{specialist.offers?.length} ta</span>
          </div>
          <div className="public-specialist-rail">
            {specialist.offers?.map((item) => (
              <article className="sp-offer-card" key={item.id}>
                <div className="sp-offer-img">
                  {item.image_url ? (
                    <img alt="" loading="lazy" src={item.image_url} />
                  ) : item.kind === "product" ? (
                    "📦"
                  ) : (
                    "🧰"
                  )}
                </div>
                <div className="sp-offer-body">
                  <div className="sp-offer-kind">
                    {item.kind === "product" ? "Mahsulot" : "Xizmat"}
                  </div>
                  <div className="sp-offer-name">{item.name}</div>
                  {item.price_text ? (
                    <div className="sp-offer-price">{item.price_text}</div>
                  ) : null}
                  {item.note ? <div className="idesc">{item.note}</div> : null}
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}
      {(specialist.portfolio ?? []).length ? (
        <section className="public-profile-section public-specialist-section">
          <div className="sec-head">
            <h2>Bajargan ishlari</h2>
            <span className="link">{specialist.portfolio?.length} ta</span>
          </div>
          <div className="public-specialist-rail">
            {specialist.portfolio?.map((item) => (
              <div className="sp-media-card" key={item.id}>
                {item.media_type === "video" ? (
                  <>
                    <video
                      controls
                      playsInline
                      preload="metadata"
                      src={item.media_url}
                    />
                    <span className="sp-media-type">▶ VIDEO</span>
                  </>
                ) : (
                  <img alt="Ish namunasi" loading="lazy" src={item.media_url} />
                )}
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </>
  );
}
