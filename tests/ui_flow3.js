// 브라우저 화면 테스트 3 (고정 유지 재편성·편성안 비교·원인 확인)
// 실행: 예시 프로젝트를 한 번 편성해 둔 서버(CLASSPLAN_PORT=8770)에서  node tests/ui_flow3.js <스크린샷폴더>
const { chromium } = require('playwright');
const OUT = process.argv[2];
const log = (...a) => console.log(...a);
(async () => {
  const b = await chromium.launch();
  const pg = await (await b.newContext({ viewport: { width: 1500, height: 1000 } })).newPage();
  const errs = [];
  pg.on('pageerror', (e) => errs.push('PAGEERR ' + e.message));
  pg.on('console', (m) => { if (m.type() === 'error') errs.push('CONSOLE ' + m.text()); });
  await pg.goto('http://127.0.0.1:8770/'); await pg.waitForTimeout(500);
  await pg.click('[data-open]'); await pg.waitForTimeout(500);
  await pg.click('#tabs button[data-tab=results]'); await pg.waitForTimeout(1200);
  const unconf = await pg.$('#pUnconf'); if (unconf) { await unconf.click(); await pg.waitForTimeout(800); }
  const nPlans = (await pg.$$('[data-plan]')).length;
  const lockBtn = pg.locator('[data-lockcls]').nth(1);
  if ((await lockBtn.textContent()).includes('학급 고정') && !(await lockBtn.textContent()).includes('해제')) { await lockBtn.click(); await pg.waitForTimeout(1000); }
  const lockedBefore = await pg.$$eval('.stu', (els) => els.filter((e) => e.textContent.includes('🔒')).map((e) => [e.dataset.stu, e.closest('[data-col]').dataset.col]));
  log('locked students:', lockedBefore.length);
  await pg.click('#rRerun'); await pg.waitForSelector('#rrN'); await pg.selectOption('#rrN', '2');
  await pg.click('.modal >> text=재편성 시작');
  await pg.waitForTimeout(800); await pg.screenshot({ path: OUT + '/30_rerun_progress.png' });
  await pg.waitForFunction((n) => document.querySelectorAll('[data-plan]').length > n, nPlans, { timeout: 60000 });
  await pg.waitForTimeout(1200);
  log('plans:', nPlans, '->', (await pg.$$('[data-plan]')).length, 'active:', await pg.textContent('[data-plan].active'));
  const after = await pg.$$eval('.stu', (els) => Object.fromEntries(els.map((e) => [e.dataset.stu, e.closest('[data-col]').dataset.col])));
  log('locks kept in new plan:', lockedBefore.every(([k, c]) => after[k] === c));
  await pg.click('#rCmp'); await pg.waitForSelector('#cOut .notice', { timeout: 10000 });
  log('compare:', (await pg.textContent('#cOut .notice')).replace(/\s+/g, ' '));
  await pg.screenshot({ path: OUT + '/31_compare.png' });
  await pg.click('.modal .x');
  const cause = await pg.$('[data-cause]');
  if (cause) { await cause.click(); await pg.waitForTimeout(6000); log('cause:', (await pg.textContent('#sideBody .notice.n-info')).slice(0, 160)); }
  else log('no item needs cause check');
  console.log(errs.join('\n') || 'NO ERRORS');
  await b.close();
})();
