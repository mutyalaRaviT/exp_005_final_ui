import { chromium } from 'playwright';
const BASE = process.env.BASE, OUT = process.env.OUT;
const b = await chromium.launch();
const pg = await b.newPage({ viewport:{width:2000,height:1200} });
const errs=[]; pg.on('console', m=>{ if(m.type()==='error') errs.push(m.text()); });
await pg.goto(BASE+'/bench', { waitUntil:'networkidle' });
await pg.waitForTimeout(1500);
// M4b: UI2 is keyed by fileid now, and the pass mark is the exp_42 receipt file
// (23 blocks, 80 statements, folded 80/80, round trip 80/80, 12 table edges),
// converted into the store as its own root. localStorage would otherwise reopen
// whatever was last looked at, so it is cleared first.
await pg.evaluate(()=>{ try{ localStorage.removeItem('bench.last'); }catch(e){} });
await pg.evaluate(()=>window.openFile('test_vishnu_testdata_fixed.sas'));
await pg.waitForTimeout(6000);
const cells = await pg.$$eval('.cell, .blk', n=>n.length).catch(()=>0);
const pills = await pg.$$eval('#top .pill', n=>n.map(x=>x.textContent.trim())).catch(()=>[]);
const meta  = await pg.$eval('#meta, #top', n=>n.textContent.trim().slice(0,180)).catch(()=>'');
const edges = await pg.evaluate(()=>window.LINEAGE ? window.LINEAGE.length : -1);
await pg.screenshot({ path: `${OUT}/bench.png` });
console.log('cells:', cells);
console.log('pills:', JSON.stringify(pills));
console.log('header:', meta.replace(/\s+/g,' '));
console.log('edges:', edges);
console.log(errs.length ? 'CONSOLE ERRORS: '+errs.slice(0,4).join(' | ') : 'no console errors');
await b.close();
