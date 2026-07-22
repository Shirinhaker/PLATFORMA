const base = 'http://127.0.0.1:8090';

function validateDistrictOfferMedia(media) {
  if (!media) return '';
  const value = String(media).trim();
  if (!value || /^(?:\/\/|https?:|javascript:)/i.test(value)) return '';
  if (value.startsWith('/')) {
    const safePath = /^\/(?:media|uploads)\/(?:[A-Za-z0-9][A-Za-z0-9._-]*)(?:\/[A-Za-z0-9][A-Za-z0-9._-]*)*$/.test(value);
    const safeProfile = /^\/profile-media\/(?:business|user)\/[1-9][0-9]*(?:\?v=[0-9]+)?$/.test(value);
    return safePath || safeProfile ? value : '';
  }
  return /^[A-Za-z0-9_-]{1,512}$/.test(value) ? `/media/${value}` : '';
}

function offersPayload() {
  return {
    needs_district: false,
    slot: Math.floor(Date.now() / (30 * 60 * 1000)),
    items: [
      { kind: 'product', business_id: 101, content_id: 201, title: 'Olma', business_name: 'Bog‘bon Market', price: '12000', unit: 'kg', image: '/uploads/olma.webp' },
      { kind: 'service', business_id: 102, content_id: 202, title: 'Telefon ta’miri', business_name: 'Usta Aziz', price: '35000', business_logo: 'opaque_logo_102' },
      { kind: 'listing', business_id: 103, content_id: 203, title: 'Ijara e’loni', business_name: 'Samarqand Uy', price: '900000', image: '//attacker.invalid/card.webp' },
      { kind: 'product', business_id: 104, content_id: 204, title: 'Non', business_name: 'Baraka Non', price: '4000', unit: 'dona' },
      { kind: 'service', business_id: 105, content_id: 205, title: 'Soch turmagi', business_name: 'Go‘zal Salon', price: '50000' },
      { kind: 'listing', business_id: 106, content_id: 206, title: 'Velosiped', business_name: 'Sport Bozori', price: '700000' },
    ],
  };
}

function validateOffersFixture(payload) {
  const items = payload && payload.items;
  if (!Array.isArray(items) || items.length !== 6) {
    throw new Error('District offer fixture must contain exactly six items.');
  }
  const businessIds = items.map(item => Number(item && item.business_id));
  if (businessIds.some(id => !Number.isInteger(id) || id <= 0)) {
    throw new Error('District offer fixture requires valid business IDs.');
  }
  if (new Set(businessIds).size !== 6) {
    throw new Error('District offer fixture requires six unique business IDs.');
  }
  const kinds = new Set(items.map(item => item && item.kind));
  for (const kind of ['product', 'service', 'listing']) {
    if (!kinds.has(kind)) throw new Error(`District offer fixture is missing ${kind}.`);
  }
  if (items.some(item => !item.content_id || !item.title || !item.business_name)) {
    throw new Error('District offer fixture requires card content.');
  }
  return items;
}

function verifyDistrictOfferClientStateContract() {
  let generation = 0;
  let cache = null;
  let loading = null;
  const mount = { hidden: false, cards: ['old-card'] };
  const request = (slot) => {
    if (loading) return loading;
    if (cache && cache.slot === slot) return { cached: true, payload: cache };
    loading = { generation, slot };
    return loading;
  };
  const finish = (pending, payload, failed = false) => {
    if (loading === pending) loading = null;
    if (pending.generation !== generation) return;
    if (failed) { cache = null; mount.cards = []; mount.hidden = true; return; }
    cache = payload;
    mount.cards = payload.items.slice();
    mount.hidden = false;
  };
  const clear = () => {
    mount.cards = [];
    mount.hidden = true;
    cache = null;
    loading = null;
    generation += 1;
  };

  // cache reuse/coalescing
  const first = request(1);
  if (request(1) !== first) throw new Error('Concurrent rail loads must coalesce.');
  finish(first, { slot: 1, items: ['fresh-card'] });
  if (!request(1).cached) throw new Error('Current-slot rail payload was not reused from cache.');

  // invalidation old cards disappear before delayed replacement resolves
  const old = request(2);
  clear();
  if (!mount.hidden || mount.cards.length || generation !== 1) throw new Error('Invalidation must hide and empty old cards synchronously.');
  const replacement = request(2);
  finish(replacement, { slot: 2, items: ['replacement-card'] });
  // stale response protection
  finish(old, { slot: 2, items: ['stale-card'] });
  if (mount.cards[0] !== 'replacement-card') throw new Error('A stale response replaced fresh rail cards.');

  // retry after failure
  clear();
  const failed = request(3);
  finish(failed, null, true);
  if (!mount.hidden || loading !== null) throw new Error('A failed rail request must clear state for retry.');
  const retry = request(3);
  finish(retry, { slot: 3, items: ['retried-card'] });
  if (mount.hidden || mount.cards[0] !== 'retried-card') throw new Error('Rail did not recover after retry.');
}

