# Design QA — v1629 approved home and catalog UI

## References

- Desktop target: `upload/image-edit-target-5b68dd3053c827bf.png`
- Mobile target: `upload/01-IMG_20260722_131413_224.jpg`
- Compact search target: `upload/915bb757-57ba-4182-a477-1ea83f022976.png`
- Catalog target: `upload/8cbc87ca-b0ff-477e-ab39-bce8b72309e9.png`

## Automated checks

- Public header contract: passed.
- Compact home search contract: passed.
- Two-level catalog contract: passed.
- Responsive and hidden-scrollbar contract: passed.
- Inline JavaScript syntax parse: passed.
- Full Python suite: 183 tests passed.

## Browser comparison

The actual v1629 preview was started through the supported preview service, but the selected cloud browser rejected the refreshed preview under its URL safety policy. No alternate browser or policy workaround was used.

Because a fresh rendered screenshot of the installed v1629 source could not be captured, side-by-side visual comparison against the references is not complete.

**final result: blocked**

---

# Design QA — Taxi v1656 visual parity

final result: blocked

## Sources and implementation

- Taxi reference: `/workspace/scratch/d33bfb1af2e9/upload/bd694665-1da4-4820-a5f3-6ce73e013b36.png`
- Delivery reference: `/workspace/scratch/d33bfb1af2e9/upload/7caa8fa5-c4fd-4111-9553-cb9c0c4ba50b.png`
- Implementation: `frontend/src/taxi/TaxiCallV1656.tsx`
- Styles: `frontend/src/taxi/taxi-v1656.css`
- App wiring: `frontend/src/app/App.tsx`

## Target state

- Taxi reference viewport: 1206 × 909 px.
- Delivery reference viewport: 1067 × 909 px.
- Required state: form panel before map; selected destination and route; GPS action; district chip; Taxi and Delivery tab states; Delivery vehicle chips.

## Evidence

- Source screenshots inspected at original resolution.
- Monolith v1656 structure and values were mapped into the modular implementation: 920 px shell, 380 px desktop map, 280 px mobile map, panel-first DOM order, v1656 field/button geometry, GPS action, map overlays, and Delivery chips.
- Automated interaction coverage passed: `frontend/src/taxi/TaxiCallV1656.test.tsx` — 5/5 tests.
- Full frontend suite passed: 85 files, 515 tests.
- TypeScript and production build passed.
- Local Sites preview started at the required preview endpoint, but the selected cloud browser rejected the local preview with `net::ERR_BLOCKED_BY_CLIENT` on repeated fresh-tab attempts.

## Comparison history

1. Structural pass: moved the form panel above the map, restored self-contained v1656 styling, GPS control, district/map controls, origin marker, and Delivery vehicle chips.
2. Interaction pass: preserved manual-map selection against delayed GPS, while allowing the explicit GPS button to recenter; kept route drawing from moving the map.
3. Browser comparison: blocked before an implementation screenshot could be captured, so a same-viewport side-by-side pixel comparison could not be completed.

## Blocker

The required browser-rendered implementation evidence is unavailable because the selected cloud browser blocks the local preview endpoint. Automated and source-level checks pass, but this report cannot be marked `passed` without the browser screenshot comparison.
