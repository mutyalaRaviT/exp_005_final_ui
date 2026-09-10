import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://localhost:5199';
const OUT  = process.env.OUT  || '/tmp';
// Task 5 (2026-09-09) rebuilt the store on `sas/raw/<name>.sas` fileids; these two deep
// links still said `ankitha_1/...`, so both shots landed on an empty canvas and reported
// files=0 without failing. Measured and fixed 2026-09-10 (Task 8).
const shots = [
  ['baseline_18_dashboard_mart', '/?file=sas%2Fraw%2F18_dashboard_mart.sas&up=1&down=1'],
  ['passmark_11_branch_rollup',  '/?file=sas%2Fraw%2F11_branch_rollup.sas&up=1&down=1'],
  ['passmark_07_enrich_fx',      '/?file=sas%2Fraw%2F07_enrich_fx.sas&up=1&down=1'],
];
const b = await chromium.launch();
const pg = await b.newPage({ viewport:{width:2000,height:1200}, deviceScaleFactor:1 });
const errs=[]; pg.on('console', m=>{ if(m.type()==='error') errs.push(m.text()); });
for (const [name, path] of shots) {
  await pg.goto(BASE+path, { waitUntil:'networkidle' });
  await pg.waitForSelector('.rf-file', { timeout: 20000 }).catch(()=>{});
  await pg.waitForTimeout(2500);
  const files = await pg.$$eval('.rf-file', n=>n.length).catch(()=>0);
  const edges = await pg.$$eval('.react-flow__edge', n=>n.length).catch(()=>0);
  // Open the edges drawer ("e" toggles the strip's edges tab, App.tsx:397) so the shot
  // carries the drawer's own receipt — the "25 / 25" and the HUMAN_GOLD row the owner's
  // 2026-09-09 baseline shows for 18_dashboard_mart. Without this the drawer is closed and
  // edgeRows was always 0, which is what the pre-Task-8 script reported.
  await pg.keyboard.press('e');
  await pg.waitForSelector('[data-cid="edges-count"]', { timeout: 20000 }).catch(()=>{});
  await pg.waitForTimeout(1500);
  const rows  = await pg.$$eval('.edges-row', n=>n.length).catch(()=>0);
  const count = await pg.$eval('[data-cid="edges-count"]', n=>n.textContent.trim()).catch(()=>'n/a');
  const gold  = await pg.$$eval('.edges-row .chip-human_gold', n=>n.length).catch(()=>0);
  await pg.screenshot({ path: `${OUT}/${name}.png`, fullPage:false });
  console.log(`${name}: files=${files} edges=${edges} edgeRows=${rows} edgesCount=${count} humanGold=${gold} -> ${OUT}/${name}.png`);
}
if (errs.length) console.log('CONSOLE ERRORS:', errs.slice(0,5).join(' | '));
else console.log('no console errors');
await b.close();