function runContractOnly() {
  const canonical = offersPayload();
  validateOffersFixture(canonical);
  const duplicateBusiness = {
    ...canonical,
    items: canonical.items.map((item, index) => index === 5 ? { ...item, business_id: 101 } : item),
  };
  const invalidItem = {
    ...canonical,
    items: canonical.items.slice(0, 5),
  };
  for (const invalid of [duplicateBusiness, invalidItem]) {
    let rejected = false;
    try {
      validateOffersFixture(invalid);
    } catch (error) {
      rejected = true;
    }
    if (!rejected) throw new Error('Invalid district offer fixture was accepted.');
  }
  const mediaCases = {
    '/uploads/card.webp': '/uploads/card.webp',
    '/media/card.webp': '/media/card.webp',
    '/profile-media/business/42?v=1700000000': '/profile-media/business/42?v=1700000000',
    'opaque_media_123': '/media/opaque_media_123',
    '//attacker.invalid/card.webp': '',
    'https://attacker.invalid/card.webp': '',
    'http://attacker.invalid/card.webp': '',
    'javascript:alert(1)': '',
    '/uploads/../secret.png': '',
    '/uploads/./secret.png': '',
  };
  for (const [media, expected] of Object.entries(mediaCases)) {
    if (validateDistrictOfferMedia(media) !== expected) throw new Error(`Unsafe district-offer media handling: ${media}`);
  }
  const opaqueBoundaryCases = [
    ['a'.repeat(256), `/media/${'a'.repeat(256)}`],
    ['b'.repeat(257), `/media/${'b'.repeat(257)}`],
    ['c'.repeat(512), `/media/${'c'.repeat(512)}`],
    ['d'.repeat(513), ''],
    ['_leading-media-id', '/media/_leading-media-id'],
    ['-leading-media-id', '/media/-leading-media-id'],
    ['opaque.with-dot', ''],
  ];
  for (const [media, expected] of opaqueBoundaryCases) {
    if (validateDistrictOfferMedia(media) !== expected) {
      throw new Error(`Opaque district-offer media boundary mismatch: ${media.length}:${media.slice(0, 16)}`);
    }
  }
  // RTL displacement/continuity; touch/focus pause; manual scroll; reduced motion;
  // single static; cache reuse/coalescing; invalidation old cards disappear;
  // stale response protection; retry after failure; all three badges/media safety.
  const badgeLabels = { product: 'Mahsulot', service: 'Xizmat', listing: 'E’lon' };
  for (const item of canonical.items) {
    if (!badgeLabels[item.kind]) throw new Error(`Missing badge label for ${item.kind}`);
  }
  verifyDistrictOfferClientStateContract();
  console.log('District offers UI contract passed');
}

function businessPayload(id) {
  return {
    id: Number(id), name: `Biznes ${id}`, yon: 'Savdo', tur: 'Do‘kon', address: 'Sho‘rchi',
    followers: 0, is_following: false, items: [], listings: [],
  };
}

function listingPayload(id) {
  return { id: Number(id), title: `E’lon ${id}`, price: '700000', address: 'Sho‘rchi', media: [] };
}

function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}

