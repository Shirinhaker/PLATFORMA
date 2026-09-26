import type { PublicSearchItem } from "../../../api/types";

export type HomeSearchMemory = {
  district: string;
  query: string;
  resultQuery: string;
  results: PublicSearchItem[] | null;
  searchPage: number;
  searchPages: number;
  scrollTop: number;
};
