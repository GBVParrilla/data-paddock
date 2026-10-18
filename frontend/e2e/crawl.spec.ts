import { expect, test, type Page } from '@playwright/test'

// Crawls the site the way a visitor does: in-app links only, never a reload. At every step:
// no console errors or uncaught exceptions, a non-empty <main>, and no leaked machine text.
const FORBIDDEN: RegExp[] = [/\bNone\b/, /\bnull\b/, /\bundefined\b/, /\bNaN\b/, /\[object/, /BAD_FORMAT/, /\{\}/, /<br>/]
const PILOT_ROUNDS = [1, 12, 17]
// Helper text the declutter removed (REVIEW_ROUND2 A7). Exactly one hint may remain: "Pick up to two drivers".
const OLD_HINTS = ['What decided the race, in lap order', 'Pick a driver to follow their weekend', 'Hover a line', 'Tap a line', 'Circles mark pit stops', 'What stood out']
const FRESHNESS = /Data through round \d+ · updated \d{1,2} [A-Z][a-z]{2}/

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
  // a page-specific title, never the bare site name (REVIEW #24, #43)
  expect.soft(await page.title(), `${label}: page title`).toMatch(/^.+ · Data Paddock$/)
  const calm = await page.evaluate(() => {
    const terms = [...document.querySelectorAll('main [data-term]')].map((t) => t.getAttribute('data-term'))
    const hints = [...document.querySelectorAll('main [data-hint]')].map((t) => t.textContent?.trim())
    const sources = [...document.querySelectorAll('[data-story-source]')].map((t) => t.getAttribute('data-story-source'))
    return { terms, hints, sources, body: document.body.innerText }
  })
  // each glossary term is underlined once per page, the first time it appears
  const twice = calm.terms.filter((t, i) => calm.terms.indexOf(t) !== i)
  expect.soft([...new Set(twice)], `${label}: glossary terms underlined more than once`).toEqual([])
  expect.soft(calm.hints.length, `${label}: helper labels (${calm.hints.join(' | ')})`).toBeLessThanOrEqual(1)
  for (const h of OLD_HINTS) expect.soft(calm.body.includes(h), `${label}: removed helper label "${h}" is back`).toBe(false)
  // nothing claims Claude wrote what the page shows unless a Claude-written story is on it (REVIEW_ROUND2 #37)
  if (!calm.sources.includes('claude')) expect.soft(/by Claude/i.test(calm.body), `${label}: claims Claude authorship with no Claude-written story on the page`).toBe(false)
}

/** With nobody picked, a race page is calm: at most 5 panels, and each fact said once (REVIEW_ROUND2 #38, #46). */
async function calmRacePage(page: Page, label: string) {
  const r = await page.evaluate(() => {
    const main = document.querySelector('main')!
    const panels = [...main.querySelectorAll('.panel')].filter((el) => !el.parentElement?.closest('.panel') && (el as HTMLElement).offsetHeight > 0)
    const facts = (sel: string) => [...main.querySelectorAll(`${sel} [data-fact]`)].map((e) => e.getAttribute('data-fact'))
    const table = main.querySelector('section[aria-label="Classification"] .overflow-x-auto')
    return {
      panels: panels.map((p) => p.getAttribute('aria-label') ?? p.className), summary: facts('[data-summary]'), moments: facts('section[aria-label="Key moments"]'),
      tableOverflow: table ? table.scrollWidth - table.clientWidth : 0,
      podium: [...main.querySelectorAll('section[aria-label="Classification"] tr[data-pos="1"], section[aria-label="Classification"] tr[data-pos="2"], section[aria-label="Classification"] tr[data-pos="3"]')].map((t) => t.getAttribute('data-driver')),
      raceLike: !!main.querySelector('section[aria-label="Race positions"]'),
    }
  })
  // the mission stays visible: every race and sprint names someone beyond the podium near the top
  if (r.raceLike) {
    const named = [...r.summary, ...r.moments].map((f) => f?.split(':')[0]).filter((d) => d && d !== 'session')
    expect.soft(named.some((d) => !r.podium.includes(d!)), `${label}: no driver from beyond the podium in the summary or key moments`).toBe(true)
  }
  // every column, Pts included, fits its panel at this width (found at 1280-1360px in round 2)
  expect.soft(r.tableOverflow, `${label}: classification scrolls sideways by ${r.tableOverflow}px`).toBeLessThanOrEqual(1)
  expect.soft(r.panels.length, `${label}: panels before a driver is picked (${r.panels.join(', ')})`).toBeLessThanOrEqual(5)
  const both = r.summary.filter((f) => r.moments.includes(f))
  expect.soft(both, `${label}: facts in both the summary and key moments`).toEqual([])
}

