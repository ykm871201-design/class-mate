/* ⑥ 결과 비교 및 조정 */
'use strict';
App.tabs.results = {
  sel: [], showFeat: null, side: 'balance', facts: null, aiExplain: null, fixRes: null, causes: {},

  async render(main) {
    const p = App.state.project; const plan = App.plan();
    if (!p.plans.length || !plan) {
      if (p.plans.length && !plan) { p.active_plan_id = p.plans[0].id; return this.render(main); }
      main.innerHTML = '<div class="panel"><h2>결과 비교 및 조정</h2><p>아직 편성안이 없습니다. ⑤ 자동 편성을 먼저 실행하세요.</p><button class="btn btn-pri" data-goto=\'{"tab":"solve"}\'>⑤ 자동 편성으로 이동 ▸</button></div>';
      return;
    }
    plan.locks = plan.locks || {};
    if (!App.state.evalCache[plan.id]) main.innerHTML = '<div class="panel">균형 상태를 계산하는 중…</div>';
    let rep;
    try { rep = await App.evaluatePlan(plan); } catch (e) { main.innerHTML = `<div class="notice n-bad">${esc(e.message)}</div>`; return; }
    this.rep = rep; this.plan = plan;
    const items = rep.items;
    if (!this.showFeat) this.showFeat = items.filter((x) => x.kind === 'feature' && x.enabled).slice(0, 2).map((x) => x.id);
    this.sel = this.sel.filter((k) => plan.assignment[k]);
    const unitOf = {}; rep.units.forEach((u) => u.forEach((k) => { unitOf[k] = u; }));
    this.unitOf = unitOf;
    const h = App.hist(plan);
    const s = rep.summary;
    const conf = plan.confirmed;
    main.innerHTML = `
      <div class="plan-tabs">${p.plans.map((x) => `<button class="btn btn-sm ${x.id === plan.id ? 'active' : ''}" data-plan="${esc(x.id)}">${x.confirmed ? '✅ ' : ''}${esc(x.name)}</button>`).join('')}
        <span class="grow"></span><button class="btn btn-sm" id="pRen">이름 바꾸기</button><button class="btn btn-sm" id="pCopy">복사본 만들기</button><button class="btn btn-sm btn-danger" id="pDel">이 편성안 삭제</button></div>
      ${conf ? `<div class="notice n-ok">✅ 최종 확정된 편성안입니다. 수정하려면 확정을 해제하세요. <button class="btn btn-sm" id="pUnconf">확정 해제</button></div>` : ''}
      <div class="toolbar" id="toolbar">
        <button class="btn btn-sm" id="uUndo" ${h.undo.length && !conf ? '' : 'disabled'} title="${esc(h.undo.length ? h.undo[h.undo.length - 1].label : '')}">↶ 실행 취소</button>
        <button class="btn btn-sm" id="uRedo" ${h.redo.length && !conf ? '' : 'disabled'}>↷ 다시 실행</button>
        <span class="muted">|</span><span id="selInfo" class="grow">${this.selHtml(plan)}</span>
        <button class="btn btn-sm" id="rRerun" ${conf ? 'disabled' : ''}>🔒 고정 유지하고 나머지 재편성</button>
        <button class="btn btn-sm" id="rCmp">⇄ 편성안 비교</button>
        <details style="position:relative"><summary class="btn btn-sm">카드에 표시할 특성</summary><div class="panel tight" style="position:absolute;right:0;z-index:30;min-width:260px">
          ${App.state.share ? '<p class="small muted">화면 공유용 보기에서는 학생별 특성 표시를 숨깁니다.</p>' : ''}
          ${items.filter((x) => x.kind === 'feature' || x.kind === 'combo').map((x) => `<label class="chk" style="display:flex"><input type="checkbox" class="sfSel" value="${esc(x.id)}" ${this.showFeat.includes(x.id) ? 'checked' : ''}> ${esc(x.name)}</label>`).join('')}</div></details>
      </div>
      <div class="panel tight row">
        <b>필수 조건:</b> ${rep.hard.ok ? '<span class="badge b-ok">✔ 모두 충족</span>' : `<span class="badge b-bad">✖ 위반 ${rep.hard.violations.length}건</span>`}
        <b>균형:</b> <span class="badge b-ok">✔ 고름 ${s.good}</span><span class="badge b-warn">△ 약간 차이 ${s.caution}</span><span class="badge b-bad">✖ 차이 큼 ${s.bad}</span>
        <b>선호 조건:</b> <span class="badge ${rep.soft.unmet.length ? 'b-warn' : 'b-ok'}">${rep.soft.met}/${rep.soft.total} 충족</span>
        <b>배정:</b> ${s.n_assigned}/${s.n_eligible}명
        <span class="legend grow" style="text-align:right">🔒 고정 · 🔗 반드시 같은 반 그룹 · ✎ 원래 자동 편성안에서 옮겨진 학생 · 노란색 = 선택됨</span>
      </div>
      ${rep.hard.ok ? '' : `<div class="notice n-bad"><b>✖ 필수 조건 위반 (이 상태로는 확정할 수 없습니다)</b><ul>${rep.hard.violations.map((v) => `<li>${esc(this.mask(v.message))}${v.relation ? ` <button class="btn btn-sm" data-goto='${esc(JSON.stringify({ tab: 'relations', relation: v.relation }))}'>조건 보기 ▸</button>` : ''}</li>`).join('')}</ul></div>`}
      <div class="board" id="board">${rep.classes.map((c, k) => this.columnHtml(c, k, plan, rep)).join('')}</div>
      <div class="panel" style="margin-top:12px"><div class="sidetabs">${[['balance', '항목별 균형 상태'], ['cross', '현재 반 × 새 학급'], ['cond', '조건 충족 현황'], ['assist', '설명 · 수정 제안']].map(([k, l]) => `<button class="btn btn-sm ${this.side === k ? 'active' : ''}" data-side="${k}">${l}</button>`).join('')}</div>
        <div id="sideBody">${this.sideHtml(rep, plan)}</div></div>`;
    this.bind(main, plan, rep);
  },

  mask(t) { return App.state.share ? String(t).replace(/[가-힣A-Za-z]+\(S?[\w-]+\)/g, '○○') : t; },

  selHtml(plan) {
    const conf = plan.confirmed;
    if (!this.sel.length) return '<span class="muted">학생을 누르면 선택됩니다. 끌어서 다른 반에 놓으면 이동 전에 영향을 미리 보여 줍니다. 두 명을 고르면 교환할 수 있습니다.</span>';
    const p = App.state.project;
    if (this.sel.length === 1) {
      const k = this.sel[0]; const st = App.stuByKey(k); const cur = plan.assignment[k]; const locked = !!plan.locks[k]; const u = this.unitOf[k];
      return `선택: <b>${esc(App.dnFull(st))}</b> (${esc(App.className(cur))}) ${conf ? '' : `→ 이동할 반: ${p.classes.filter((c) => c.id !== cur).map((c) => `<button class="btn btn-sm" data-moveto="${esc(c.id)}">${esc(c.name)}</button>`).join(' ')}`}
        ${u ? `<span class="badge b-info">🔗 같은 반 그룹 ${u.length}명</span>` : ''}
        ${conf ? '' : `<button class="btn btn-sm" id="tLock">${locked ? '🔓 고정 해제' : '🔒 이 학생 고정'}</button>`} <button class="btn btn-sm" id="tClear">선택 해제</button>`;
    }
    const [a, b] = this.sel; const ca = plan.assignment[a], cb = plan.assignment[b];
    return `선택: <b>${esc(App.dn(App.stuByKey(a)))}</b>(${esc(App.className(ca))}) · <b>${esc(App.dn(App.stuByKey(b)))}</b>(${esc(App.className(cb))})
      ${ca === cb ? '<span class="muted">같은 반 학생끼리는 교환할 수 없습니다.</span>' : (conf ? '' : '<button class="btn btn-sm btn-pri" id="tSwap">⇄ 두 학생 교환 미리보기</button>')} <button class="btn btn-sm" id="tClear">선택 해제</button>`;
  },

  columnHtml(c, k, plan, rep) {
    const p = App.state.project; const share = App.state.share;
    const keys = Object.keys(plan.assignment).filter((x) => plan.assignment[x] === c.id && App.stuByKey(x));
    keys.sort((x, y) => (share ? App.stuByKey(x)._seq - App.stuByKey(y)._seq : (App.stuByKey(x).name || '').localeCompare(App.stuByKey(y).name || '', 'ko')));
    const allLocked = keys.length && keys.every((x) => plan.locks[x]);
    const viol = rep.hard.violations.filter((v) => v.class === c.id || (v.students || []).some((x) => plan.assignment[x] === c.id)).length;
    const feats = this.showFeat.map((id) => rep.items.find((x) => x.id === id)).filter(Boolean);
    const dist = feats.map((it) => {
      const cats = it.method === 'count' || it.kind === 'combo' ? it.cats : it.display;
      let t = cats.map((ct) => `<span>${esc(ct.label.replace(/^(\d+) \((.+)\)$/, '$1단계'))} ${ct.counts[k]}</span>`).join('');
      if (it.mean) t += `<span>평균 ${it.mean.class_means[k] ?? '-'}</span>`;
      if (it.missing && it.missing.by_class[k]) t += `<span>미입력 ${it.missing.by_class[k]}</span>`;
      return `<div class="dist"><b>${esc(it.name)}</b><div class="dist-mini">${t}</div></div>`;
    }).join('');
    const showTraitBadges = !share;
    const distHtml = share ? '<div class="small muted">(화면 공유용 보기: 특성 분포 숨김)</div>' : dist;
    const featDefs = this.showFeat.filter((id) => id.startsWith('feature:')).map((id) => p.features.find((f) => 'feature:' + f.id === id)).filter(Boolean);
    return `<div class="ccol ${c.over ? 'over' : ''}" data-col="${esc(c.id)}">
      <div class="chead"><div class="row"><span class="cname grow">${esc(c.name)}</span>${plan.confirmed ? '' : `<button class="btn btn-sm" data-lockcls="${esc(c.id)}" title="이 학급의 모든 학생 고정/해제">${allLocked ? '🔓 학급 고정 해제' : '🔒 학급 고정'}</button>`}</div>
        <div class="meta"><b>${c.size}명</b> / 목표 ${c.target} · 최대 ${c.max} ${c.over ? '<span class="badge b-bad">⚠ 정원 초과</span>' : ''}</div>
        <div class="meta">${Object.entries(c.gender).map(([g, n]) => `${esc(g)} ${n}`).join(' · ')}</div>
        <div class="meta small">출신: ${Object.entries(c.origin).map(([o, n]) => `${esc(o)} ${n}`).join(' · ')}</div>
        <div class="meta">${viol ? `<span class="badge b-bad">✖ 필수 조건 위반 ${viol}건</span>` : '<span class="badge b-ok">✔ 필수 조건 충족</span>'}</div>
        ${distHtml}</div>
      <div class="cbody">${keys.map((x) => {
        const st = App.stuByKey(x); const moved = plan.original && plan.original[x] && plan.original[x] !== plan.assignment[x];
        const tags = showTraitBadges ? featDefs.map((f) => { const v = (st.traits || {})[f.id]; const t = App.isMissing(f, v) ? '미입력' : App.traitText(f, v, true); return `<span class="tag" title="${esc(f.name)}: ${esc(App.traitText(f, v))}">${esc(t.length > 6 ? t.slice(0, 6) + '…' : t)}</span>`; }).join('') : '';
        return `<div class="stu ${this.sel.includes(x) ? 'sel' : ''} ${moved ? 'moved' : ''}" draggable="${plan.confirmed ? 'false' : 'true'}" data-stu="${esc(x)}" tabindex="0" title="${esc(App.dnFull(st))} ${esc(App.stuInfo(st))}">
          ${plan.locks[x] ? '<span title="고정">🔒</span>' : ''}${this.unitOf[x] ? '<span title="반드시 같은 반 그룹">🔗</span>' : ''}${moved ? '<span title="원래 편성안에서 옮겨짐">✎</span>' : ''}
          <span>${esc(App.dn(st))}</span><span class="g">${esc(share ? '' : (st.gender || ''))} ${esc(share ? '' : (st.cls || (st.transfer_in ? '전입' : '')))}</span><span class="tb">${tags}</span></div>`;
      }).join('')}</div></div>`;
  },

  sideHtml(rep, plan) {
    const names = rep.classes.map((c) => c.name);
    if (this.side === 'cross') {
      return `<p class="small muted">현재 반 학생들이 새 학급에 얼마나 고르게 나뉘었는지 보여 줍니다.</p><table class="tbl compact" style="max-width:900px"><thead><tr><th>현재 반</th>${names.map((n) => `<th class="num">${esc(n)}</th>`).join('')}<th class="num">합계</th></tr></thead><tbody>
        ${rep.cross.rows.map((r) => `<tr><td>${esc(r.origin)}</td>${r.counts.map((x) => `<td class="num">${x}</td>`).join('')}<td class="num"><b>${r.total}</b></td></tr>`).join('')}
        <tr><td><b>합계</b></td>${rep.classes.map((c) => `<td class="num"><b>${c.size}</b></td>`).join('')}<td class="num"><b>${rep.summary.n_assigned}</b></td></tr></tbody></table>`;
    }
    if (this.side === 'cond') {
      return `<h3>필수 조건</h3>${rep.hard.ok ? '<div class="notice n-ok">✔ 모든 필수 조건을 충족합니다 (누락·중복 배정 없음, 정원·지정 배정·고정·반드시 조건 모두 충족).</div>' : `<ul>${rep.hard.violations.map((v) => `<li>✖ ${esc(this.mask(v.message))}</li>`).join('')}</ul>`}
        <h3>충족하지 못한 선호(가급적) 조건 (${rep.soft.unmet.length}/${rep.soft.total})</h3>${rep.soft.unmet.length ? `<ul>${rep.soft.unmet.map((u) => `<li>△ ${esc(this.mask(u.message))} <button class="btn btn-sm" data-goto='${esc(JSON.stringify({ tab: 'relations', relation: u.relation }))}'>보기 ▸</button></li>`).join('')}</ul>` : '<p>✔ 모두 충족</p>'}
        <h3>반드시 같은 반 그룹 (함께 이동)</h3>${rep.units.length ? `<ul>${rep.units.map((u) => `<li>🔗 ${u.map((k) => esc(App.dnKey(k))).join(', ')} — ${esc(App.className(plan.assignment[u[0]]))}</li>`).join('')}</ul>` : '<p class="muted">없음</p>'}
        <h3>고정된 학생 (${Object.keys(plan.locks).length}명)</h3><p class="small">${Object.keys(plan.locks).map((k) => esc(App.dnKey(k)) + ' → ' + esc(App.className(plan.locks[k]))).join(', ') || '없음'}</p>`;
    }
    if (this.side === 'assist') return this.assistHtml(rep, plan);
    return `<p class="small muted">기대 인원은 학급 목표 인원 비율로 계산합니다. ‘최대 차이’는 학급별 실제 인원과 기대 인원의 가장 큰 차이입니다. 미입력 학생은 따로 세며 0이나 ‘해당 없음’으로 보지 않습니다.</p>
      <div class="tbl-wrap" style="max-height:none"><table class="tbl compact"><thead><tr><th>항목</th><th>편성 반영</th><th>상태</th><th class="num">최대 차이</th><th>학급별 분포 (${names.map(esc).join(' / ')})</th><th></th></tr></thead><tbody>
      ${rep.items.map((it) => `<tr ${it.enabled ? '' : 'style="opacity:.7"'}><td><b>${esc(it.name)}</b>${it.count_desc ? `<div class="small muted">${esc(it.count_desc)}</div>` : ''}</td>
        <td class="small">${it.enabled ? '✔ ' + esc(it.importance_label) : '참고용'}</td><td>${App.statusBadge(it.status, it.status_label)}${it.data_limited ? '<div><span class="badge b-info">ⓘ 자료 부족</span></div>' : ''}</td><td class="num">${it.max_dev}</td>
        <td class="small">${App.state.share && (it.kind === 'feature' || it.kind === 'combo') ? '<span class="muted">(화면 공유용 보기에서 숨김)</span>' : (it.method === 'count' || it.kind === 'combo' || it.kind === 'size' ? it.cats : it.display).map((c) => `<div>${esc(c.label)} (${c.total}명): <b>${c.counts.join(' / ')}</b> <span class="muted">기대 ${c.expected.map((e) => App.fmtNum(e)).join('/')}</span></div>`).join('')}
          ${it.mean && !(App.state.share && it.kind === 'feature') ? `<div>평균: <b>${it.mean.class_means.map((m) => m ?? '-').join(' / ')}</b> (전체 ${it.mean.overall})</div>` : ''}
          ${it.missing && it.missing.total && it.kind !== 'size' ? `<div>미입력: ${it.missing.by_class.join(' / ')} (계 ${it.missing.total})</div>` : ''}
          ${it.na ? `<div>해당 없음: ${it.na.by_class.join(' / ')}</div>` : ''}${it.multi_note ? `<div class="muted">${esc(it.multi_note)}</div>` : ''}${it.data_note ? `<div class="muted">${esc(it.data_note)}</div>` : ''}${it.note ? `<div class="muted">${esc(it.note)}</div>` : ''}
          ${this.causes[it.id] ? `<div class="notice n-info">${esc(this.causes[it.id])}</div>` : ''}</td>
        <td>${it.enabled && it.status !== 'good' && it.kind !== 'size' ? `<button class="btn btn-sm" data-cause="${esc(it.id)}">원인 확인(재계산)</button>` : ''}</td></tr>`).join('')}
      </tbody></table></div>`;
  },

  assistHtml(rep, plan) {
    const items = rep.items.filter((x) => x.enabled);
    return `<div class="grid2"><div>
        <h3 style="margin-top:0">결과 설명 (프로그램이 계산한 실제 값)</h3>
        <button class="btn btn-sm" id="fLoad">설명 만들기</button> <button class="btn btn-sm" id="fAI">🤖 AI로 쉽게 정리하기</button>
        <div id="factsBox">${this.facts ? `<ul>${this.facts.map((f) => `<li class="small">${esc(this.mask(f.text))}</li>`).join('')}</ul>` : '<p class="small muted">‘설명 만들기’를 누르면 인원·분포·조건 충족 여부를 문장으로 정리합니다. 확인되지 않은 원인은 ‘가능성’으로 구분합니다.</p>'}</div>
        <div id="aiExplainBox">${this.aiExplain || ''}</div></div>
      <div><h3 style="margin-top:0">수정 제안 (알고리즘이 실제 이동·교환을 계산)</h3>
        <textarea id="fixText" placeholder="예: 3반의 학습 지원 부담을 조금 줄여줘. / 고정된 학생은 유지하면서 활동성 분포를 더 균형 있게 해줘. / 학생 이동을 최소화하면서 반별 인원을 맞춰줘."></textarea>
        <button class="btn btn-sm" id="fixAI">🤖 AI로 수정 조건 만들기</button>
        <details style="margin-top:8px" open><summary>직접 조건 정하기 (AI 없이)</summary>
          <div class="row" style="margin-top:6px"><label class="field"><span>항목</span><select id="fxItem">${items.map((x) => `<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('')}</select></label>
          <label class="field"><span>학급 (선택)</span><select id="fxCls"><option value="">전체 학급</option>${rep.classes.map((c) => `<option value="${esc(c.id)}">${esc(c.name)}</option>`).join('')}</select></label>
          <label class="field"><span>방향</span><select id="fxDir"><option value="balance">고르게 하기</option><option value="decrease">이 학급에서 줄이기</option><option value="increase">이 학급에서 늘리기</option></select></label>
          <label class="field"><span>최대 이동 학생 수</span><input type="number" id="fxMax" value="6" min="1" max="40" style="width:90px"></label>
          <label class="chk"><input type="checkbox" id="fxMin" checked> 이동 최소화</label></div>
          <button class="btn btn-sm" id="fxGo">수정 후보 계산</button></details>
        <p class="small muted">후보는 고정 학생과 필수 조건을 모두 지킨 것만 표시됩니다. ‘적용’을 누르기 전에는 편성안이 바뀌지 않으며, 적용 후 실행 취소할 수 있습니다.</p>
        <div id="fixBox">${this.fixRes ? this.fixHtml(this.fixRes) : ''}</div></div></div>`;
  },

  fixHtml(r) {
    const sf = r.fix || r;
    let head = '';
    if (r.objective_text) head = `<div class="notice n-info"><b>AI가 만든 수정 조건 (검증 통과):</b> ${r.objective_text.map(esc).join(' / ')} · 최대 ${r.objective.max_moved}명 이동${r.explanation ? `<div class="small">${esc(r.explanation)}</div>` : ''}${(r.notes || []).map((n) => `<div class="small">ⓘ ${esc(n)}</div>`).join('')}</div>${App.tabs.relations.listHtml('확인이 필요한 부분', r.unclear)}`;
    if (!sf.ok) return head + `<div class="notice n-bad">${esc(sf.message)}</div>`;
    if (!sf.candidates.length) return head + `<div class="notice n-warn">${esc(sf.message)}</div>`;
    return head + `<p>${esc(sf.message)}</p>` + sf.candidates.map((c, i) => `<div class="panel tight"><b>후보 ${i + 1}</b> — 이동 학생 <b>${c.moved_count}명</b> · ${c.hard_ok ? '<span class="badge b-ok">✔ 필수 조건 충족</span>' : '<span class="badge b-bad">✖</span>'}
      <div class="small">이동·교환: ${c.moves.map((m) => `${esc(App.dnKey(m.key))} ${esc(m.from)}→${esc(m.to)}`).join(', ')}</div>
      <div class="small">학급별 인원: ${c.class_names.map((n, j) => `${esc(n)} ${c.sizes_before[j]}→${c.sizes_after[j]}`).join(' · ')} · 선호 조건 미충족 ${c.soft_before}→${c.soft_after}개</div>
      ${c.focus_change.filter((f) => f.class).map((f) => `<div class="small">${esc(f.name)} · ${esc(f.class)} ‘${esc(f.category)}’: ${f.before}명 → <b>${f.after}명</b></div>`).join('')}
      ${c.improved.length ? `<div class="small trend-better">▲ 좋아지는 항목: ${c.improved.map((x) => `${esc(x.name)}(${x.before_dev}→${x.after_dev})`).join(', ')}</div>` : ''}
      ${c.worse.length ? `<div class="small trend-worse">▼ 나빠지는 항목: ${c.worse.map((x) => `${esc(x.name)}(${x.before_dev}→${x.after_dev})`).join(', ')}</div>` : '<div class="small">나빠지는 항목 없음</div>'}
      <button class="btn btn-sm btn-pri" data-applyfix="${i}" ${this.plan.confirmed ? 'disabled' : ''}>이 후보 적용</button></div>`).join('');
  },

  bind(main, plan, rep) {
    const p = App.state.project; const re = () => this.render(main);
    const refresh = () => { App.state.evalCache = {}; App.changed({ keepEval: false }); this.render(main); };
    main.querySelectorAll('[data-plan]').forEach((b) => { b.onclick = () => { p.active_plan_id = b.dataset.plan; this.sel = []; this.facts = null; this.aiExplain = null; this.fixRes = null; this.causes = {}; App.changed({ keepEval: true }); re(); }; });
    main.querySelector('#pRen').onclick = () => App.modal({ title: '편성안 이름 바꾸기', body: `<input type="text" id="nn" value="${esc(plan.name)}" style="width:100%">`, buttons: [{ label: '취소' }, { label: '저장', cls: 'btn-pri', onClick: (el) => { const v = el.querySelector('#nn').value.trim(); if (v) { plan.name = v; App.changed({ keepEval: true }); re(); } } }] });
    main.querySelector('#pCopy').onclick = () => { const c = App.clone(plan); c.id = App.uid('pl'); c.name = plan.name + ' (복사본)'; c.confirmed = false; c.created_at = App.nowIso(); p.plans.push(c); p.active_plan_id = c.id; App.log('교사', `편성안 복사: ${c.name}`); App.changed(); re(); };
    main.querySelector('#pDel').onclick = async () => { if (!await App.confirm('편성안 삭제', `‘${esc(plan.name)}’ 편성안을 삭제합니다.`, '삭제', true)) return; p.plans = p.plans.filter((x) => x !== plan); p.active_plan_id = p.plans.length ? p.plans[0].id : null; App.log('교사', `편성안 삭제: ${plan.name}`); App.changed(); re(); };
    const unc = main.querySelector('#pUnconf'); if (unc) unc.onclick = () => { plan.confirmed = false; App.log('교사', `확정 해제: ${plan.name}`); App.changed({ keepEval: true }); re(); };
    main.querySelector('#uUndo').onclick = () => this.undo(plan, refresh);
    main.querySelector('#uRedo').onclick = () => this.redo(plan, refresh);
    main.querySelectorAll('.sfSel').forEach((c) => { c.onchange = () => { this.showFeat = App.$$('.sfSel:checked', main).map((x) => x.value); re(); }; });
    main.querySelectorAll('[data-side]').forEach((b) => { b.onclick = () => { this.side = b.dataset.side; re(); }; });
    // 학생 선택 / 끌어 놓기
    main.querySelectorAll('[data-stu]').forEach((el) => {
      el.onclick = () => { const k = el.dataset.stu; if (this.sel.includes(k)) this.sel = this.sel.filter((x) => x !== k); else { this.sel.push(k); if (this.sel.length > 2) this.sel.shift(); } re(); };
      el.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); el.click(); } };
      el.ondragstart = (e) => { e.dataTransfer.setData('text/plain', el.dataset.stu); e.dataTransfer.effectAllowed = 'move'; };
    });
    main.querySelectorAll('[data-col]').forEach((col) => {
      col.ondragover = (e) => { if (plan.confirmed) return; e.preventDefault(); col.classList.add('drop'); };
      col.ondragleave = () => col.classList.remove('drop');
      col.ondrop = (e) => { e.preventDefault(); col.classList.remove('drop'); const k = e.dataTransfer.getData('text/plain'); if (!k || plan.assignment[k] === col.dataset.col) return; this.preview(plan, [{ key: k, to: col.dataset.col }], refresh); };
    });
    main.querySelectorAll('[data-moveto]').forEach((b) => { b.onclick = () => this.preview(plan, [{ key: this.sel[0], to: b.dataset.moveto }], refresh); });
    const sw = main.querySelector('#tSwap'); if (sw) sw.onclick = () => { const [a, b] = this.sel; this.preview(plan, [{ key: a, to: plan.assignment[b] }, { key: b, to: plan.assignment[a] }], refresh, true); };
    const cl = main.querySelector('#tClear'); if (cl) cl.onclick = () => { this.sel = []; re(); };
    const lk = main.querySelector('#tLock'); if (lk) lk.onclick = () => { const k = this.sel[0]; App.pushHistory(plan, '고정 변경'); if (plan.locks[k]) delete plan.locks[k]; else plan.locks[k] = plan.assignment[k]; App.changed({ keepEval: false }); refresh(); };
    main.querySelectorAll('[data-lockcls]').forEach((b) => {
      b.onclick = () => {
        const cid = b.dataset.lockcls; const keys = Object.keys(plan.assignment).filter((k) => plan.assignment[k] === cid);
        const all = keys.every((k) => plan.locks[k]); App.pushHistory(plan, '학급 고정 변경');
        keys.forEach((k) => { if (all) delete plan.locks[k]; else plan.locks[k] = cid; });
        App.log('교사', `${App.className(cid)} ${all ? '학급 고정 해제' : '학급 전체 고정'} (${keys.length}명)`); refresh();
      };
    });
    main.querySelector('#rRerun').onclick = () => this.rerun(plan, main);
    main.querySelector('#rCmp').onclick = () => this.compareDialog(plan);
    main.querySelectorAll('[data-cause]').forEach((b) => {
      b.onclick = async () => { b.disabled = true; b.textContent = '재계산 중…'; try { const r = await App.api('POST', 'analyze-item', { project: p, assignment: plan.assignment, locks: plan.locks, item_id: b.dataset.cause }); this.causes[b.dataset.cause] = r.message; } catch (e) { App.toast(e.message, 'err'); } re(); };
    });
    // 설명 · 수정 제안
    const fl = main.querySelector('#fLoad');
    if (fl) {
      fl.onclick = async () => { const r = await App.api('POST', 'facts', { project: p, assignment: plan.assignment, locks: plan.locks }); this.facts = r.facts; re(); };
      main.querySelector('#fAI').onclick = () => App.ai.run('explain', { assignment: plan.assignment, locks: plan.locks }, (res) => {
        this.aiExplain = res.ok ? `<div class="notice n-info"><b>🤖 AI 정리 (숫자 검증 통과 — 프로그램 계산 값만 사용)</b><p>${esc(res.summary)}</p><ul>${res.points.map((x) => `<li class="small">${esc(x)}</li>`).join('')}</ul>${res.possible_causes.length ? `<b>가능성 (확인되지 않음)</b><ul>${res.possible_causes.map((x) => `<li class="small">${esc(x)}</li>`).join('')}</ul>` : ''}</div>`
          : App.ai.errorsHtml(res) + `<p class="small">프로그램 계산 설명:</p><ul>${(res.facts || []).map((f) => `<li class="small">${esc(f)}</li>`).join('')}</ul>`;
        re();
      });
      main.querySelector('#fixAI').onclick = () => {
        const text = main.querySelector('#fixText').value.trim(); if (!text) return App.toast('수정 요청을 입력하세요.', 'err');
        const base = JSON.stringify(plan.assignment);
        App.ai.run('fix', { text, assignment: plan.assignment, locks: plan.locks }, (res) => { this.fixRes = res.ok ? res : { ok: false, message: (res.errors || []).join(' / ') || res.message, candidates: [] }; this.fixBase = base; re(); });
      };
      main.querySelector('#fxGo').onclick = async () => {
        const v = (id) => main.querySelector(id).value;
        const obj = { focus: [{ target: v('#fxItem'), class_id: v('#fxCls') || null, direction: v('#fxCls') ? v('#fxDir') : 'balance', category: null }], max_moved: Number(v('#fxMax')) || 6, minimize_moves: main.querySelector('#fxMin').checked, keep_locked: true };
        const b = main.querySelector('#fxGo'); b.disabled = true; b.textContent = '계산 중…';
        try { this.fixRes = await App.api('POST', 'suggest-fix', { project: p, assignment: plan.assignment, locks: plan.locks, objective: obj }); this.fixBase = JSON.stringify(plan.assignment); } catch (e) { App.toast(e.message, 'err'); }
        re();
      };
    }
    main.querySelectorAll('[data-applyfix]').forEach((b) => {
      b.onclick = () => {
        const sf = this.fixRes.fix || this.fixRes; const c = sf.candidates[Number(b.dataset.applyfix)];
        if (this.fixBase !== JSON.stringify(plan.assignment)) return App.toast('후보를 계산한 뒤 편성안이 바뀌었습니다. 다시 계산하세요.', 'err');
        App.pushHistory(plan, `수정 후보 적용 (${c.moved_count}명 이동)`);
        plan.assignment = App.clone(c.assignment);
        App.log(this.fixRes.objective_text ? 'AI 제안(교사 확인)' : '교사', `수정 후보 적용: ${c.moves.map((m) => `${m.from}→${m.to}`).join(', ')} (${c.moved_count}명)`);
        this.fixRes = null; App.toast('수정 후보를 적용했습니다. ‘실행 취소’로 되돌릴 수 있습니다.', 'ok'); refresh();
      };
    });
  },

  async preview(plan, changes, refresh, isSwap) {
    const p = App.state.project;
    if (plan.confirmed) return App.toast('확정된 편성안은 수정할 수 없습니다. 먼저 확정을 해제하세요.', 'err');
    let r;
    try { r = await App.api('POST', 'preview', { project: p, assignment: plan.assignment, locks: plan.locks, changes }); } catch (e) { return App.toast(e.message, 'err'); }
    const desc = changes.map((c) => `${App.dn(App.stuByKey(c.key))}: ${App.className(plan.assignment[c.key])} → ${App.className(c.to)}`).join(', ');
    const body = `<p><b>${isSwap ? '교환' : '이동'}:</b> ${esc(desc)}</p>
      <h3>이동 후 학급별 인원</h3><table class="tbl compact"><thead><tr>${r.class_names.map((n) => `<th class="num">${esc(n)}</th>`).join('')}</tr></thead><tbody><tr>${r.sizes_after.map((s, i) => `<td class="num">${r.sizes_before[i] !== s ? `${r.sizes_before[i]} → <b>${s}</b>` : s}${s > r.caps[i] ? ' <span class="badge b-bad">⚠ 정원 초과</span>' : ''}</td>`).join('')}</tr></tbody></table>
      <h3>필수 조건</h3>${r.new_violations.length ? `<div class="notice n-bad"><b>✖ 이 이동은 필수 조건을 위반하므로 확정할 수 없습니다.</b><ul>${r.new_violations.map((v) => `<li>${esc(this.mask(v.message))}</li>`).join('')}</ul>
        필요하면 관련 조건(관계 조건·지정 배정·고정·정원)을 직접 수정하세요. <button class="btn btn-sm" data-goto='{"tab":"relations"}'>관계 및 편성 조건으로 이동 ▸</button></div>`
        : (r.allowed ? '<div class="notice n-ok">✔ 이동 후에도 모든 필수 조건을 충족합니다.</div>' : '<div class="notice n-warn">이 이동으로 새로 생기는 위반은 없지만, 기존 필수 조건 위반이 남아 있어 확정할 수 없습니다.</div>')}
      ${r.group_hint.length ? `<div class="notice n-info">🔗 이 학생은 ‘반드시 같은 반’ 그룹(${r.group_hint[0].members.map((k) => esc(App.dn(App.stuByKey(k)))).join(', ')})에 속합니다. 그룹 전체를 함께 옮길 수 있습니다.</div>` : ''}
      <h3>균형 항목 변화</h3><table class="tbl compact"><thead><tr><th>항목</th><th>이동 전</th><th>이동 후</th><th>변화</th></tr></thead><tbody>
      ${r.items.map((it) => `<tr><td>${esc(it.name)}</td><td>${esc(it.before)} (${it.before_dev})</td><td>${esc(it.after)} (${it.after_dev})</td><td>${it.trend === 'better' ? '<span class="trend-better">▲ 좋아짐</span>' : it.trend === 'worse' ? '<span class="trend-worse">▼ 나빠짐</span>' : '= 같음'}</td></tr>`).join('')}</tbody></table>
      <p class="small">‘가급적’ 조건 미충족: ${r.soft_before}개 → <b>${r.soft_after}개</b></p>`;
    const buttons = [{ label: '취소' }];
    if (r.group_hint.length) {
      const g = r.group_hint[0];
      buttons.push({ label: `🔗 그룹 ${g.members.length}명 함께 이동 미리보기`, onClick: () => { const to = g.to; const rest = changes.filter((c) => !g.members.includes(c.key)); this.preview(plan, rest.concat(g.members.map((k) => ({ key: k, to }))), refresh, isSwap); } });
    }
    buttons.push({
      label: isSwap ? '교환 확정' : '이동 확정', cls: 'btn-pri', disabled: !r.allowed, onClick: () => {
        App.pushHistory(plan, desc);
        changes.forEach((c) => { plan.assignment[c.key] = c.to; if (plan.locks[c.key]) plan.locks[c.key] = c.to; });
        App.log('교사', `수동 ${isSwap ? '교환' : '이동'}: ${changes.map((c) => `${App.stuByKey(c.key).sid} → ${App.className(c.to)}`).join(', ')}`);
        this.sel = []; refresh();
      },
    });
    App.modal({ title: isSwap ? '교환 영향 미리보기' : '이동 영향 미리보기', body, buttons, wide: true });
  },

  undo(plan, refresh) { const h = App.hist(plan); const s = h.undo.pop(); if (!s) return; h.redo.push({ a: App.clone(plan.assignment), l: App.clone(plan.locks), label: s.label }); plan.assignment = s.a; plan.locks = s.l; App.toast('실행 취소: ' + s.label); refresh(); },
  redo(plan, refresh) { const h = App.hist(plan); const s = h.redo.pop(); if (!s) return; h.undo.push({ a: App.clone(plan.assignment), l: App.clone(plan.locks), label: s.label }); plan.assignment = s.a; plan.locks = s.l; App.toast('다시 실행: ' + s.label); refresh(); },

  rerun(plan, main) {
    const n = Object.keys(plan.locks).length;
    if (!n) return App.toast('고정된 학생이 없습니다. 학생을 선택해 ‘고정’하거나 학급 머리의 ‘학급 고정’을 누르세요.', 'err');
    const so = App.state.project.solver;
    App.modal({
      title: '고정 유지하고 나머지 재편성',
      body: `<p>고정된 학생 <b>${n}명</b>은 지금 학급에 그대로 두고, 나머지 학생만 다시 편성합니다. 결과는 새 편성안으로 추가되며 현재 편성안은 바뀌지 않습니다.</p>
        <div class="row"><label class="field"><span>대안 개수</span><select id="rrN"><option>1</option><option>2</option><option selected>3</option></select></label><label class="field"><span>난수 시드</span><input type="number" id="rrSeed" value="${esc(so.seed)}"></label></div>`,
      buttons: [{ label: '취소' }, {
        label: '재편성 시작', cls: 'btn-pri', onClick: (el) => {
          const opts = { seed: Number(el.querySelector('#rrSeed').value) || so.seed, alternatives: Number(el.querySelector('#rrN').value), effort: so.effort };
          setTimeout(() => App.runSolve(opts, plan.locks, plan, main, (res) => {
            if (res.status === 'ok') { App.toast('고정을 유지한 새 편성안을 만들었습니다.', 'ok'); this.sel = []; this.render(main); } else App.modal({ title: '재편성 결과', body: App.tabs.solve.resultHtml(res), wide: true });
          }), 10);
        },
      }],
    });
  },

  compareDialog(plan) {
    const p = App.state.project;
    const opts = [];
    p.plans.forEach((x) => { opts.push([x.id + '|cur', `${x.name} (현재 상태)`]); opts.push([x.id + '|orig', `${x.name} (원래 자동 편성 결과)`]); });
    const m = App.modal({
      title: '편성안 비교', wide: true,
      body: `<div class="row"><label class="field grow"><span>A</span><select id="cA">${opts.map(([v, l]) => `<option value="${esc(v)}" ${v === plan.id + '|orig' ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select></label>
        <label class="field grow"><span>B</span><select id="cB">${opts.map(([v, l]) => `<option value="${esc(v)}" ${v === plan.id + '|cur' ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select></label><button class="btn btn-pri" id="cGo" style="margin-top:14px">비교</button></div><div id="cOut"></div>`,
    });
    const get = (v) => { const [id, kind] = v.split('|'); const x = p.plans.find((y) => y.id === id); return kind === 'orig' ? (x.original || x.assignment) : x.assignment; };
    const go = async () => {
      const a = m.el.querySelector('#cA'), b = m.el.querySelector('#cB');
      const r = await App.api('POST', 'compare', { project: p, a: get(a.value), b: get(b.value), label_a: a.selectedOptions[0].text, label_b: b.selectedOptions[0].text });
      m.el.querySelector('#cOut').innerHTML = `<div class="notice n-info">학급이 달라진 학생 <b>${r.moved_count}명</b> · 학급 이름을 서로 맞바꿔 가장 비슷하게 맞춘 뒤에도 다른 학생 <b>${r.structural}명</b></div>
        <div class="row"><span>필수 조건: A ${r.hard_a ? '✔' : '✖'} · B ${r.hard_b ? '✔' : '✖'}</span><span>선호 조건 미충족: A ${r.soft_a}개 · B ${r.soft_b}개</span></div>
        <table class="tbl compact"><thead><tr><th>균형 항목</th><th>A</th><th>B</th></tr></thead><tbody>${r.items.map((it) => `<tr><td>${esc(it.name)}</td><td>${esc(it.a)} (${it.a_dev})</td><td>${esc(it.b)} (${it.b_dev})</td></tr>`).join('')}</tbody></table>
        <h3>학급이 다른 학생</h3><div class="tbl-wrap" style="max-height:260px"><table class="tbl compact"><tbody>${r.moved.map((x) => `<tr><td>${esc(App.dnKey(x.key))}</td><td>${esc(x.from)} → ${esc(x.to)}</td></tr>`).join('') || '<tr><td>없음</td></tr>'}</tbody></table></div>`;
    };
    m.el.querySelector('#cGo').onclick = go; go();
  },
};
