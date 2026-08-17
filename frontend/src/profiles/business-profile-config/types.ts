// Biznes profili sozlamalari uchun umumiy tiplar.

import { money } from "./helpers";

export type Metric = {
  label: string;
  key: string;
  sub: string;
  view: string;
  money?: boolean;
};

export type PayloadSource = string | readonly string[];

export type Menu = {
  icon: string;
  label: string;
  caption: string;
  view: string;
  payload?: PayloadSource;
  directions?: readonly string[];
  excludedDirections?: readonly string[];
};

export type BusinessDirection = {
  name: string;
  icon: string;
  activities: readonly string[];
};
