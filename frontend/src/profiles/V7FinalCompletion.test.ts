import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const root = fileURLToPath(new URL("../..", import.meta.url));
const read = (path: string) => readFileSync(`${root}/${path}`, "utf8");

describe("V7 final completion contract", () => {
  it("does not route remaining business modules through the generic CabinetDataView", () => {
    const source = read("src/profiles/BusinessProfileV3.tsx");
    expect(source).not.toContain("<CabinetDataView");
    expect(source).toContain("BusinessSystemScreen");
    expect(source).toContain("BusinessAdministrationScreen");
    expect(source).toContain("BusinessDirectionScreen");
  });

  it("does not route ordinary cabinet data through the generic CabinetDataView", () => {
    const source = read("src/profiles/UserProfile.tsx");
    expect(source).not.toContain("<CabinetDataView");
    expect(source).toContain("UserCabinetScreen");
  });

  it("keeps a dedicated final V7 verification contract", () => {
    const source = read("../backend/app/legacy_migration/verify_v7_final.py");
    expect(source).toContain("business_module_coverage");
    expect(source).toContain("user_module_coverage");
    expect(source).toContain("extended_media_coverage");
    expect(source).toContain("nested_relation_coverage");
  });
});
