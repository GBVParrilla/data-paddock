import { defineConfig, devices } from '@playwright/test'

// Crawls the production build (make build) served by `vite preview`, or any deployed copy via
// E2E_BASE_URL (e.g. the live site). Two projects: desktop and a 375px phone.
const external = process.env.E2E_BASE_URL
const baseURL = external ?? 'http://127.0.0.1:4173/data-paddock/'

export default defineConfig({
  testDir: 'e2e',
  timeout: 15 * 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list'], ['json', { outputFile: 'e2e-results/results.json' }]],
  outputDir: 'e2e-results/artifacts',
  use: {
    baseURL,
    trace: 'retain-on-failure',
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    launchOptions: process.env.PW_CHROMIUM_PATH ? { executablePath: process.env.PW_CHROMIUM_PATH } : undefined,
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } } },
    { name: 'mobile', use: { ...devices['iPhone 13'], browserName: 'chromium', viewport: { width: 375, height: 812 } } },
  ],
  webServer: external ? undefined : {
    command: 'npx vite preview --base /data-paddock/ --port 4173 --strictPort',
    url: baseURL,
    reuseExistingServer: true,
  },
})
