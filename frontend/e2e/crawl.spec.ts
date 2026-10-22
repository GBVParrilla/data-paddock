import { expect, test, type Locator, type Page } from '@playwright/test'

// Crawls the site the way a visitor does: in-app links only, never a reload. At every step:
// no console errors or uncaught exceptions, a non-empty <main>, and no leaked machine text.
const FORBIDDEN: RegExp[] = [/\bNone\b/, /\bnull\b/, /\bundefined\b/, /\bNaN\b/, /\[object/, /BAD_FORMAT/, /\{\}/, /<br>/]
const PILOT_ROUNDS = [1, 12, 17]
// Helper text the declutter removed (REVIEW_ROUND2 A7). Exactly one hint may remain: "Pick up to two drivers".
const OLD_HINTS = ['What decided the race, in lap order', 'Pick a driver to follow their weekend', 'Hover a line', 'Tap a line', 'Circles mark pit stops', 'What stood out']
const FRESHNESS = /Data through round \d+, updated \d{1,2} [A-Z][a-z]{2}/

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
      momentTexts: [...main.querySelectorAll('section[aria-label="Key moments"] li')].map((e) => (e as HTMLElement).innerText),
      margin: [...main.querySelectorAll('[data-margin-moment]')].map((e) => [e.getAttribute('data-margin-moment'), (e as HTMLElement).innerText]),
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
  // #63: one gap, one row ("Hülkenberg ... 1.720s behind Lawson" and "Lawson ... 1.720s ahead of Hülkenberg" was one fact twice)
  const gaps = r.momentTexts.flatMap((t) => t.match(/\d+\.\d{3}s (?:behind|ahead of)/g)?.map((g) => g.split(' ')[0]) ?? [])
  expect.soft(gaps.filter((g, i) => gaps.indexOf(g) !== i), `${label}: the same gap in two key moments`).toEqual([])
  // #64: a margin note about a driver says whose it is
  const nameless = r.margin.filter(([who, text]) => who !== 'session' && !/\(.+\)/.test(text!)).map(([, t]) => t)
  expect.soft(nameless, `${label}: margin notes without a driver`).toEqual([])
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
  // the deep dive renders once it scrolls into view (it is below the fold, and heavy)
  await toggle.scrollIntoViewIfNeeded()
  await page.getByRole('region', { name: 'Deep dive' }).waitFor()
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
        // the race sheet comes first, so scroll the page (only vertically) to the table before looking
        await page.locator('section[aria-label="Classification"]').evaluate((el) => window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - 8))
        await expect.soft(pts, `${label}: Pts column`).toBeInViewport()
      }
    }
  }
})

