// Screenshots of one page of a production build: node scripts/shot.mjs <baseURL> <path> <out.png|.jpg> [width] [selector]
// Env: SCHEME=light|dark. Motion is reduced, so the race sheet's drawing is captured finished.
import { chromium } from '@playwright/test'

const [base, path, out, width = '1360', selector] = process.argv.slice(2)
const browser = await chromium.launch(process.env.PW_CHROMIUM_PATH ? { executablePath: process.env.PW_CHROMIUM_PATH } : {})
const page = await browser.newPage({ viewport: { width: Number(width), height: 900 }, colorScheme: process.env.SCHEME ?? 'light', reducedMotion: 'reduce' })
await page.goto(new URL(path, base).href, { waitUntil: 'networkidle' })
await page.waitForTimeout(800)
const jpeg = out.endsWith('.jpg') ? { type: 'jpeg', quality: 70 } : {}
if (selector) await page.locator(selector).first().screenshot({ path: out, ...jpeg })
else {
  // full page, but at most 2,600px tall: enough for the top of a page without bloating the repository
  const h = Math.min(2600, await page.evaluate(() => document.documentElement.scrollHeight))
  await page.screenshot({ path: out, fullPage: true, clip: { x: 0, y: 0, width: Number(width), height: h }, ...jpeg })
}
await browser.close()
