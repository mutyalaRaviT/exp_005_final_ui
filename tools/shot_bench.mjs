import { chromium } from 'playwright';
const BASE = process.env.BASE, OUT = process.env.OUT;
const b = await chromium.launch();
const pg = await b.newPage({ viewport:{width:2000,height:1200} });
const errs=[]; pg.on('console', m=>{ if(m.type()==='error') errs.push(m.text()); });
await pg.goto(BASE+'/bench', { waitUntil:'networkidle' });
await pg.waitForTimeout(1500);
// open the file the owner's baseline shows
await pg.evaluate(() => window.openFile('testdata/test_vishnu_testdata_fixed.sas'));
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
