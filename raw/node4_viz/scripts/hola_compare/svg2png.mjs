import { chromium } from '/Users/mutyala/Desktop/lineageQ/lineageQ_sep_experiments/exp_003_lineageq_slides/node4_viz/node_modules/playwright/index.mjs'
import { readFileSync } from 'node:fs'
const browser = await chromium.launch()
for (const name of process.argv.slice(2)) {
  const svg = readFileSync(`${name}.svg`, 'utf8')
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
  await page.setContent(`<html><body style="margin:0;background:#fff">${svg}</body></html>`)
  const el = await page.$('svg')
  await el.screenshot({ path: `${name}.png` })
  console.log('wrote', `${name}.png`)
}
await browser.close()
