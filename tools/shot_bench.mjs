import { chromium } from 'playwright';
const BASE = process.env.BASE, OUT = process.env.OUT;
const b = await chromium.launch();
const pg = await b.newPage({ viewport:{width:2000,height:1200} });
const errs=[]; pg.on('console', m=>{ if(m.type()==='error') errs.push(m.text()); });
await pg.goto(BASE+'/bench', { waitUntil:'networkidle' });
await pg.waitForTimeout(1500);
// open a file from the corpus (2026-09-09, Task 5 fix round 1: testdata/ is deleted)
await pg.evaluate(() => window.openFile('../../corpus/team_finance/sas/raw/09_customer_summary.sas'));
await pg.waitForTimeout(6000);
const cells = await pg.$$eval('.cell, .blk', n=>n.length).catch(()=>0);
const pills = await pg.$$eval('#top .pill', n=>n.map(x=>x.textContent.trim())).catch(()=>[]);
const meta  = await pg.$eval('#meta, #top', n=>n.textContent.trim().slice(0,180)).catch(()=>'');
await pg.screenshot({ path: `${OUT}/bench.png` });
console.log('cells:', cells);
console.log('pills:', JSON.stringify(pills));
console.log('header:', meta.replace(/\s+/g,' '));
console.log(errs.length ? 'CONSOLE ERRORS: '+errs.slice(0,4).join(' | ') : 'no console errors');
await b.close();
