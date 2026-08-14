import { useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  ReviewListRead,
  ReviewRead,
  ReviewTargetKind,
} from "../api/types";
import "./Reviews.css";


export type ReviewsApi = Pick<
  ApiClient,
  | "getReviews"
  | "saveReview"
  | "deleteReview"
  | "getReceivedReviews"
  | "replyToReview"
>;

export type PublicReviewsApi = Pick<
  ReviewsApi,
  "getReviews" | "saveReview" | "deleteReview"
>;

export type ReceivedReviewsApi = Pick<
  ReviewsApi,
  "getReceivedReviews" | "replyToReview"
>;


function errorMessage(reason: unknown) {
  return reason instanceof Error ? reason.message : "Amal bajarilmadi.";
}


function Stars({ value, large = false }: { value: number; large?: boolean }) {
  return (
    <span className={`reviews-modular__stars${large ? " is-large" : ""}`}>
      {[1, 2, 3, 4, 5].map((star) => (
        <span className={star <= value ? "is-on" : ""} key={star}>★</span>
      ))}
    </span>
  );
}


function ReviewCard({ review, owner = false }: { review: ReviewRead; owner?: boolean }) {
  return (
    <article className="reviews-modular__card">
      <div className="reviews-modular__card-head">
        <div>
          <b>{review.user_name}</b>
          {owner ? (
            <small>{new Date(review.created_at).toLocaleDateString("uz-UZ")}</small>
          ) : null}
        </div>
        <Stars value={review.stars} />
      </div>
      <p className={review.comment ? "" : "is-muted"}>
        {review.comment || "Matnsiz baho"}
      </p>
      {review.owner_reply ? (
        <div className="reviews-modular__owner-reply">
          <b>{owner ? "Sizning javobingiz" : "Mutaxassis javobi"}</b>
          <div>{review.owner_reply}</div>
        </div>
      ) : null}
    </article>
  );
}


type PublicProps = {
  api: PublicReviewsApi;
  targetKind: ReviewTargetKind;
  targetPublicId: string;
};


