const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const base = 'http://127.0.0.1:8090';
const outputDir = '/tmp/koprik-v1612-qa';
fs.mkdirSync(outputDir, { recursive: true });

function subscriptionPayload(planCode = 'free') {
  const now = Math.floor(Date.now() / 1000);
  const paid = planCode !== 'free';
  return {
    current: {
      id: paid ? 17 : null,
      business_id: 9,
      plan_code: planCode,
      duration_months: paid ? 3 : 0,
      starts_at: paid ? now : 0,
      expires_at: paid ? now + 90 * 86400 : 0,
      status: 'active',
      is_demo: paid,
      created_at: paid ? now : 0,
      is_virtual: !paid,
    },
    features: {
      unlimited_items: true,
      home_nearby_eligible: paid,
      map_marker_eligible: planCode === 'pro',
    },
    history: [],
    plans: [],
    durations: [1, 3, 12],
    demo_mode: true,
  };
}

async function mockApi(page, requestState) {
  await page.addInitScript(() => {
    localStorage.setItem('koprik_mobile_token', 'subscription-ui-token');
    localStorage.setItem('koprik_active_mode', 'business');
  });
  await page.route('**/api/**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname === '/api/me') {
      return route.fulfill({ json: {
        registered: true,
        role: 'business',
        id: 3,
        name: 'Ko‘prik egasi',
        has_business: true,
        is_privileged: false,
        business: { id: 9, name: 'Ko‘prik Market', yon: 'Savdo', tur: 'Do‘kon', status: 'active' },
      }});
    }
    if (url.pathname === '/api/profile') {
      return route.fulfill({ json: { id: 3, role: 'business', name: 'Ko‘prik egasi', business_followers: 12, business_following: 4 }});
    }
    if (url.pathname === '/api/business/subscription' && request.method() === 'GET') {
      return route.fulfill({ json: subscriptionPayload(requestState.planCode) });
    }
    if (url.pathname === '/api/business/subscription/demo-activate' && request.method() === 'POST') {
      const body = request.postDataJSON();
      requestState.posted = body;
      requestState.planCode = body.plan_code;
      return route.fulfill({ json: { ok: true, ...subscriptionPayload(requestState.planCode) } });
    }
    if (url.pathname === '/api/stories/feed') return route.fulfill({ json: [] });
    if (url.pathname === '/api/advertisements/home') return route.fulfill({ json: [] });
    if (url.pathname === '/api/map') return route.fulfill({ json: [] });
    if (url.pathname === '/api/business/reviews') return route.fulfill({ json: { avg: 0, count: 0, reviews: [] } });
    if (url.pathname.includes('/badges')) return route.fulfill({ json: {} });
    return route.fulfill({ json: [] });
  });
}

async function verifyViewport(browser, viewport, screenshotName) {
  const page = await browser.newPage({ viewport });
  const requestState = { planCode: 'free', posted: null };
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await mockApi(page, requestState);
  await page.goto(base, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => typeof ME !== 'undefined' && ME.registered === true && ME.has_business === true);
  if ((await page.title()) !== 'Ko‘prik') throw new Error('Page title is not Ko‘prik.');
  await page.click('#cabBtn');
  await page.waitForSelector('.screen[data-screen="cabinet"].active');
  await page.click('[data-screen="cabinet"] [data-nav="cab-subscriptions"]');
  await page.waitForSelector('.screen[data-screen="cab-subscriptions"].active');
  await page.waitForSelector('#businessSubscriptionContent:not([hidden])');
  const initialPlan = (await page.locator('#businessSubscriptionCurrent .subscription-current-name').textContent()).trim();
  if (initialPlan !== 'Bepul') throw new Error(`Default plan is ${initialPlan}, expected Bepul.`);
  await page.click('[data-screen="cab-subscriptions"] [data-sub-duration="3"]');
  await page.click('[data-screen="cab-subscriptions"] [data-sub-activate="plus"]');
  await page.waitForFunction(() => document.querySelector('#businessSubscriptionCurrent .subscription-current-name')?.textContent.trim() === 'Plus');
  if (!requestState.posted || requestState.posted.plan_code !== 'plus' || requestState.posted.duration_months !== 3) {
    throw new Error(`Unexpected activation payload: ${JSON.stringify(requestState.posted)}`);
  }
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  if (overflow > 2) throw new Error(`Horizontal overflow: ${overflow}px at ${viewport.width}px.`);
  const cards = await page.locator('.subscription-plan-card').count();
  if (cards !== 3) throw new Error(`Expected 3 tariff cards, received ${cards}.`);
  const relevantErrors = errors.filter(message => !message.includes('Leaflet') && !message.includes('Mapbox'));
  if (relevantErrors.length) throw new Error(`Page errors: ${relevantErrors.join(' | ')}`);
  await page.screenshot({ path: path.join(outputDir, screenshotName), fullPage: false });
  await page.close();
  return { viewport, overflow, plan: requestState.planCode, cards };
}

(async () => {
  const executablePath = process.env.PLAYWRIGHT_CHROMIUM_PATH || undefined;
  const browser = await chromium.launch({ headless: true, executablePath });
  const results = [];
  results.push(await verifyViewport(browser, { width: 390, height: 844 }, 'subscription-mobile.png'));
  results.push(await verifyViewport(browser, { width: 820, height: 1180 }, 'subscription-tablet.png'));
  results.push(await verifyViewport(browser, { width: 1440, height: 1000 }, 'subscription-desktop.png'));
  await browser.close();
  console.log(`Subscription UI smoke passed: ${JSON.stringify(results)}`);
})().catch(error => {
  console.error(error);
  process.exit(1);
});