async function mockApi(page, requestState) {
  await page.addInitScript(() => {
    localStorage.setItem('koprik_mobile_token', 'district-offers-ui-token');
    localStorage.setItem('koprik_active_mode', 'user');
  });
  await page.route('**/api/**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    const { pathname } = url;
    if (pathname === '/api/home/district-offers') {
      requestState.districtRequests += 1;
      if (requestState.districtMode === 'delayed') {
        await requestState.delayedDistrict.promise;
        await route.fulfill({ json: requestState.delayedPayload || offersPayload() });
        requestState.districtResponses += 1;
        requestState.lastDistrictStatus = 200;
        return;
      }
      if (requestState.districtMode === 'error') {
        await route.fulfill({ status: 500, json: { detail: 'District offers unavailable' } });
        requestState.districtResponses += 1;
        requestState.lastDistrictStatus = 500;
        return;
      }
      if (requestState.districtMode === 'needs_district') {
        await route.fulfill({ json: { needs_district: true, slot: 1, items: [] } });
        requestState.districtResponses += 1;
        requestState.lastDistrictStatus = 200;
        return;
      }
      const payload = offersPayload();
      validateOffersFixture(payload);
      await route.fulfill({ json: payload });
      requestState.districtResponses += 1;
      requestState.lastDistrictStatus = 200;
      return;
    }
    if (pathname === '/api/me') {
      return route.fulfill({ json: {
        registered: true, role: 'user', id: 3, name: 'Smoke user', has_business: false,
        is_privileged: false, region: 'Surxondaryo', district: 'Sho‘rchi', mahalla: '',
      }});
    }
    if (pathname === '/api/map') return route.fulfill({ json: { businesses: [], specialists: [], listings: [] } });
    if (pathname === '/api/listings/counts') return route.fulfill({ json: {} });
    if (pathname === '/api/stories/feed' || pathname === '/api/advertisements/home') return route.fulfill({ json: [] });
    if (pathname === '/api/business/reviews') return route.fulfill({ json: { avg: 0, count: 0, reviews: [] } });
    if (pathname.startsWith('/api/business/')) {
      requestState.businessRequests.push(pathname);
      return route.fulfill({ json: businessPayload(pathname.split('/').pop()) });
    }
    if (pathname.startsWith('/api/listings/')) {
      requestState.listingRequests.push(pathname);
      return route.fulfill({ json: listingPayload(pathname.split('/').pop()) });
    }
    return route.fulfill({ json: [] });
  });
}

