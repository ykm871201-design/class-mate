/* ⑤ 자동 편성 */
'use strict';
App.tabs.solve = {
  pre: null, last: null,
  render(main) {
    const p = App.state.project; const so = p.solver;
    const lockedPlans = p.plans.filter((x) => Object.keys(x.locks || {}).length);
    main.innerHTML = `
      <div class="panel"><h2>1단계 · 조건 충돌 사전 검사</h2>
        <p class="muted small">자동 편성 전에 필수 조건끼리 부딪히지 않는지 확인합니다. 문제가 있으면 관련 학생과 조건을 보여주고, 해당 설정 화면으로 바로 이동할 수 있습니다. 프로그램은 교사가 승인하지 않은 필수 조건 완화를 하지 않습니다.</p>
        <button class="btn" id="preGo">조건 충돌 검사</button><div id="preOut">${this.pre ? this.preHtml(this.pre) : ''}</div></div>
      <div class="panel"><h2>2단계 · 자동 편성</h2>
        <p class="muted small">① 필수 조건을 모두 만족하는 배치를 먼저 찾고 ② 필수 조건을 지키는 이동·교환만 하면서 균형 조건을 개선합니다. 서로 충분히 다른 대안을 최대 3개 제시합니다(학급 이름만 바뀐 결과는 같은 대안으로 봅니다).
        같은 자료와 같은 난수 시드로 실행하면 같은 결과가 나옵니다.</p>
        <div class="row">
          <label class="field"><span>난수 시드 (결과 재현용 번호)</span><div class="row"><input type="number" id="sSeed" value="${esc(so.seed)}" style="width:140px"><button class="btn btn-sm" id="sNewSeed">새 번호</button></div></label>
          <label class="field"><span>대안 개수</span><select id="sAlt">${[1, 2, 3].map((n) => `<option ${Number(so.alternatives) === n ? 'selected' : ''}>${n}</option>`).join('')}</select></label>
          <label class="field"><span>꼼꼼함</span><select id="sEff"><option value="fast" ${so.effort === 'fast' ? 'selected' : ''}>빠르게</option><option value="normal" ${so.effort === 'normal' ? 'selected' : ''}>보통 (권장)</option><option value="thorough" ${so.effort === 'thorough' ? 'selected' : ''}>꼼꼼하게 (오래 걸림)</option></select></label>
        </div>
        ${lockedPlans.length ? `<label class="chk"><input type="checkbox" id="sKeep"> 고정한 학생을 유지하고 나머지만 재편성 — 기준 편성안: <select id="sKeepPlan">${lockedPlans.map((x) => `<option value="${esc(x.id)}" ${x.id === p.active_plan_id ? 'selected' : ''}>${esc(x.name)} (고정 ${Object.keys(x.locks).length}명)</option>`).join('')}</select></label>` : '<p class="small muted">결과 화면에서 학생이나 학급을 고정하면, 고정을 유지한 채 나머지만 다시 편성할 수 있습니다.</p>'}
        <div class="row" style="margin-top:8px"><button class="btn btn-pri" id="sGo">▶ 자동 편성 시작</button></div>
        <div id="sProg" class="hidden" style="margin-top:12px"><div class="progress"><div style="width:0%"></div></div><div class="row" style="margin-top:6px"><span id="sMsg" class="grow"></span><button class="btn btn-danger" id="sCancel">편성 취소</button></div></div>
        <div id="sOut">${this.last ? this.resultHtml(this.last) : ''}</div></div>`;
    const sv = () => { so.seed = Number(main.querySelector('#sSeed').value) || 1; so.alternatives = Number(main.querySelector('#sAlt').value); so.effort = main.querySelector('#sEff').value; App.changed({ keepEval: true }); };
    ['#sSeed', '#sAlt', '#sEff'].forEach((id) => { main.querySelector(id).onchange = sv; });
    main.querySelector('#sNewSeed').onclick = () => { main.querySelector('#sSeed').value = Math.floor(Math.random() * 900000) + 1000; sv(); };
    main.querySelector('#preGo').onclick = async () => { this.pre = await App.api('POST', 'precheck', { project: p }); main.querySelector('#preOut').innerHTML = this.preHtml(this.pre); };
    main.querySelector('#sGo').onclick = () => {
      sv();
      const keep = main.querySelector('#sKeep'); let locks = {}; let base = null;
      if (keep && keep.checked) { base = p.plans.find((x) => x.id === main.querySelector('#sKeepPlan').value); locks = base.locks; }
      App.runSolve({ seed: so.seed, alternatives: so.alternatives, effort: so.effort }, locks, base, main, (res) => { this.last = res; main.querySelector('#sOut').innerHTML = this.resultHtml(res); this.bindResult(main); });
    };
    this.bindResult(main);
  },

  preHtml(pc) {
    const n = pc.errors.length;
    return `<div class="notice ${n ? 'n-bad' : 'n-ok'}" style="margin-top:10px">${n ? `✖ 편성할 수 없게 만드는 필수 조건 충돌 ${n}건이 있습니다. 아래 문제를 먼저 해결하세요.` : '✔ 필수 조건 충돌이 없습니다. 자동 편성을 시작할 수 있습니다.'}
      ${pc.warnings.length ? ` · 주의 ${pc.warnings.length}건` : ''}${pc.infos.length ? ` · 안내 ${pc.infos.length}건` : ''}</div>
      ${pc.errors.concat(pc.warnings, pc.infos).map((i) => App.issueHtml(i)).join('')}`;
  },

  resultHtml(res) {
    if (!res) return '';
    if (res.status === 'precheck_failed') return `<div class="notice n-bad" style="margin-top:12px"><b>✖ 편성을 시작하지 않았습니다 — 조건 충돌</b><br>${esc(res.message)}</div>${this.preHtml(res.precheck)}`;
    if (res.status === 'infeasible') return `<div class="notice n-bad" style="margin-top:12px"><b>✖ 조건상 편성이 불가능합니다 (모든 경우를 확인함)</b><br>${esc(res.message)}</div>`;
    if (res.status === 'not_found') return `<div class="notice n-warn" style="margin-top:12px"><b>⚠ 제한 안에서 편성안을 찾지 못했습니다 (불가능하다고 확인된 것은 아님)</b><br>${esc(res.message)}</div>`;
    if (res.status === 'cancelled') return `<div class="notice n-info" style="margin-top:12px">${esc(res.message)}</div>`;
    if (res.status === 'error') return `<div class="notice n-bad" style="margin-top:12px">${esc(res.message)}</div>`;
    const names = App.state.project.classes.map((c) => c.name);
    return `<div class="notice n-ok" style="margin-top:12px"><b>✔ ${esc(res.message)}</b> (시드 ${esc(res.seed)}) — 편성안 목록에 추가되었습니다.</div>
      <div class="grid2">${res.alternatives.map((a, i) => { const r = a.report; return `<div class="panel tight"><h3 style="margin-top:4px">대안 ${i + 1} — ${esc(a.planName || '')}</h3>
        <div>${r.hard.ok ? '<span class="badge b-ok">✔ 필수 조건 모두 충족</span>' : '<span class="badge b-bad">✖ 필수 조건 위반</span>'}
        <span class="badge b-ok">✔ 고름 ${r.summary.good}</span> <span class="badge b-warn">△ 약간 차이 ${r.summary.caution}</span> <span class="badge b-bad">✖ 차이 큼 ${r.summary.bad}</span>
        <span class="badge ${r.soft.unmet.length ? 'b-warn' : 'b-ok'}">선호 조건 미충족 ${r.soft.unmet.length}개</span></div>
        <div class="small" style="margin-top:4px">학급별 인원: ${r.classes.map((c) => `${esc(c.name)} ${c.size}`).join(' · ')}</div>
        <table class="tbl compact" style="margin-top:6px"><tbody>${r.items.filter((x) => x.enabled).map((x) => `<tr><td>${esc(x.name)}</td><td>${App.statusBadge(x.status, x.status_label)}${x.data_limited ? ' <span class="badge b-info">ⓘ 자료 부족</span>' : ''}</td><td class="small">최대 차이 ${x.max_dev}명</td></tr>`).join('')}</tbody></table>
        ${r.soft.unmet.length ? `<details><summary>충족하지 못한 선호 조건</summary><ul>${r.soft.unmet.map((u) => `<li class="small">${esc(App.state.share ? u.message.replace(/[가-힣A-Za-z]+\(S?[\w-]+\)/g, '○○') : u.message)}</li>`).join('')}</ul></details>` : ''}
        <button class="btn btn-sm" data-openplan="${esc(a.planId)}">결과 화면에서 보기 ▸</button></div>`; }).join('')}</div>
      ${res.differences.length ? `<h3>편성 결과 간 차이</h3><p class="small muted">학급 이름을 서로 맞바꿔 가장 비슷하게 맞춘 뒤에도 다른 반인 학생 수입니다 (같은 대안으로 보는 기준: ${res.min_diff}명 미만).</p><ul>${res.differences.map((d) => `<li>대안 ${d.a + 1} ↔ 대안 ${d.b + 1}: <b>${d.students}명</b> 다름</li>`).join('')}</ul>` : ''}
      <p class="small muted">학급 순서: ${names.map(esc).join(', ')}</p>`;
  },
  bindResult(main) { main.querySelectorAll('[data-openplan]').forEach((b) => { b.onclick = () => { App.state.project.active_plan_id = b.dataset.openplan; App.changed({ keepEval: true }); App.go('results'); }; }); },
};

