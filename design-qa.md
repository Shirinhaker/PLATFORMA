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
- Current user reference: `/workspace/scratch/b413d71f5555/upload/919b9db1-5772-4912-a71a-efd50465367a.png`
- Implementation route: `https://v1656-comparison-web-listing-preview-188.up.railway.app`, public `E’lonlar` section
- Implementation screenshot: captured in Cloud Browser and compared with the reference in the same comparison input; the browser shared-file mount was read-only, so the capture was not persisted into the repository.
- Intended viewport: desktop and mobile public-listing widths
- Source pixels: current reference is 192 × 216 px and shows the compact card without the previous empty right side.
- Implementation CSS size: listing preview and compact detail media are fixed at 172 × 129 CSS px.
- Density normalization: desktop CSS-pixel measurements were read from the rendered page.
- State: `Uy-joy` selected; compact card visible; first listing expanded; horizontal media strip scrolled to its final video; Leaflet map rendered; media viewer opened and closed.

**Full-view Comparison Evidence**

- The isolated Railway preview opened successfully in Cloud Browser.
- The selected `Uy-joy` category rendered six live listings in compact 192 px columns. The previous 270 px card width and its empty right side are gone.
- The first listing uses its actual first image and keeps title, price, date and media count below the 172 × 129 media surface, matching the reference hierarchy.
- The opened listing occupies the complete result row. Its eight media items stay in one 172 × 129 horizontal strip rather than wrapping vertically.
- A working Leaflet/OpenStreetMap map with the listing marker renders directly below the media strip. Price, map-address text, description and actions follow below the map.

**Focused Region Comparison Evidence**

- The 192 × 216 px user reference and the final Cloud Browser capture were emitted together and visually compared.
- Card width, 172 × 129 image crop, rounded corners, information order, media badge and compact density match the source intent.
- Clicking the final video in the horizontal strip automatically scrolled it into view and opened the `E'lon mediasi` dialog, proving the off-screen media remains reachable.
- The earlier iframe map failed WebGL in Cloud Browser. It was replaced with the product's existing Leaflet map approach; the final capture shows map tiles and the bundled blue marker asset correctly.

**Findings**

- [P2] Mobile same-viewport capture remains unavailable
  Location: public listing card and expanded listing detail below the desktop breakpoint.
  Evidence: Cloud Browser exposed the desktop viewport but no supported viewport-resize control. Responsive CSS and component tests pass, but a mobile browser image was not captured.
  Impact: the desktop result is visually signed off; final mobile spacing remains a manual-preview check.
  Fix: open the Railway preview from a phone or responsive browser and confirm the 172 × 129 media surface does not overflow.

**Required Fidelity Surfaces**

- Fonts and typography: existing product typography rendered consistently with the surrounding E’lonlar UI.
- Spacing and layout rhythm: the compact 192 px card removes the unwanted empty right side; the desktop 172 × 129 media, horizontal detail strip, map and information order are visually verified.
- Colors and visual tokens: existing product tokens are retained and rendered consistently.
- Image quality and asset fidelity: real listing media URLs render with `object-fit: cover`; the Leaflet marker uses the bundled library image assets rather than a placeholder.
- Copy and content: title, price, address/time, media count, interactive map, map address, coordinates, description and actions are present in the requested order.

**Primary Interactions Tested**

- Select a listing category.
- Render the first available photo on the compact listing card.
- Expand and collapse the listing card.
- Reach the final video in the horizontal media strip.
- Open and close the final media item in the viewer.
- Render the Leaflet map, marker, map address and coordinates.
- Contact and save actions remain wired.

**Console Errors Checked**

- The first iframe-map iteration produced a WebGL error and was removed.
- The final Leaflet iteration produced no new application error during category selection, card expansion, map rendering or final-video viewer open/close. Remaining log entries were historical iframe errors and unrelated browser-extension metadata errors.

**Comparison History**

- Iteration 1: local preview capture blocked by Cloud Browser URL policy.
- Iteration 2: deployed the branch to an isolated Railway preview, inspected the live cards, verified exact media dimensions, expanded the first listing and opened the media viewer.
- Iteration 3: reduced card width from 270 to 192 px, changed compact detail media from wrapping to horizontal scrolling and placed a map before all other information.
- Iteration 4: found the OSM iframe WebGL failure in rendered QA, replaced it with Leaflet, then found and fixed the broken default marker by bundling Leaflet's real marker assets. The final Railway screenshot shows a working map and marker.

**Implementation Checklist**

- Capture mobile card and expanded detail.
- Verify mobile text wrapping and button stacking in a resizable browser or phone.
- Repeat comparison after any P0/P1/P2 visual fix.

**Follow-up Polish**

- None for the verified desktop target.

final result: blocked
