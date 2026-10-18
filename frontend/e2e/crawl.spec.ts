import { expect, test, type Page } from '@playwright/test'

// Crawls the site the way a visitor does: in-app links only, never a reload. At every step:
// no console errors or uncaught exceptions, a non-empty <main>, and no leaked machine text.
const FORBIDDEN: RegExp[] = [/\bNone\b/, /\bnull\b/, /\bundefined\b/, /\bNaN\b/, /\[object/, /BAD_FORMAT/, /\{\}/, /<br>/]
const PILOT_ROUNDS = [1, 12, 17]

type Watch = { problems: string[] }

function watch(page: Page): Watch {
  const w: Watch = { problems: [] }
  page.on('pageerror', (e) => w.problems.push(`uncaught: ${e.message}`))
  page.on('console', (m) => {
    if (m.type() !== 'error') return
    const url = m.location().url ?? ''
    if (/fonts\.(googleapis|gstatic)\.com/.test(url)) return // blocked in some sandboxes; cosmetic
    w.problems.push(`console: ${m.text()} ${url}`)
  })
  return w
}

// Automation tools and some extensions wrap window.scrollTo and return a Promise. The app must not
// depend on the return value of browser APIs (REVIEW #1: a returned value became an effect cleanup).
async function hostileScrollTo(page: Page) {
  await page.addInitScript(() => {
    const original = window.scrollTo.bind(window) as (...a: unknown[]) => void
    ;(window as unknown as { scrollTo: unknown }).scrollTo = (...a: unknown[]) => { original(...a); return Promise.resolve() }
  })
}

async function settle(page: Page) {
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(150)
}

async function check(page: Page, w: Watch, label: string) {
  await settle(page)
  // a lazily loaded page shows a short "Loading" line first; give it time to fill, then judge it
  await expect.poll(async () => (await page.locator('main').innerText()).trim().length, { timeout: 10_000, message: `${label}: <main> is empty` }).toBeGreaterThan(40)
  const text = await page.locator('main').innerText()
  for (const re of FORBIDDEN) {
    const m = re.exec(text)
    const where = m ? text.slice(Math.max(0, m.index - 60), m.index + 60).replace(/\s+/g, ' ') : ''
    expect.soft(m ? `${m[0]} in "...${where}..."` : null, `${label}: leaked text`).toBeNull()
  }
  expect.soft(w.problems.splice(0), `${label}: console errors`).toEqual([])
  const [scroll, width] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth])
  expect.soft(scroll, `${label}: page scrolls sideways (${scroll}px content in a ${width}px window)`).toBeLessThanOrEqual(width + 1)
}

async function home(page: Page) {
  await page.getByRole('link', { name: 'Data Paddock home' }).click()
  await expect(page.locator('main')).toContainText('season')
}

async function openRound(page: Page, round: number) {
  await home(page)
  await page.locator(`main a[aria-label$=", round ${round}"]`).first().click()
  await expect(page.locator('h1')).not.toBeEmpty()
}

async function sessionTabs(page: Page) {
  const tabs = page.getByRole('tablist', { name: 'Session' }).locator('button:not([disabled])')
  await expect(tabs.first(), 'session tabs never appeared').toBeVisible() // never count an empty, still-loading list
  return tabs
}

test.beforeEach(async ({ page }) => {
  await hostileScrollTo(page)
})

test('every race and every session tab, via in-app links', async ({ page }) => {
  const w = watch(page)
  await page.goto('./')
  await check(page, w, 'home')
  const cards = page.locator('section[aria-label="Results"] a')
  const n = await cards.count()
  expect(n, 'completed races on the home page').toBeGreaterThan(0)
  for (let i = 0; i < n; i++) {
    if (i > 0) await home(page)
    const card = page.locator('section[aria-label="Results"] a').nth(i)
    const label = (await card.getAttribute('aria-label')) ?? `card ${i}`
    await card.click()
    await check(page, w, label)
    const tabs = await sessionTabs(page)
    const count = await tabs.count()
    for (let t = 0; t < count; t++) {
      const tab = (await sessionTabs(page)).nth(t)
      const name = (await tab.innerText()).trim()
      await tab.click()
      await check(page, w, `${label} / ${name}`)
    }
  }
})

for (const round of PILOT_ROUNDS) {
  test(`round ${round}: one driver, two drivers, every deep-dive tab, every session`, async ({ page }) => {
    const w = watch(page)
    await page.goto('./')
    await openRound(page, round)
    const tabs = await sessionTabs(page)
    const count = await tabs.count()
    expect(count, 'sessions on the pilot weekend').toBeGreaterThanOrEqual(4)
    for (let t = 0; t < count; t++) {
      const tab = (await sessionTabs(page)).nth(t)
      const name = (await tab.innerText()).trim()
      await tab.click()
      await settle(page)
      const rows = page.locator('section[aria-label="Classification"] tbody tr')
      await expect(rows.nth(10)).toBeVisible()
      await rows.nth(9).click()
      await check(page, w, `R${round} ${name}: one driver`)
      await rows.nth(10).click()
      await check(page, w, `R${round} ${name}: two drivers`)
      const dd = page.getByRole('region', { name: 'Deep dive' }).getByRole('tab')
      for (let k = 0; k < (await dd.count()); k++) {
        await dd.nth(k).click()
        await check(page, w, `R${round} ${name}: deep dive ${(await dd.nth(k).innerText()).trim()}`)
      }
      await page.getByRole('button', { name: 'Clear selection' }).click()
    }
  })
}

test('standings: drivers, constructors and season stories', async ({ page }) => {
  const w = watch(page)
  await page.goto('./')
  await check(page, w, 'home')
  await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Standings' }).click()
  await check(page, w, 'standings')
  await page.locator('section[aria-label="Driver standings"] tbody tr').nth(7).click()
  await check(page, w, 'standings: driver story')
  await page.getByRole('button', { name: 'Constructors' }).click()
  await check(page, w, 'standings: constructors')
  await page.locator('section[aria-label="Constructor standings"] tbody tr').nth(4).click()
  await check(page, w, 'standings: team story')
  await home(page)
  await check(page, w, 'back home')
})

test('unknown race and unknown route show a way back', async ({ page }) => {
  const w = watch(page)
  await page.goto('race/99999')
  await settle(page)
  await expect(page.locator('main')).toContainText(/not found/i)
  await expect(page.locator('main').getByRole('link', { name: /home|races/i }).first()).toBeVisible()
  await page.goto('no/such/page')
  await settle(page)
  await expect(page.locator('main')).toContainText(/not found/i)
  w.problems.length = 0
})

test('links shared before path routing still open the right page', async ({ page }) => {
  const w = watch(page)
  await page.goto('./#/season/2026')
  await expect(page.locator('h1')).toContainText('standings')
  expect(new URL(page.url()).pathname).toMatch(/\/season\/2026$/)
  await check(page, w, 'legacy hash link')
})

test('a driver\'s race has its own page', async ({ page }) => {
  const w = watch(page)
  await page.goto('race/1/driver/gasly')
  await expect(page.getByRole('region', { name: "Pierre Gasly's weekend" })).toBeVisible()
  await check(page, w, 'driver race page')
})
