// Screenshots of one page of a production build: node scripts/shot.mjs <baseURL> <path> <out.png> [width] [selector]
import { chromium } from '@playwright/test'

const [base, path, out, width = '1360', selector] = process.argv.slice(2)
const browser = await chromium.launch(process.env.PW_CHROMIUM_PATH ? { executablePath: process.env.PW_CHROMIUM_PATH } : {})
const page = await browser.newPage({ viewport: { width: Number(width), height: 900 }, colorScheme: process.env.SCHEME ?? 'light' })
await page.goto(new URL(path, base).href, { waitUntil: 'networkidle' })
await page.waitForTimeout(800)
if (selector) await page.locator(selector).first().screenshot({ path: out })
else await page.screenshot({ path: out, fullPage: true })
await browser.close()