async function home(page: Page) {
  await page.getByRole('link', { name: 'Data Paddock home' }).click()
  await expect(page.locator('main')).toContainText('season')
}

async function races(page: Page) {
  await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Races' }).click()
  await expect(page.locator('h1')).toContainText('races')
}

async function openRound(page: Page, round: number) {
  await races(page)
  await page.locator(`main a[aria-label$=", round ${round}"]`).first().click()
  await expect(page.locator('h1')).not.toBeEmpty()
}

async function openMoreDetail(page: Page) {
  const toggle = page.getByRole('button', { name: /more detail/i })
  if ((await toggle.getAttribute('aria-expanded')) !== 'true') await toggle.click()
}

async function sessionTabs(page: Page) {
  const tabs = page.getByRole('tablist', { name: 'Session' }).locator('button:not([disabled])')
  await expect(tabs.first(), 'session tabs never appeared').toBeVisible() // never count an empty, still-loading list
  return tabs
}

test.beforeEach(async ({ page }) => {
  await hostileScrollTo(page)
})

test('every race and every session tab, via in-app links', async ({ page }, info) => {
  const w = watch(page)
  await page.goto('./')
  await check(page, w, 'home')
  await expect(page.locator('main'), 'home: freshness stamp').toContainText(FRESHNESS)
  // home shows the latest 4 races; /races has them all
  expect(await page.locator('section[aria-label="Results"] a[aria-label*=", round "]').count(), 'big race cards on home').toBeLessThanOrEqual(4)
  await races(page)
  await check(page, w, 'races')
  const n = await page.locator('section[aria-label="Results"] a').count()
  expect(n, 'completed races on /races').toBeGreaterThan(0)
  for (let i = 0; i < n; i++) {
    if (i > 0) await races(page)
    const card = page.locator('section[aria-label="Results"] a').nth(i)
    const label = (await card.getAttribute('aria-label')) ?? `card ${i}`
    await card.click()
    await check(page, w, label)
    await expect.soft(page.locator('main'), `${label}: freshness stamp`).toContainText(FRESHNESS)
    const tabs = await sessionTabs(page)
    const count = await tabs.count()
    for (let t = 0; t < count; t++) {
      const tab = (await sessionTabs(page)).nth(t)
      const name = (await tab.innerText()).trim()
      await tab.click()
      await check(page, w, `${label} / ${name}`)
      await calmRacePage(page, `${label} / ${name}`)
      if (name === 'Race' && info.project.name === 'mobile') {
        // points are the result fans look for: visible without scrolling sideways (REVIEW_ROUND2 #45)
        const pts = page.locator('section[aria-label="Classification"] th', { hasText: 'Pts' })
        await expect.soft(pts, `${label}: Pts column`).toBeInViewport()
      }
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
      await openMoreDetail(page)
      const dd = page.getByRole('region', { name: 'Deep dive' }).getByRole('tab')
      if (name === 'Race') expect.soft(await dd.count(), `R${round} race: deep-dive tabs`).toBeGreaterThanOrEqual(4)
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
  await expect(page, 'standings title after in-app navigation').toHaveTitle(/standings/)
  await expect.soft(page.locator('main'), 'standings: freshness stamp').toContainText(FRESHNESS)
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

test('Expert mode opens more detail and the full story, and survives a shared link', async ({ page }) => {
  const w = watch(page)
  await page.goto('race/1/driver/gasly?mode=expert')
  const story = page.getByRole('region', { name: "Pierre Gasly's weekend" })
  await expect(story).toBeVisible()
  await expect(page.getByRole('button', { name: /more detail/i })).toHaveAttribute('aria-expanded', 'true')
  await expect(page.getByRole('region', { name: 'Deep dive' })).toBeVisible()
  await expect(page.getByRole('radio', { name: 'Expert' })).toBeChecked()
  await check(page, w, 'expert driver page')
  // back to Essential: the detail closes again for a page with nobody picked
  await page.getByRole('radio', { name: 'Essential' }).click()
  await page.getByRole('button', { name: 'Clear selection' }).click()
  await expect(page.getByRole('button', { name: /more detail/i })).toHaveAttribute('aria-expanded', 'false')
  await check(page, w, 'essential, nobody picked')
})