for (const round of PILOT_ROUNDS) {
  test(`round ${round}: one driver, then another, every deep-dive tab, every session`, async ({ page }) => {
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
      // REVIEW_ROUND3 #50: a second tap switches the selection; it never stacks a second story or a head-to-head
      const second = Number(await rows.nth(10).getAttribute('data-driver'))
      await rows.nth(10).click()
      await expect(page.locator('section[aria-label="Classification"] tr[aria-selected="true"]')).toHaveCount(1)
      await expect(page.locator('section[aria-label$="\'s weekend"]')).toHaveCount(1)
      await expect(page.locator(`section[aria-label="Classification"] tr[data-driver="${second}"]`)).toHaveAttribute('aria-selected', 'true')
      // the vs strip is part of the panel for every driver who took part
      const ran = await page.evaluate(async (d) => {
        const sid = document.querySelector('[data-session]')?.getAttribute('data-session')
        const h = await (await fetch(`${document.baseURI.replace(/\/(race|season|races)(\/.*)?(\?.*)?$/, '/')}data/sessions/${sid}/headline.json`)).json()
        const row = (h.race ?? h.qualifying ?? h.practice ?? []).find((r: { driver_id: number }) => r.driver_id === d)
        return !!row && row.status_code !== 'DNS' && row.status_code !== 'NO_TIME' && (row.rank === undefined || row.rank !== null)
      }, second)
      if (ran) await expect(page.locator('section[aria-label$="\'s weekend"] [data-vs]')).toHaveCount(1)
      await check(page, w, `R${round} ${name}: another driver`)
      await openMoreDetail(page)
      const dd = page.getByRole('region', { name: 'Deep dive' }).getByRole('tab')
      if (name === 'Race') {
        // tyres, sectors, race control, plus turn by turn once that driver's breakdown is exported (#8)
        const turns = await page.evaluate(async () => {
          const sid = document.querySelector('[data-session]')?.getAttribute('data-session')
          const picked = [...document.querySelectorAll('section[aria-label="Classification"] tr[aria-selected="true"]')].map((t) => Number(t.getAttribute('data-driver')))
          const res = await fetch(`${document.baseURI.replace(/\/(race|season|races)(\/.*)?(\?.*)?$/, '/')}data/sessions/${sid}/turn-deltas.json`)
          if (!res.ok || !(res.headers.get('content-type') ?? '').includes('json')) return null
          const have = (await res.json()).drivers as number[]
          return picked.some((d) => have.includes(d))
        })
        expect(turns, `R${round} race: turn-deltas index`).not.toBeNull()
        expect.soft(await dd.count(), `R${round} race: deep-dive tabs`).toBeGreaterThanOrEqual(turns ? 4 : 3)
      }
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
  const story = page.getByRole('region', { name: "Pierre Gasly's weekend" })
  await expect(story).toBeVisible()
  // #62: the story comes straight after the race sheet, before the classification (it was 1,750px down,
  // past the classification, key moments and position chart)
  const top = async (l: Locator) => (await l.boundingBox())!.y
  expect(await top(story)).toBeLessThan(await top(page.getByRole('region', { name: 'Classification' })))
  await check(page, w, 'driver race page')
  // BENCHMARKS row 17: the numbers behind each chart, as a table and a CSV
  const positions = page.getByRole('region', { name: 'Race positions' })
  await positions.scrollIntoViewIfNeeded()
  await positions.getByText('The numbers').click()
  expect(await positions.locator('[data-chart-table] tbody tr').count(), 'one row per driver in the positions table').toBeGreaterThanOrEqual(18)
  await expect(positions.getByRole('link', { name: 'Download CSV' })).toHaveAttribute('download', 'positions.csv')
  const vs = story.locator('[data-vs]')
  await vs.getByText('The numbers').click()
  expect(await vs.locator('[data-chart-table] tbody tr').count(), 'one row per lap in the gap table').toBeGreaterThan(10)
  // a tap on another driver shows their story: it replaces this one and scrolls into view
  await page.getByRole('region', { name: 'Classification' }).locator('tr[data-driver]', { hasText: 'OCO' }).click()
  const next = page.getByRole('region', { name: "Esteban Ocon's weekend" })
  await expect(next).toBeInViewport()
  await check(page, w, 'driver picked from the table')
})

test('a lap opens its sectors: from the chart, the picker and a shared link (BENCHMARKS row 21)', async ({ page }) => {
  const w = watch(page)
  // a shared link: Stroll's lap 20 at Singapore
  await page.goto('race/17/driver/stroll?lap=20')
  const positions = page.getByRole('region', { name: 'Race positions' })
  await positions.scrollIntoViewIfNeeded()
  const card = positions.locator('[data-lap-card="20"]')
  await expect(card).toBeVisible()
  // his line and his teammate's, each with three sectors
  expect(await card.locator('[data-lap-driver]').count()).toBe(2)
  expect(await card.locator('[data-lap-driver]').first().locator('tbody tr').count()).toBe(3)
  await expect(card.locator('[data-lap-driver]').first()).toContainText(/S1.*\d/s)
  await check(page, w, 'lap card from a link')
  // the next lap, kept in the link
  await card.getByRole('button', { name: 'Next lap' }).click()
  await expect(positions.locator('[data-lap-card="21"]')).toBeVisible()
  expect(new URL(page.url()).searchParams.get('lap')).toBe('21')
  // the head-to-head gap chart picks a lap too, and shows it in the strip
  const gapChart = page.locator('[data-vs] [data-gap-chart]')
  const g = (await gapChart.boundingBox())!
  await gapChart.click({ position: { x: g.width * 0.6, y: g.height / 2 } })
  await expect(page.locator('[data-vs] [data-lap-card]')).toBeVisible()
  // nobody picked: the picker shows the first three on that lap
  await page.goto('race/17')
  await page.getByRole('region', { name: 'Race positions' }).scrollIntoViewIfNeeded()
  await page.getByRole('combobox', { name: 'Show a lap' }).selectOption('30')
  const top3 = page.locator('[data-lap-card="30"] [data-lap-driver]')
  await expect(top3).toHaveCount(3)
  // a click on the chart picks the lap under the pointer
  const chart = page.getByRole('region', { name: 'Race positions' }).locator('.recharts-wrapper').first()
  const box = (await chart.boundingBox())!
  await chart.click({ position: { x: box.width * 0.5, y: box.height * 0.5 } })
  await expect(page.locator('[data-lap-card]')).toBeVisible()
  expect(Number(new URL(page.url()).searchParams.get('lap'))).toBeGreaterThan(10)
  await page.locator('[data-lap-card]').getByRole('button', { name: 'Close' }).click()
  await expect(page.locator('[data-lap-card]')).toHaveCount(0)
  await check(page, w, 'lap picked on the chart')
})

test('follow a driver: Follow on their panel puts them first on home', async ({ page }) => {
  const w = watch(page)
  await page.goto('race/17/driver/stroll')
  const story = page.getByRole('region', { name: "Lance Stroll's weekend" })
  await story.getByRole('button', { name: 'Follow' }).click()
  await expect(story.getByRole('button', { name: 'Following' })).toHaveAttribute('aria-pressed', 'true')
  await page.goto('./')
  const mine = page.getByRole('region', { name: 'The driver you follow' })
  await expect(mine).toContainText('Lance Stroll')
  await expect(mine.getByRole('link')).toHaveAttribute('href', /\/race\/\d+\/driver\/stroll$/)
  // on the championship ladder too, after the top ten
  await expect(page.locator('section[aria-label="Championship"] [data-followed]')).toContainText('Stroll')
  await check(page, w, 'home, following a driver')
  await mine.getByRole('button', { name: 'Stop following' }).click()
  await expect(mine).toHaveCount(0)
})

test('spoiler-free mode hides the latest round until revealed', async ({ page }) => {
  const w = watch(page)
  await page.goto('./')
  const latest = page.getByRole('article', { name: 'Latest race' })
  await expect(latest.locator('[data-moment-n], .num').first()).toBeVisible()
  await page.getByRole('button', { name: /spoiler-free/i }).click()
  await expect(page.getByRole('button', { name: /spoiler-free/i })).toHaveAttribute('aria-pressed', 'true')
  // the latest plate keeps its circuit but not its podium; the standings wait too
  await expect(latest.getByRole('button', { name: 'Show the result' })).toBeVisible()
  await expect(page.locator('section[aria-label="Championship"] [data-spoiler-gate]')).toBeVisible()
  await check(page, w, 'home, spoiler-free')
  // the race page shows only its name and the button
  await latest.getByRole('link').first().click()
  const gate = page.getByRole('region', { name: 'Spoiler-free' })
  await expect(gate).toBeVisible()
  await expect(page.getByRole('region', { name: 'Classification' })).toHaveCount(0)
  await check(page, w, 'race page, spoiler-free')
  await gate.getByRole('button', { name: 'Show the result' }).click()
  await expect(page.getByRole('region', { name: 'Classification' })).toBeVisible()
  // older rounds were never hidden
  await page.goto('race/1')
  await expect(page.getByRole('region', { name: 'Classification' })).toBeVisible()
  await page.getByRole('button', { name: /spoiler-free/i }).click()
  await expect(page.getByRole('button', { name: /spoiler-free/i })).toHaveAttribute('aria-pressed', 'false')
})

test('the changelog lists dated changes and is linked from every page', async ({ page }) => {
  const w = watch(page)
  await page.goto('./')
  await page.getByRole('contentinfo').getByRole('link', { name: 'What changed' }).click()
  await expect(page.locator('h1')).toHaveText('What changed')
  expect(await page.locator('main time[datetime]').count()).toBeGreaterThan(3)
  await check(page, w, 'changelog')
})

test('Expert mode shows the debrief and opens more detail, and survives a shared link', async ({ page }) => {
  const w = watch(page)
  await page.goto('race/1/driver/gasly?mode=expert')
  const story = page.getByRole('region', { name: "Pierre Gasly's weekend" })
  await expect(story).toBeVisible()
  // REVIEW_ROUND3 D7: Expert is the computed debrief (findings and tables), not more prose
  await expect(story.locator('[data-debrief="race"]')).toBeVisible()
  await expect(story.getByRole('list', { name: 'Findings' })).toBeVisible()
  await expect(story.locator('[data-essential]')).toHaveCount(0)
  await expect(page.getByRole('button', { name: /more detail/i })).toHaveAttribute('aria-expanded', 'true')
  await page.getByRole('button', { name: /more detail/i }).scrollIntoViewIfNeeded()
  await expect(page.getByRole('region', { name: 'Deep dive' })).toBeVisible()
  await expect(page.getByRole('radio', { name: 'Expert' })).toBeChecked()
  await check(page, w, 'expert driver page')
  // back to Essential: the detail closes again for a page with nobody picked
  await page.getByRole('radio', { name: 'Essential' }).click()
  await page.getByRole('button', { name: 'Clear selection' }).click()
  await expect(page.getByRole('button', { name: /more detail/i })).toHaveAttribute('aria-expanded', 'false')
  await check(page, w, 'essential, nobody picked')
})

test('corner colours are ranks, and a withheld breakdown colours no corner (REVIEW_ROUND3 #48, #49)', async ({ page }) => {
  // Baku FP1 (session 71): Norris's best lap had a frozen location feed, which drew +98.9s at T1 and purple
  // everywhere else. Every shown breakdown's map colours must equal its exported ranks; a withheld one (when the
  // snapshot has one) colours no corner
  const index = await (await page.request.get('data/sessions/71/turn-deltas.json')).json() as { drivers: number[]; withheld: number[] }
  test.skip(!index.drivers.length, 'this snapshot has no Baku FP1 breakdowns')
  const w = watch(page)
  const circuit = page.getByRole('region', { name: 'Circuit' })
  if (index.withheld.length) {
    await page.goto(`race/15?session=71&drivers=${index.withheld.includes(19) ? 19 : index.withheld[0]}`)
    await expect(circuit.getByText("Corner times aren't reliable for this lap.")).toBeVisible()
    await expect(circuit.locator('circle[data-tier]')).toHaveCount(0)
    await check(page, w, 'withheld corners')
  }
  const shown = index.drivers.includes(19) ? 19 : index.drivers[0]
  await page.goto(`race/15?session=71&drivers=${shown}`)
  const td = await (await page.request.get(`data/sessions/71/drivers/${shown}/turn-deltas.json`)).json() as { turns: { number: number; rank: number; of: number }[] }
  await expect(circuit.locator('circle[data-tier]').first()).toBeVisible()
  const tierOf = (rank: number, of: number) => rank === 1 ? 'purple' : rank <= Math.ceil(of / 4) ? 'green' : rank <= Math.ceil(of * 3 / 4) ? 'yellow' : 'red'
  for (const t of td.turns) {
    await expect.soft(circuit.locator(`circle[data-turn="${t.number}"]`).first(), `T${t.number}`).toHaveAttribute('data-tier', tierOf(t.rank, t.of))
  }
  await check(page, w, 'ranked corners')
})

test('one driver per tap: vs links restore exactly, old two-driver links redirect, the strip stays short (REVIEW_ROUND3 #50)', async ({ page }) => {
  const w = watch(page)
  // R1 race: Gasly (Alpine); Ocon is a rival, Colapinto the teammate
  const h = await (await page.request.get('data/sessions/' + (await (await page.request.get('data/events/1/sessions.json')).json() as { id: number; session_type: string }[]).find((s) => s.session_type === 'R')!.id + '/headline.json')).json() as { session: { id: number }; drivers: Record<string, { driver_ref: string; team: string }> }
  const id = (ref: string) => Number(Object.entries(h.drivers).find(([, d]) => d.driver_ref === ref)![0])
  const sid = h.session.id
  const [gas, oco, col] = [id('gasly'), id('ocon'), id('colapinto')]
  const panel = page.locator('section[aria-label$="\'s weekend"]')

  await page.goto(`race/1?session=${sid}&drivers=${gas}`)
  await expect(panel).toHaveCount(1)
  await expect(panel.locator('[data-vs]')).toHaveAttribute('data-vs', String(col))  // the teammate by default
  const without = await page.evaluate(() => document.documentElement.scrollHeight)

  await page.goto(`race/1?session=${sid}&drivers=${gas}&vs=${oco}`)
  await expect(panel.locator('[data-vs]')).toHaveAttribute('data-vs', String(oco))
  await expect(page.getByRole('combobox', { name: 'Compare with' })).toHaveValue(String(oco))
  expect(new URL(page.url()).searchParams.get('vs')).toBe(String(oco))
  const withVs = await page.evaluate(() => document.documentElement.scrollHeight)
  expect(withVs - without, 'a vs page is at most 900px taller').toBeLessThanOrEqual(900)
  const strip = await panel.locator('[data-vs]').boundingBox()
  expect(strip!.height, 'the vs strip').toBeLessThanOrEqual(900)
  await check(page, w, 'vs link')

  // a link from before D8: drivers=a,b opens a with vs b
  await page.goto(`race/1?session=${sid}&drivers=${gas},${oco}`)
  await expect(panel).toHaveCount(1)
  await expect(panel.locator('[data-vs]')).toHaveAttribute('data-vs', String(oco))
  await expect.poll(() => new URL(page.url()).searchParams.get('drivers')).toBe(String(gas))
  expect(new URL(page.url()).searchParams.get('vs')).toBe(String(oco))

  // Compare with... is a plain list; picking from it changes the strip and the link
  await page.getByRole('combobox', { name: 'Compare with' }).selectOption(String(col))
  await expect(panel.locator('[data-vs]')).toHaveAttribute('data-vs', String(col))
  await expect.poll(() => new URL(page.url()).searchParams.get('vs')).toBe(String(col))
  // "Read X's story" switches the selection
  await panel.getByRole('button', { name: /Read Colapinto's story/ }).click()
  await expect(page.getByRole('region', { name: "Franco Colapinto's weekend" })).toBeVisible()
  await check(page, w, 'switched by the strip')
})

test('the methods page explains the computed numbers', async ({ page }) => {
  const w = watch(page)
  await page.goto('methods')
  await expect(page.locator('h1')).toHaveText('How the numbers are made')
  for (const id of ['fuel', 'degradation', 'stops', 'ranks', 'corners']) await expect(page.locator(`#${id}`)).toBeVisible()
  await check(page, w, 'methods')
})
