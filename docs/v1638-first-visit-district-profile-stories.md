# v1638 — First-visit district and profile stories

## Implemented behavior

- A first-time visitor must choose a district before the home screen opens.
- The selected district is stored in the browser and reused on later visits.
- A signed-in user without a saved server-side district can sync the browser selection to the profile.
- The home map shows active Plus and Pro business markers from the selected district.
- The home offer rail shows eligible products, services, and listings from that district.
- Search temporarily replaces district markers with search-result markers.
- Closing search restores the selected district's markers.
- The old distance control and `15 km gacha` text were removed.
- Stories were removed from the home screen.
- Stories are loaded inside public user and business profiles.
- An ordinary user's district and region are not returned or rendered on the public profile.

## API changes

- `GET /api/map?district=<district>`
- `GET /api/home/district-offers?district=<district>`

Both endpoints are available for the public home screen. Marker responses do not expose the
selected user's district.

## Build flags

- `first_visit_district_v1638`
- `district_paid_discovery_v1638`
- `profile_only_stories_v1638`

## Verification

- Inline JavaScript syntax: passed.
- District-offers frontend contract: passed.
- Python test suite: `217 / 217` passed.
- Browser-rendered smoke test could not run because the Playwright Chromium executable is
  not installed in the environment.