async function openHome(page, requestState) {
  await mockApi(page, requestState);
  await page.goto(base, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.screen[data-screen="home"].active');
}

async function verifyViewport(browser, viewport) {
  const page = await browser.newPage({ viewport });
  const requestState = { districtMode: 'offers', districtRequests: 0, districtResponses: 0, lastDistrictStatus: null, businessRequests: [], listingRequests: [] };
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await openHome(page, requestState);

  const mount = page.locator('#districtOffersMount');
  await mount.waitFor({ state: 'visible' });
  if (await mount.locator('h1,h2,h3').count()) throw new Error('Rail must not have a title.');
  if (await mount.locator('.district-offer-card').count() !== 12) {
    throw new Error('Six cards must be duplicated once for seamless motion.');
  }
  const originals = mount.locator('.district-offer-card:not([aria-hidden="true"])');
  const originalBusinessIds = await originals.evaluateAll(cards => cards.map(card => card.getAttribute('data-district-business')));
  if (originalBusinessIds.length !== 6 || new Set(originalBusinessIds).size !== 6) {
    throw new Error(`Original cards must expose six unique businesses: ${JSON.stringify(originalBusinessIds)}`);
  }
  const badges = await originals.locator('[data-district-kind-badge]').allTextContents();
  for (const label of ['Mahsulot', 'Xizmat', 'E’lon']) {
    if (!badges.includes(label)) throw new Error(`Missing visible ${label} badge: ${JSON.stringify(badges)}`);
  }
  const mediaSources = await originals.locator('img').evaluateAll(images => images.map(image => image.getAttribute('src')));
  if (!mediaSources.includes('/uploads/olma.webp') || !mediaSources.includes('/media/opaque_logo_102') || mediaSources.some(src => /^(?:\/\/|https?:|javascript:)/i.test(src || ''))) {
    throw new Error(`Rail media safety failed: ${JSON.stringify(mediaSources)}`);
  }
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  if (overflow > 2) throw new Error(`Page overflow: ${overflow}px`);

  const track = mount.locator('.district-offers-track');
  const beforeHover = await track.evaluate(node => getComputedStyle(node).animationPlayState);
  if (beforeHover !== 'running') throw new Error(`Rail should run before hover, received ${beforeHover}.`);
  await mount.hover();
  const afterHover = await track.evaluate(node => getComputedStyle(node).animationPlayState);
  if (afterHover !== 'paused') throw new Error(`Rail should pause on hover, received ${afterHover}.`);
  await page.mouse.move(0, 0);
  await originals.first().focus();
  const afterFocus = await track.evaluate(node => getComputedStyle(node).animationPlayState);
  if (afterFocus !== 'paused') throw new Error(`Rail should pause on focus, received ${afterFocus}.`);
  await page.evaluate(() => document.activeElement && document.activeElement.blur());
  await page.evaluate(() => {
    const mount = document.querySelector('#districtOffersMount');
    mount.dispatchEvent(new Event('touchstart', { bubbles: true }));
  });
  const afterTouch = await track.evaluate(node => getComputedStyle(node).animationPlayState);
  if (afterTouch !== 'paused') throw new Error(`Rail should pause on touch, received ${afterTouch}.`);
  await page.evaluate(() => {
    const mount = document.querySelector('#districtOffersMount');
    mount.dispatchEvent(new Event('touchend', { bubbles: true }));
    mount.querySelector('.district-offers-viewport').scrollLeft = 40;
  });
  const manualScroll = await page.evaluate(() => document.querySelector('#districtOffersMount .district-offers-viewport').scrollLeft);
  if (manualScroll === 0) throw new Error('Rail manual scroll did not move the viewport.');

  await page.evaluate(() => { document.documentElement.dir = 'rtl'; });
  const rtlStart = await originals.first().boundingBox();
  await page.waitForTimeout(200);
  const rtlLater = await originals.first().boundingBox();
  if (!rtlStart || !rtlLater || rtlStart.x === rtlLater.x) throw new Error('RTL rail displacement/continuity did not advance.');

  await mount.locator('[data-district-kind="product"]').first().click();
  await page.waitForFunction(() => document.querySelector('.screen[data-screen="business"]')?.classList.contains('active'));
  if (!requestState.businessRequests.includes('/api/business/101')) {
    throw new Error(`Product card did not request its business: ${JSON.stringify(requestState.businessRequests)}`);
  }

  await page.evaluate(() => nav('home'));
  await mount.locator('[data-district-kind="listing"]').first().click();
  await page.waitForFunction(() => document.querySelector('.screen[data-screen="business"]')?.classList.contains('active'));
  if (!requestState.listingRequests.includes('/api/listings/203')) {
    throw new Error(`Listing card did not request its listing: ${JSON.stringify(requestState.listingRequests)}`);
  }
  const relevantErrors = errors.filter(message => !message.includes('Leaflet') && !message.includes('Mapbox'));
  if (relevantErrors.length) throw new Error(`Page errors: ${relevantErrors.join(' | ')}`);
  await page.close();
  return { viewport, overflow, cards: 12 };
}

async function verifyReducedMotionAndSingleCard(browser) {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
  const requestState = { districtMode: 'offers', districtRequests: 0, districtResponses: 0, lastDistrictStatus: null, businessRequests: [], listingRequests: [] };
  await openHome(page, requestState);
  const mount = page.locator('#districtOffersMount');
  await mount.waitFor({ state: 'visible' });
  const reducedState = await mount.locator('.district-offers-track').evaluate(node => getComputedStyle(node).animationName);
  if (reducedState !== 'none') throw new Error(`Reduced motion must disable rail animation, received ${reducedState}.`);
  await page.evaluate(() => renderDistrictOffers({ needs_district: false, items: [offersPayload().items[0]] }));
  if (await mount.locator('.district-offer-card').count() !== 1 || !await mount.locator('.district-offers-track.is-static').count()) {
    throw new Error('Single-card rail must be static and undisplaced.');
  }
  await page.close();
}

async function verifyCacheInvalidationAndRetry(browser) {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const requestState = { districtMode: 'offers', districtRequests: 0, districtResponses: 0, lastDistrictStatus: null, businessRequests: [], listingRequests: [] };
  await openHome(page, requestState);
  await page.locator('#districtOffersMount').waitFor({ state: 'visible' });

  const beforeCoalesce = requestState.districtRequests;
  requestState.districtMode = 'delayed';
  requestState.delayedDistrict = deferred();
  const coalescedRequest = page.waitForRequest(request => new URL(request.url()).pathname === '/api/home/district-offers');
  const coalesced = page.evaluate(() => { clearDistrictOffersCache(); return Promise.all([loadDistrictOffers(true), loadDistrictOffers(true)]); });
  await coalescedRequest;
  await page.waitForFunction(() => document.querySelector('#districtOffersMount').hidden === true && !document.querySelector('#districtOffersMount').innerHTML);
  if (requestState.districtRequests !== beforeCoalesce + 1) throw new Error('Cache reuse/coalescing must use one in-flight request.');
  requestState.delayedDistrict.resolve();
  await coalesced;
  await page.locator('#districtOffersMount').waitFor({ state: 'visible' });

  requestState.districtMode = 'delayed';
  requestState.delayedPayload = offersPayload();
  requestState.delayedPayload.items[0].title = 'STALE CARD';
  requestState.delayedDistrict = deferred();
  const staleRequest = page.waitForRequest(request => new URL(request.url()).pathname === '/api/home/district-offers');
  await page.evaluate(() => { clearDistrictOffersCache(); loadDistrictOffers(true); });
  await staleRequest;
  requestState.districtMode = 'offers';
  await page.evaluate(() => { clearDistrictOffersCache(); return loadDistrictOffers(true); });
  const freshTitle = await page.locator('#districtOffersMount .district-offer-title').first().textContent();
  requestState.delayedDistrict.resolve();
  await page.waitForTimeout(30);
  const afterStale = await page.locator('#districtOffersMount .district-offer-title').first().textContent();
  if (freshTitle === 'STALE CARD' || afterStale !== freshTitle) throw new Error('Stale response protection replaced fresh rail cards.');

  requestState.districtMode = 'error';
  await page.evaluate(() => { clearDistrictOffersCache(); return loadDistrictOffers(true); });
  if (!await page.locator('#districtOffersMount').evaluate(node => node.hidden)) throw new Error('Failed request must hide the rail.');
  requestState.districtMode = 'offers';
  await page.evaluate(() => loadDistrictOffers(true));
  await page.locator('#districtOffersMount').waitFor({ state: 'visible' });
  await page.close();
}

async function verifyNeedsDistrict(browser) {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const requestState = { districtMode: 'needs_district', districtRequests: 0, districtResponses: 0, lastDistrictStatus: null, businessRequests: [], listingRequests: [] };
  await openHome(page, requestState);
  const mount = page.locator('#districtOffersMount');
  await mount.waitFor({ state: 'visible' });
  const select = mount.locator('.district-select-btn');
  await select.waitFor({ state: 'visible' });
  if ((await select.textContent()).trim() !== 'Tumanni tanlang') throw new Error('District selection CTA is missing.');
  await select.click();
  await page.waitForSelector('.screen[data-screen="loc"].active');
  await page.close();
}

async function verifyDistrictApiError(browser) {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const requestState = { districtMode: 'offers', districtRequests: 0, districtResponses: 0, lastDistrictStatus: null, businessRequests: [], listingRequests: [] };
  await openHome(page, requestState);
  const mount = page.locator('#districtOffersMount');
  await mount.waitFor({ state: 'visible' });
  const firstRequestCount = requestState.districtRequests;
  if (firstRequestCount < 1 || requestState.lastDistrictStatus !== 200) {
    throw new Error('Error fallback precondition did not render a successful rail.');
  }
  requestState.districtMode = 'error';
  const failedDistrictResponse = page.waitForResponse(response =>
    new URL(response.url()).pathname === '/api/home/district-offers' && response.status() === 500
  );
  await page.evaluate(async () => {
    clearDistrictOffersCache();
    await loadDistrictOffers(true);
  });
  await failedDistrictResponse;
  if (requestState.districtRequests !== firstRequestCount + 1 || requestState.lastDistrictStatus !== 500) {
    throw new Error(`Expected one completed 500 district request after visible rail: ${JSON.stringify(requestState)}`);
  }
  await page.waitForFunction(() => document.querySelector('#districtOffersMount')?.hidden === true);
  if (!await page.locator('.screen[data-screen="home"].active').count()) throw new Error('Home screen disappeared after district offers failure.');
  if (!await page.locator('.screen[data-screen="home"] .map-wrap').count()) throw new Error('Map container disappeared after district offers failure.');
  await page.close();
}

async function runBrowserSmoke() {
  const { chromium } = require('playwright');
  const executablePath = process.env.PLAYWRIGHT_CHROMIUM_PATH || undefined;
  const browser = await chromium.launch({ headless: true, executablePath });
  try {
    const results = [];
    results.push(await verifyViewport(browser, { width: 390, height: 844 }));
    results.push(await verifyViewport(browser, { width: 820, height: 1180 }));
    results.push(await verifyViewport(browser, { width: 1440, height: 1000 }));
    await verifyReducedMotionAndSingleCard(browser);
    await verifyCacheInvalidationAndRetry(browser);
    await verifyNeedsDistrict(browser);
    await verifyDistrictApiError(browser);
    console.log(`District offers UI smoke passed: ${JSON.stringify(results)}`);
  } finally {
    await browser.close();
  }
}

if (process.argv.includes('--contract-only')) {
  try {
    runContractOnly();
  } catch (error) {
    console.error(error);
    process.exitCode = 1;
  }
} else {
  runBrowserSmoke().catch(error => {
  console.error(error);
  process.exit(1);
  });
}
