// scripts/smoke.mjs — needs `npm run dev` on :5174 and the API on :8000.
import { chromium } from 'playwright'

const URL = process.env.SMOKE_URL ?? 'http://localhost:5174/?file=ankitha_1%2F04_build_accounts.sas&up=1&down=1'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
const fail = (m) => { console.error('SMOKE FAIL:', m); process.exitCode = 1 }

await page.goto(URL)
await page.waitForSelector('.rf-file', { timeout: 15000 })
const files = await page.locator('.rf-file').count()
console.log('file nodes:', files)
if (files !== 11) fail(`expected 11 file nodes, got ${files}`)
await page.screenshot({ path: '../plots/node4_viz_ankitha_04.png' })

await page.locator('[data-cid="file:ankitha_1/04_build_accounts.sas"] .rf-toggle').click()
await page.waitForSelector('.rf-group.kind-blockCluster', { timeout: 15000 })
const blocks = await page.locator('.rf-group.kind-blockCluster').count()
const occs = await page.locator('.rf-occ').count()
console.log('block groups:', blocks, 'table pills:', occs)
if (blocks < 2) fail(`expected >= 2 block groups, got ${blocks}`)
if (occs < 5) fail(`expected >= 5 table pills, got ${occs}`)
await page.screenshot({ path: '../plots/node4_viz_ankitha_04_expanded.png' })

await page.locator('.rf-group.kind-fileCluster .rf-toggle').first().click()
await page.waitForFunction(() => document.querySelectorAll('.rf-file').length === 11, null, { timeout: 15000 })
console.log('collapsed back to 11 files')
await browser.close()
if (!process.exitCode) console.log('SMOKE OK')
