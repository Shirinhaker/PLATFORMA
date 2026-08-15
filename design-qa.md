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
- Implementation route: local Vite app, public `E’lonlar` section
- Implementation screenshot: unavailable
- Intended viewport: desktop and mobile public-listing widths
- Source pixels: supporting screenshot is 510 × 189 px; the approved demo uses a fixed 172 × 129 CSS-px media surface.
- Implementation CSS size: listing preview and compact detail media are fixed at 172 × 129 CSS px.
- Density normalization: not performed because a browser-rendered implementation capture could not be obtained.
- State: category selected, listing card visible, listing expanded, media viewer available.

**Full-view Comparison Evidence**

- The source visual was available, but the cloud browser rejected the local preview URL with `ERR_BLOCKED_BY_CLIENT`.
- A visual, same-viewport comparison could therefore not be completed.

**Focused Region Comparison Evidence**

- Not available for the same blocker. Code and component tests confirm the fixed media dimensions, content order, media count, expanded media collection, map-address data, and viewer trigger, but these are not substitutes for browser-rendered visual evidence.

**Findings**

- [P1] Browser-rendered fidelity is unverified
  Location: public listing card and expanded listing detail.
  Evidence: the source is available, while the implementation screenshot could not be captured from the cloud browser.
  Impact: spacing, wrapping, image crop, and responsive polish cannot be signed off visually.
  Fix: open the local preview in an accessible browser surface, capture the same card and expanded state at desktop and mobile widths, then compare both captures against the approved source.

**Required Fidelity Surfaces**

- Fonts and typography: code uses the existing product typography tokens; visual matching remains unverified.
- Spacing and layout rhythm: fixed 172 × 129 media and information-below-media order are implemented; visual matching remains unverified.
- Colors and visual tokens: existing product tokens are retained; visual matching remains unverified.
- Image quality and asset fidelity: real listing media URLs are used with `object-fit: cover`; crop quality remains visually unverified.
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

- Not checked in a browser because the local preview could not be opened by the cloud browser.

**Comparison History**

- Iteration 1: source available; implementation capture blocked before visual comparison. No visual fixes were claimed from this pass.

**Implementation Checklist**

- Capture desktop card and expanded detail.
- Capture mobile card and expanded detail.
- Verify exact 172 × 129 media surfaces, text wrapping, card width, media wrapping, and button stacking.
- Check browser console and keyboard/media-viewer behavior.
- Repeat comparison after any P0/P1/P2 visual fix.

**Follow-up Polish**

- None classified until browser-rendered comparison is available.

final result: blocked
