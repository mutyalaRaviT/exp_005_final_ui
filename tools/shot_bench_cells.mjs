import { chromium } from 'playwright';
const BASE=process.env.BASE, OUT=process.env.OUT;
const b=await chromium.launch();
const pg=await b.newPage({viewport:{width:2000,height:1200}});
const errs=[]; pg.on('console',m=>{if(m.type()==='error')errs.push(m.text());});
await pg.goto(BASE+'/bench',{waitUntil:'networkidle'});
await pg.waitForTimeout(1200);
// M4b: UI2 is keyed by fileid now, and the pass mark is the exp_42 receipt file
// (23 blocks, 80 statements, folded 80/80, round trip 80/80, 12 table edges),
// converted into the store as its own root. localStorage would otherwise reopen
// whatever was last looked at, so it is cleared first.
await pg.evaluate(()=>{ try{ localStorage.removeItem('bench.last'); }catch(e){} });
await pg.evaluate(()=>window.openFile('test_vishnu_testdata_fixed.sas'));
await pg.waitForTimeout(6000);
await pg.keyboard.press('c');            // cells view
await pg.waitForTimeout(2500);
const sas   = await pg.$$eval('.cell .sas, .col-sas .cell', n=>n.length).catch(()=>0);
const cells = await pg.$$eval('.cell', n=>n.length).catch(()=>0);
const status= await pg.$eval('#statusbar, .statusbar, footer', n=>n.textContent.replace(/\s+/g,' ').trim().slice(0,140)).catch(()=>'');
await pg.screenshot({path:`${OUT}/bench_cells.png`});
console.log('cells:',cells,' sasCells:',sas);
console.log('status:',status);
console.log(errs.length?'ERRORS: '+errs.slice(0,3).join(' | '):'no console errors');
await b.close();
