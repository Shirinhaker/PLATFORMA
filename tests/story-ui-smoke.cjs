const { chromium } = require('playwright');
const path = require('path');

const base = 'http://127.0.0.1:8090';
const uploadImage = path.resolve('../../upload/image-edit-target-3dbf591f5b88a709.png');

function managedStory(id, state, caption, createdOffset) {
  const now = Math.floor(Date.now() / 1000);
  return {
    id,
    owner_type:'user',
    owner_id:7,
    media_type:'image',
    media_url:`/api/stories/${id}/owner-media`,
    thumbnail_url:`/api/stories/${id}/owner-media?thumbnail=1`,
    caption,
    duration_seconds:0,
    created_at:now-createdOffset,
    expires_at:state === 'active' ? now+42000 : now-3600,
    state,
    view_count:id === 11 ? 5 : 2
  };
}

async function mockApi(page) {
  await page.addInitScript(() => localStorage.setItem('koprik_mobile_token', 'ui-test'));
  await page.route('**/api/**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname === '/api/me') {
      return route.fulfill({ json: { registered:true, role:'user', id:7, name:'Sinovchi', has_business:false, is_privileged:false } });
    }
    if (url.pathname === '/api/stories/feed') {
      return route.fulfill({ json: [{
        owner_type:'user', owner_id:8, name:'Dilnoza', avatar_url:'', is_own:false,
        is_followed:true, has_unseen:true, distance_km:0.8,
        stories:[{ id:1, media_type:'image', media_url:'/story-media/1', thumbnail_url:'/story-media/1', caption:'Yangi mahsulotlar keldi', duration_seconds:0, created_at:Math.floor(Date.now()/1000)-120, expires_at:Math.floor(Date.now()/1000)+85000, viewed:false }]
      }] });
    }
    if (url.pathname === '/api/stories/mine') {
      const state = url.searchParams.get('state') || 'active';
      const items = state === 'archived'
        ? [managedStory(12, 'archived', 'Kecha joylangan istoriya', 90000)]
        : [
            managedStory(11, 'active', 'Bugungi yangi istoriya', 300),
            managedStory(13, 'active', 'Ikkinchi faol istoriya', 900)
          ];
      return route.fulfill({ json:items });
    }
    if (/^\/api\/stories\/(11|12|13)\/owner-media$/.test(url.pathname)) {
      return route.fulfill({ path:uploadImage, contentType:'image/png' });
    }
    if (/^\/api\/stories\/(11|12|13)$/.test(url.pathname) && request.method() === 'DELETE') {
      return route.fulfill({ json:{ ok:true } });
    }
    if (url.pathname === '/api/stories' && request.method() === 'POST') {
      return route.fulfill({ json: { ok:true, story:{ id:2 } } });
    }
    if (url.pathname.endsWith('/view')) return route.fulfill({ json:{ ok:true, counted:true } });
    return route.fulfill({ json: [] });
  });
  await page.route('**/story-media/1', route => route.fulfill({ path: uploadImage, contentType:'image/png' }));
}

async function horizontalOverflow(page) {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
}

async function openPersonalStories(page) {
  await page.waitForFunction(() => typeof ME !== 'undefined' && ME.registered === true);
  await page.click('#cabBtn');
  await page.waitForSelector('.screen[data-screen="ucab"].active');
  await page.click('[data-screen="ucab"] [data-nav="ucab-stories"]');
  await page.waitForSelector('.screen[data-screen="ucab-stories"].active');
  await page.waitForSelector('#ucabStoriesList .my-story-card');
  await page.waitForSelector('#ucabStoriesList [data-my-story-thumb="11"] img');
}

async function verifyViewport(browser, viewport, screenshotName, interact) {
  const page = await browser.newPage({ viewport });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await mockApi(page);
  await page.goto(base, { waitUntil:'domcontentloaded' });
  await page.waitForSelector('[data-story-group="0"]', { timeout:10000 });
  if (interact) await interact(page);
  const overflow = await horizontalOverflow(page);
  if (overflow > 2) throw new Error(`Horizontal overflow: ${overflow}px at ${viewport.width}px`);
  await page.screenshot({ path:path.resolve('artifacts', screenshotName), fullPage:true });
  const relevantErrors = errors.filter(message => !message.includes('Leaflet') && !message.includes('Mapbox'));
  if (relevantErrors.length) throw new Error('Page errors: ' + relevantErrors.join(' | '));
  await page.close();
}

(async () => {
  const executablePath = process.env.PLAYWRIGHT_CHROMIUM_PATH || undefined;
  const browser = await chromium.launch({ headless:true, executablePath });
  await verifyViewport(browser, { width:390, height:844 }, 'story-mobile.png', async page => {
    await openPersonalStories(page);
    await page.click('#ucabStoriesList [data-my-story-open="11"]');
    await page.waitForSelector('#storyViewer.on');
    await page.click('#storyViewerClose');
    await page.waitForSelector('#storyViewer:not(.on)');
    await page.click('#ucabStoriesTabs [data-my-story-state="archived"]');
    await page.waitForSelector('#ucabStoriesList [data-my-story-id="12"]');
    await page.waitForSelector('#ucabStoriesList [data-my-story-thumb="12"] img');
  });
  await verifyViewport(browser, { width:820, height:1180 }, 'story-tablet.png', async page => {
    await openPersonalStories(page);
    const cards = await page.locator('#ucabStoriesList .my-story-card').evaluateAll(nodes => nodes.slice(0, 2).map(node => {
      const rect = node.getBoundingClientRect();
      return { x:rect.x, y:rect.y, width:rect.width };
    }));
    if (cards.length !== 2 || Math.abs(cards[0].y - cards[1].y) > 2 || cards[1].x <= cards[0].x) {
      throw new Error('Tablet stories grid is not rendered in two columns.');
    }
  });
  await browser.close();
  console.log('Story UI smoke test passed for mobile and tablet.');
})().catch(error => { console.error(error); process.exit(1); });
