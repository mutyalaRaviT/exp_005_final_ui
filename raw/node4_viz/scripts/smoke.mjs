// scripts/smoke.mjs — needs `npm run dev` (`:5199` in frontend/ui_across_file_ui,
// `:5174` in raw/node4_viz) and the Rust API on :8110.
//
// Task 8 (2026-09-10): the expected file-node count and the screenshot directory were
// hard-coded (`!== 11`, `../plots/`), so this script only ever passed for one seed file
// on one machine's layout. Both are parameters now: SMOKE_FILES (default 11, the count
// for 04_build_accounts at up=1&down=1) and SMOKE_OUT (default `../plots`).
import { chromium } from 'playwright'

// 2026-09-09, Task 5 (team-finance-corpus): fileid updated from `ankitha_1/...` to
// `sas/raw/...` to match the rebuilt oracle (raw/lineage_server/output/explorer.duckdb).
const URL = process.env.SMOKE_URL ?? 'http://localhost:5174/?file=sas%2Fraw%2F04_build_accounts.sas&up=1&down=1'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
const EXPECT_FILES = Number(process.env.SMOKE_FILES ?? 11)
const OUT = process.env.SMOKE_OUT ?? '../plots'
const fail = (m) => { console.error('SMOKE FAIL:', m); process.exitCode = 1 }

await page.goto(URL)
await page.waitForSelector('.rf-file', { timeout: 15000 })
const files = await page.locator('.rf-file').count()
console.log('file nodes:', files)
if (files !== EXPECT_FILES) fail(`expected ${EXPECT_FILES} file nodes, got ${files}`)
await page.screenshot({ path: `${OUT}/node4_viz_ankitha_04.png` })

await page.locator('[data-cid="file:sas/raw/04_build_accounts.sas"] .rf-toggle').click()
await page.waitForSelector('.rf-group.kind-blockCluster', { timeout: 15000 })
const blocks = await page.locator('.rf-group.kind-blockCluster').count()
const occs = await page.locator('.rf-occ').count()
console.log('block groups:', blocks, 'table pills:', occs)
if (blocks < 2) fail(`expected >= 2 block groups, got ${blocks}`)
if (occs < 5) fail(`expected >= 5 table pills, got ${occs}`)
await page.screenshot({ path: `${OUT}/node4_viz_ankitha_04_expanded.png` })

await page.locator('.rf-group.kind-fileCluster .rf-toggle').first().click()
await page.waitForFunction((n) => document.querySelectorAll('.rf-file').length === n, EXPECT_FILES, { timeout: 15000 })
console.log(`collapsed back to ${EXPECT_FILES} files`)
await browser.close()
if (!process.exitCode) console.log('SMOKE OK')
