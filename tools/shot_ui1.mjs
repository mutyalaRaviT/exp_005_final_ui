import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://localhost:5199';
const OUT  = process.env.OUT  || '/tmp';
const shots = [
  ['baseline_18_dashboard_mart', '/?file=ankitha_1%2F18_dashboard_mart.sas&up=1&down=1'],
  ['passmark_11_branch_rollup',  '/?file=ankitha_1%2F11_branch_rollup.sas&up=1&down=1'],
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
  const rows  = await pg.$$eval('#edges tbody tr, .edges-row', n=>n.length).catch(()=>0);
  await pg.screenshot({ path: `${OUT}/${name}.png`, fullPage:false });
  console.log(`${name}: files=${files} edges=${edges} edgeRows=${rows} -> ${OUT}/${name}.png`);
}
if (errs.length) console.log('CONSOLE ERRORS:', errs.slice(0,5).join(' | '));
else console.log('no console errors');
await b.close();