/* 자동 편성 실행 (진행 상태·취소 포함). base 가 있으면 그 편성안의 고정을 유지한 재편성 */
App.runSolve = async function (options, locks, base, main, onDone) {
  const p = App.state.project;
  if (App.state.dirty) await App.save();
  let prog = main.querySelector('#sProg');
  let modal = null;
  if (!prog) {
    modal = App.modal({ title: '자동 편성 중', closable: false, body: '<div id="sProg"><div class="progress"><div style="width:0%"></div></div><div class="row" style="margin-top:6px"><span id="sMsg" class="grow"></span><button class="btn btn-danger" id="sCancel">편성 취소</button></div></div>', buttons: [] });
    prog = modal.el.querySelector('#sProg');
  }
  prog.classList.remove('hidden');
  const bar = prog.querySelector('.progress > div'); const msg = prog.querySelector('#sMsg');
  const goBtn = main.querySelector('#sGo'); if (goBtn) goBtn.disabled = true;
  let job;
  try { job = await App.api('POST', 'solve', { project: p, options, locks: locks || {} }); } catch (e) { App.toast(e.message, 'err'); if (modal) modal.close(); return; }
  prog.querySelector('#sCancel').onclick = async () => { msg.textContent = '취소하는 중…'; await App.api('POST', `jobs/${job.job_id}/cancel`, {}); };
  const poll = async () => {
    let st;
    try { st = await App.api('GET', 'jobs/' + job.job_id); } catch (e) { msg.textContent = e.message; return finish({ status: 'error', message: e.message }); }
    bar.style.width = st.progress + '%'; msg.textContent = `${st.message} (${Math.round(st.progress)}%)`;
    if (st.status === 'running') return setTimeout(poll, 400);
    finish(st.result || { status: 'error', message: st.error || '편성 결과를 받지 못했습니다. 다시 시도하세요.' });
  };
  const finish = (res) => {
    if (goBtn) goBtn.disabled = false;
    prog.classList.add('hidden'); if (modal) modal.close();
    if (res.status === 'ok') {
      const stamp = App.nowIso().slice(5, 16).replace('T', ' ');
      res.alternatives.forEach((a, i) => {
        const id = App.uid('pl');
        const name = base ? `${base.name} → 고정 유지 재편성 ${i + 1}` : `대안 ${i + 1} (${stamp}, 시드 ${res.seed})`;
        p.plans.push({ id, name, created_at: App.nowIso(), seed: res.seed, run: a.run, effort: res.effort, source: base ? 'rerun' : 'auto',
          assignment: a.assignment, original: App.clone(a.assignment), locks: App.clone(locks || {}), confirmed: false, new_numbers: {}, based_on: base ? base.id : null });
        a.planId = id; a.planName = name;
      });
      p.active_plan_id = res.alternatives[0].planId;
      App.log('자동 편성', `${base ? '고정 유지 재편성' : '자동 편성'}: 대안 ${res.alternatives.length}개 생성 (시드 ${res.seed})`);
      App.changed();
    }
    onDone(res);
  };
  poll();
};