export function PublicReviews({
  api,
  targetKind,
  targetPublicId,
}: PublicProps) {
  const [data, setData] = useState<ReviewListRead | null>(null);
  const [stars, setStars] = useState(0);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  async function load(active: () => boolean = () => true) {
    const next = await api.getReviews(targetKind, targetPublicId);
    if (!active()) return;
    setData(next);
    setStars(next.my_review?.stars ?? 0);
    setComment(next.my_review?.comment ?? "");
  }

  useEffect(() => {
    let active = true;
    setData(null);
    setError("");
    void load(() => active).catch((reason) => {
      if (active) setError(errorMessage(reason));
    });
    return () => { active = false; };
  }, [api, targetKind, targetPublicId]);

  async function save() {
    if (stars < 1) {
      setError("Iltimos, yulduz tanlang.");
      return;
    }
    setBusy(true);
    setError("");
    setSaved("");
    try {
      await api.saveReview({
        target_kind: targetKind,
        target_public_id: targetPublicId,
        stars,
        comment,
      });
      setSaved("Rahmat! Bahoyingiz saqlandi ✅");
      await load();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm("Bahoyingiz o‘chirilsinmi?")) return;
    setBusy(true);
    setError("");
    try {
      await api.deleteReview(targetKind, targetPublicId);
      setSaved("O‘chirildi");
      await load();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  if (!data && !error) {
    return <div className="reviews-modular__loading">Fikrlar yuklanmoqda...</div>;
  }

  return (
    <section className="reviews-modular public-reviews-modular">
      <div className="sec-head"><h2>Baholar va fikrlar</h2></div>
      {data?.count ? (
        <div className="reviews-modular__summary">
          <strong>{data.avg.toFixed(1)}</strong>
          <span>★</span>
          <small>({data.count} ta fikr)</small>
        </div>
      ) : (
        <div className="reviews-modular__muted">Hali baho yo‘q</div>
      )}

      {data?.can_review ? (
        <div className="reviews-modular__form">
          <b>{data.my_review ? "Bahoyingizni o‘zgartiring" : "Baho bering"}</b>
          <div className="reviews-modular__star-input">
            {[1, 2, 3, 4, 5].map((star) => (
              <button
                aria-label={`${star} yulduz`}
                className={star <= stars ? "is-on" : ""}
                key={star}
                type="button"
                onClick={() => setStars(star)}
              >★</button>
            ))}
          </div>
          <textarea
            maxLength={1000}
            placeholder="Fikringiz (ixtiyoriy)"
            rows={2}
            value={comment}
            onChange={(event) => setComment(event.currentTarget.value)}
          />
          <button type="button" disabled={busy} onClick={() => void save()}>
            {data.my_review ? "Yangilash" : "Yuborish"}
          </button>
          {data.my_review ? (
            <button
              className="is-soft"
              type="button"
              disabled={busy}
              onClick={() => void remove()}
            >Bahoni o‘chirish</button>
          ) : null}
        </div>
      ) : null}

      {error ? <p role="alert" className="reviews-modular__error">{error}</p> : null}
      {saved ? <p role="status" className="reviews-modular__saved">{saved}</p> : null}
      <div className="reviews-modular__list">
        {data?.reviews.length
          ? data.reviews.map((review) => <ReviewCard key={review.id} review={review} />)
          : <div className="reviews-modular__muted is-center">Hozircha fikr yo‘q</div>}
      </div>
    </section>
  );
}


function OwnerReviewCard({
  api,
  review,
  onSaved,
}: {
  api: ReceivedReviewsApi;
  review: ReviewRead;
  onSaved(review: ReviewRead): void;
}) {
  const [reply, setReply] = useState(review.owner_reply);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function save() {
    const clean = reply.trim();
    if (!clean) {
      setError("Javob matnini kiriting.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      onSaved(await api.replyToReview(review.id, clean));
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <ReviewCard owner review={review} />
      <div className="reviews-modular__reply-form">
        <textarea
          maxLength={1500}
          placeholder="Mijozga javob yozing..."
          value={reply}
          onChange={(event) => setReply(event.currentTarget.value)}
        />
        <button type="button" disabled={busy} onClick={() => void save()}>
          {review.owner_reply ? "Javobni yangilash" : "Javob berish"}
        </button>
        {error ? <p role="alert" className="reviews-modular__error">{error}</p> : null}
      </div>
    </div>
  );
}


export function ReceivedReviews({
  api,
  onBack,
}: {
  api: ReceivedReviewsApi;
  onBack(): void;
}) {
  const [data, setData] = useState<ReviewListRead | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    api.getReceivedReviews()
      .then((next) => { if (active) setData(next); })
      .catch((reason) => { if (active) setError(errorMessage(reason)); });
    return () => { active = false; };
  }, [api]);

  function replaceReview(next: ReviewRead) {
    setData((current) => current ? {
      ...current,
      reviews: current.reviews.map((row) => row.id === next.id ? next : row),
    } : current);
  }

  return (
    <main className="profile-shell reviews-modular received-reviews-modular">
      <header className="profile-heading">
        <div>
          <p className="session-panel__eyebrow">{data ? `${data.count} ta fikr` : "Koprik"}</p>
          <h1>Baholar va fikrlar</h1>
        </div>
        <button className="button-secondary" type="button" onClick={onBack}>
          Kabinetga qaytish
        </button>
      </header>
      {error ? <p role="alert" className="reviews-modular__error">{error}</p> : null}
      {!data && !error ? <p>Fikrlar yuklanmoqda...</p> : null}
      {data && !data.reviews.length ? (
        <div className="reviews-modular__empty">
          <h3>Hozircha fikr yo‘q</h3>
          <p>Mijozlar qoldirgan baho va fikrlar shu yerda ko‘rinadi.</p>
        </div>
      ) : null}
      <div className="reviews-modular__list">
        {data?.reviews.map((review) => (
          <OwnerReviewCard
            api={api}
            key={review.id}
            review={review}
            onSaved={replaceReview}
          />
        ))}
      </div>
    </main>
  );
}
