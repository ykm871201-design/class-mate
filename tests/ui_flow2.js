// 브라우저 화면 테스트 2 (엑셀 불러오기·충돌 안내·상세 편집·일괄 수정·관계 추가)
// 실행: 서버를 CLASSPLAN_PORT=8770 으로 켠 뒤  node tests/ui_flow2.js <스크린샷폴더> <예시엑셀경로>
const { chromium } = require('playwright');
const [OUT, XLSX] = process.argv.slice(2);
const log = (...a) => console.log(...a);
(async () => {
  const b = await chromium.launch();
  const pg = await (await b.newContext({ viewport: { width: 1500, height: 1000 } })).newPage();
  const errs = [];
  pg.on('pageerror', (e) => errs.push('PAGEERR ' + e.message));
  pg.on('console', (m) => { if (m.type() === 'error') errs.push('CONSOLE ' + m.text()); });
  await pg.goto('http://127.0.0.1:8770/'); await pg.waitForTimeout(500);
  // 새 프로젝트
  await pg.click('#newProj'); await pg.fill('#nName', 'UI 테스트 프로젝트'); await pg.click('.modal .btn-pri'); await pg.waitForTimeout(800);
  // 특성 항목 켜기 (전반적인 학습 수준, 활동성)
  await pg.click('#tabs button[data-tab=features]'); await pg.waitForTimeout(400);
  await pg.check('[data-fa=f_learn]'); await pg.waitForTimeout(300); await pg.check('[data-fa=f_active]'); await pg.waitForTimeout(300);
  // 엑셀 불러오기
  await pg.click('#tabs button[data-tab=students]'); await pg.waitForTimeout(400);
  const [fc] = await Promise.all([pg.waitForEvent('filechooser'), pg.click('#sImport')]);
  await fc.setFiles(XLSX); await pg.waitForSelector('.modal #iMap'); await pg.waitForTimeout(400);
  await pg.screenshot({ path: OUT + '/20_import_map.png' });
  await pg.click('.modal >> text=검사하기 (미리보기)'); await pg.waitForTimeout(1500);
  log('import check:', (await pg.textContent('#iResult .notice')).replace(/\s+/g, ' ').slice(0, 200));
  await pg.screenshot({ path: OUT + '/21_import_check.png' });
  await pg.click('#iGo'); await pg.waitForTimeout(800);
  log('students heading:', await pg.textContent('h2'));
  // 동일 파일 다시 불러오기 → 중복 경고
  const [fc2] = await Promise.all([pg.waitForEvent('filechooser'), pg.click('#sImport')]);
  await fc2.setFiles(XLSX); await pg.waitForSelector('.modal #iMap'); await pg.waitForTimeout(400);
  log('dup warning shown:', (await pg.textContent('.modal-b')).includes('이미 불러온 적이 있는'));
  await pg.click('.modal >> text=검사하기 (미리보기)'); await pg.waitForTimeout(1500);
  log('re-import check:', (await pg.textContent('#iResult .notice')).replace(/\s+/g, ' ').slice(0, 160));
  await pg.click('.modal .x');
  // 상세 편집: 첫 학생 성별 지우기 → 미입력
  await pg.click('[data-detail]'); await pg.waitForSelector('#dGen');
  await pg.selectOption('#dGen', ''); await pg.click('.modal >> text=저장'); await pg.waitForTimeout(500);
  // 일괄 수정: 3명 선택 → 편성 제외
  for (const i of [1, 2, 3]) { await pg.locator('[data-sel]').nth(i).check(); await pg.waitForTimeout(200); }
  await pg.click('#sBulk'); await pg.waitForSelector('#bF');
  await pg.selectOption('#bF', 'eligible'); await pg.selectOption('#bVal', '0'); await pg.click('.modal .btn-pri'); await pg.waitForTimeout(500);
  log('after bulk:', await pg.textContent('h2'));
  // 관계 추가: 3명 모두 다른 반 (반드시)
  await pg.click('#tabs button[data-tab=relations]'); await pg.waitForTimeout(600);
  await pg.click('#rAdd'); await pg.waitForSelector('#rPick');
  for (const q of ['S0020', 'S0021', 'S0022']) { await pg.fill('#rPick .sp-in', q); await pg.waitForTimeout(200); await pg.press('#rPick .sp-in', 'Enter'); }
  await pg.screenshot({ path: OUT + '/22_relation_editor.png' });
  await pg.click('.modal >> text=저장'); await pg.waitForTimeout(600);
  // 충돌 만들기: S0020-S0021 반드시 같은 반 → 사전 검사 오류 → '해당 설정으로 이동'
  await pg.click('#rAdd'); await pg.waitForSelector('#rPick');
  await pg.click('[data-q="must,same"]');
  for (const q of ['S0020', 'S0021']) { await pg.fill('#rPick .sp-in', q); await pg.waitForTimeout(200); await pg.press('#rPick .sp-in', 'Enter'); }
  await pg.click('.modal >> text=저장'); await pg.waitForTimeout(600);
  await pg.click('#tabs button[data-tab=solve]'); await pg.waitForTimeout(400);
  await pg.click('#sGo'); await pg.waitForSelector('#sOut .notice', { timeout: 30000 }); await pg.waitForTimeout(300);
  log('solve with conflict:', (await pg.textContent('#sOut')).replace(/\s+/g, ' ').slice(0, 260));
  await pg.screenshot({ path: OUT + '/23_conflict.png' });
  await pg.click('#sOut [data-goto]'); await pg.waitForTimeout(800);
  log('went to tab:', await pg.$eval('#tabs button.active', (e) => e.dataset.tab), 'flash rows:', (await pg.$$('tr.flash')).length);
  console.log(errs.join('\n') || 'NO ERRORS');
  await b.close();
})();
