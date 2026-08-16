// `api/types.ts` dan ajratildi — domen bo'yicha.

export type ReviewTargetKind = "business" | "specialist";

export type ReviewRead = {
  id: number;
  stars: number;
  comment: string;
  user_name: string;
  created_at: string;
  owner_reply: string;
  owner_replied_at: string | null;
};

export type ReviewListRead = {
  reviews: ReviewRead[];
  avg: number;
  count: number;
  can_review: boolean;
  my_review: { stars: number; comment: string } | null;
};

export type ReviewWrite = {
  target_kind: ReviewTargetKind;
  target_public_id: string;
  stars: number;
  comment: string;
};

export type ReviewMutationRead = {
  ok: true;
  avg: number;
  count: number;
};
