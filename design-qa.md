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

---

# Design QA — Compact public listing media

**Comparison Target**

- Source visual truth: `/workspace/elon-media-asl-olcham-demo.html`
- Supporting user reference: `/workspace/scratch/b413d71f5555/upload/f453f64c-ea57-41fc-8f1e-063760ee04d4.png`
- Implementation route: `https://v1656-comparison-web-listing-preview-188.up.railway.app`, public `E’lonlar` section
- Implementation screenshot: captured and inspected in Cloud Browser during the Railway preview; the browser shared-file mount was read-only, so the capture was not persisted into the repository.
- Intended viewport: desktop and mobile public-listing widths
- Source pixels: supporting screenshot is 510 × 189 px; the approved demo uses a fixed 172 × 129 CSS-px media surface.
- Implementation CSS size: listing preview and compact detail media are fixed at 172 × 129 CSS px.
- Density normalization: desktop CSS-pixel measurements were read from the rendered page.
- State: category selected, listing card visible, listing expanded, media viewer available.

**Full-view Comparison Evidence**

- The isolated Railway preview opened successfully in Cloud Browser.
- The selected `Uy-joy` category rendered six live listings. The first listing used its actual first image, with title, price, date and media count below it.
- Rendered desktop measurements: card 270 × 253 CSS px; card media 172 × 129 CSS px.
- The expanded first listing occupied the full 554 px result row and showed all eight media items in a wrapping grid. The first three measured media buttons were each exactly 172 × 129 CSS px.

**Focused Region Comparison Evidence**

- Card media crop, information-below-media order, media badge, wrapping detail gallery and map-address block were visually inspected in the live preview.
- Clicking the first image opened the `E'lon mediasi` dialog with a close button and enlarged image.
- The detail DOM contained six image buttons and two video buttons, matching the card's `6 rasm · 2 video` count.

**Findings**

- [P2] Mobile same-viewport capture remains unavailable
  Location: public listing card and expanded listing detail below the desktop breakpoint.
  Evidence: Cloud Browser exposed the desktop viewport but no supported viewport-resize control. Responsive CSS and component tests pass, but a mobile browser image was not captured.
  Impact: the desktop result is visually signed off; final mobile spacing remains a manual-preview check.
  Fix: open the Railway preview from a phone or responsive browser and confirm the 172 × 129 media surface does not overflow.

**Required Fidelity Surfaces**

- Fonts and typography: existing product typography rendered consistently with the surrounding E’lonlar UI.
- Spacing and layout rhythm: desktop fixed 172 × 129 media and information-below-media order are visually verified.
- Colors and visual tokens: existing product tokens are retained and rendered consistently.
- Image quality and asset fidelity: real listing media URLs render with `object-fit: cover`; cards without media retain the category fallback.
- Copy and content: title, price, address/time, media count, map address, coordinates, description, and actions are present.

**Primary Interactions Tested**

- Select a listing category.
- Render the first available photo on the compact listing card.
- Expand and collapse the listing card.
- Show every image/video in the expanded compact media grid.
- Open and close the media viewer.
- Show map address and coordinates.
- Contact and save actions remain wired.

**Console Errors Checked**

- Checked in Cloud Browser. No application console error was observed during category selection, card expansion, gallery rendering or media-viewer open/close. One browser-extension metadata error was unrelated to the app.

**Comparison History**

- Iteration 1: local preview capture blocked by Cloud Browser URL policy.
- Iteration 2: deployed the branch to an isolated Railway preview, inspected the live cards, verified exact media dimensions, expanded the first listing and opened the media viewer.

**Implementation Checklist**

- Capture mobile card and expanded detail.
- Verify mobile text wrapping and button stacking in a resizable browser or phone.
- Repeat comparison after any P0/P1/P2 visual fix.

**Follow-up Polish**

- A wider desktop card could be reconsidered only if the approved 270 px card feels too narrow after user review; no change is required by the current reference.

final result: blocked
