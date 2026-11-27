/* ④ 학생 간 관계 및 편성 조건 */
'use strict';
App.tabs.relations = {
  async render(main, opts) {
    const p = App.state.project; const plan = App.plan(); const d = App.state.defaults;
    let rep = null;
    if (plan) { try { rep = await App.evaluatePlan(plan); } catch (_) { rep = null; } }
    const unmet = new Set(); const hardBad = new Set();
    if (rep) { rep.soft.unmet.forEach((u) => unmet.add(u.relation)); rep.hard.violations.forEach((v) => { if (v.relation) hardBad.add(v.relation); }); }
    const fixed = p.students.filter((s) => s.fixed_class);
    const share = App.state.share;
    main.innerHTML = `
      <div class="panel"><div class="row"><h2 class="grow">학생 간 관계 조건 (${p.relations.length}개)</h2>
        <button class="btn btn-pri" id="rAdd">＋ 관계 추가</button></div>
        <p class="muted small">🔒 <b>반드시</b> = 필수 조건(항상 지킴, 프로그램이 스스로 완화하지 않음) · ◇ <b>가급적</b> = 균형 조건(가능하면 지킴).
        여러 명을 한 그룹으로 지정할 수 있습니다. 예: 5명 그룹에서 ‘모두 서로 다른 반’과 ‘반마다 최대 2명’은 서로 다른 조건입니다.
        형제자매·쌍둥이·친구 같은 사유만으로 같은 반/다른 반이 자동 결정되지 않으며, 교사가 지정한 조건만 따릅니다. 사유는 결과 명단에 기본적으로 표시되지 않습니다.</p>
        ${p.relations.length ? `<div class="tbl-wrap"><table class="tbl compact"><thead><tr><th class="num">#</th><th>강도</th><th>조건</th><th>대상 학생</th>${share ? '' : '<th>사유</th>'}<th>${plan ? `현재 편성안(${esc(plan.name)}) 충족` : '충족 여부'}</th><th></th></tr></thead><tbody>
        ${p.relations.map((r, i) => `<tr data-rel="${esc(r.id)}"><td class="num">${i + 1}</td><td>${App.strengthBadge(r)}${r.strength === 'prefer' ? `<div class="small muted">중요도 ${esc(App.IMP[r.importance || 'high'])}</div>` : ''}</td><td>${esc(App.relKindText(r))}</td>
          <td>${r.kind === 'pairs_diff' ? r.pairs.map(([a, b]) => `<span class="chip">${esc(App.dnKey(a))} ↔ ${esc(App.dnKey(b))}</span>`).join('') : r.members.map((k) => `<span class="chip">${esc(App.dnKey(k))}${App.stuByKey(k) && App.stuByKey(k).eligible === false ? ' (편성 제외)' : ''}</span>`).join('')}</td>
          ${share ? '' : `<td class="small">${esc(r.reason || '')}</td>`}
          <td>${!rep ? '<span class="muted small">편성안 없음</span>' : (r.strength === 'must' ? (hardBad.has(r.id) ? '<span class="badge b-bad">✖ 위반</span>' : '<span class="badge b-ok">✔ 충족</span>') : (unmet.has(r.id) ? '<span class="badge b-warn">△ 미충족</span>' : '<span class="badge b-ok">✔ 충족</span>'))}</td>
          <td><div class="btn-group"><button class="btn btn-sm" data-redit="${esc(r.id)}">편집</button><button class="btn btn-sm btn-danger" data-rdel="${esc(r.id)}">삭제</button></div></td></tr>`).join('')}
        </tbody></table></div>` : '<p class="muted">설정된 관계 조건이 없습니다.</p>'}
      </div>
      <div class="panel" id="fixedPanel"><h2>지정 배정 (필수 조건: 특정 학생을 특정 학급에)</h2>
        <div class="row"><div class="grow" id="fxPick" style="max-width:420px"></div><select id="fxCls">${p.classes.map((c) => `<option value="${esc(c.id)}">${esc(c.name)}</option>`).join('')}</select><span class="muted small">학생을 검색해 고르면 선택한 학급에 지정됩니다.</span></div>
        ${fixed.length ? `<table class="tbl compact" style="margin-top:8px;max-width:700px"><tbody>${fixed.map((s) => `<tr><td>${esc(App.dnFull(s))}</td><td><select data-fx="${esc(s.key)}">${p.classes.map((c) => `<option value="${esc(c.id)}" ${s.fixed_class === c.id ? 'selected' : ''}>${esc(c.name)}</option>`).join('')}</select></td><td><button class="btn btn-sm btn-danger" data-fxdel="${esc(s.key)}">지정 해제</button></td></tr>`).join('')}</tbody></table>` : '<p class="muted">지정 배정된 학생이 없습니다.</p>'}
      </div>
      <div class="panel" id="balPanel"><h2>균형 조건 (가능한 한 맞추도록 개선, 중요도 조절)</h2>
        <p class="muted small">중요도가 높을수록 그 항목을 우선하여 고르게 맞춥니다. 학급별 목표 인원이 다르면 규모에 비례한 기대 인원과 비교합니다.</p>
        <table class="tbl compact" style="max-width:1000px"><thead><tr><th>균형 조건</th><th>사용</th><th>중요도</th><th>방식</th></tr></thead><tbody>
        ${[['size', d.builtin_items['builtin:size']], ['gender', d.builtin_items['builtin:gender']], ['origin', d.builtin_items['builtin:origin'] + ' (현재 반 × 새 학급 표로 확인)']].map(([k, n]) => `<tr><td>${esc(n)}</td><td class="num"><input type="checkbox" data-bb="${k}" ${p.balance[k].enabled ? 'checked' : ''} aria-label="사용"></td><td>${App.impSelect(p.balance[k].importance, `data-bi="${k}"`)}</td><td class="small muted">${k === 'size' ? '목표 인원 비율에 맞춤' : '선택지별 인원을 규모에 비례하게'}</td></tr>`).join('')}
        ${App.activeFeatures().map((f) => `<tr><td>${esc(f.name)} <span class="small muted">(${esc(f.category || '')})</span></td><td class="num"><input type="checkbox" data-fu="${esc(f.id)}" ${f.use_in_balance && f.method !== 'none' ? 'checked' : ''} aria-label="사용"></td><td>${App.impSelect(f.importance, `data-fi="${esc(f.id)}"`)}</td>
          <td><select data-fm="${esc(f.id)}">${d.allowed_methods[f.type].filter((m) => m !== 'none').map((m) => `<option value="${m}" ${f.method === m ? 'selected' : ''}>${esc(d.methods[m])}</option>`).join('')}</select></td></tr>`).join('')}
        ${p.combos.map((cb) => `<tr><td>조합: ${esc(cb.name)}</td><td class="num"><input type="checkbox" data-cu="${esc(cb.id)}" ${cb.use_in_balance ? 'checked' : ''} aria-label="사용"></td><td>${App.impSelect(cb.importance, `data-ci="${esc(cb.id)}"`)}</td><td class="small muted">조건에 모두 해당하는 학생 수</td></tr>`).join('')}
        <tr><td>‘가급적’ 관계 조건</td><td class="num">✔</td><td colspan="2" class="small muted">관계마다 따로 중요도를 정합니다 (관계 편집 화면)</td></tr>
        </tbody></table>
        <p class="small muted">학습 수준처럼 단계가 있는 항목은 ‘단계별 분포 + 평균’을 쓰면 평균만 같고 상·하위 학생이 몰리는 문제를 함께 막습니다.</p>
      </div>
      <div class="panel" id="aiDir"><h2>🤖 문장으로 편성 방향 설정 (AI 보조 · 선택)</h2>
        <p class="muted small">요청을 문장으로 쓰면 현재 프로젝트에 실제로 있는 특성 항목과 연결하여 균형 조건 설정을 <b>제안</b>합니다. 적용 전 ‘현재 설정 → 제안 설정’을 비교하고 원하는 것만 고를 수 있습니다. 모호한 요청은 필수 조건으로 바꾸지 않습니다.</p>
        <textarea id="aiText" placeholder="예: 학습 지원이 필요한 학생을 고르게 나누고, 활동성이 높은 학생들이 한 반에 몰리지 않도록 해줘. 각 반에 협력 활동을 이끌 수 있는 학생도 골고루 배치해줘."></textarea>
        <div class="row" style="margin-top:6px"><button class="btn btn-pri" id="aiGo">제안 받기</button><span class="small muted">AI 연결이 꺼져 있으면 안내가 표시됩니다. 내장 간이 해석기를 고르면 외부 전송 없이 체험할 수 있습니다.</span></div>
        <div id="aiOut"></div>
      </div>`;
    this.bind(main);
    if (opts && opts.relation) App.flashRow(`tr[data-rel="${opts.relation}"]`);
    else if (opts && opts.section) App.flashRow('#' + opts.section);
  },

  bind(main) {
    const p = App.state.project; const re = () => { App.state.evalCache = {}; this.render(main); };
    main.querySelector('#rAdd').onclick = () => this.editor(null, re);
    main.querySelectorAll('[data-redit]').forEach((b) => { b.onclick = () => this.editor(p.relations.find((r) => r.id === b.dataset.redit), re); });
    main.querySelectorAll('[data-rdel]').forEach((b) => {
      b.onclick = async () => { const r = p.relations.find((x) => x.id === b.dataset.rdel); if (!await App.confirm('관계 조건 삭제', `<p>${App.strengthBadge(r)} ${esc(App.relKindText(r))} 조건을 삭제합니다.</p>`, '삭제', true)) return; p.relations = p.relations.filter((x) => x !== r); App.log('교사', `관계 조건 삭제 (${App.relKindText(r)})`); App.changed(); re(); };
    });
    App.studentPicker(main.querySelector('#fxPick'), {
      filter: (s) => s.eligible !== false,
      onPick: (k) => { const s = App.stuByKey(k); s.fixed_class = main.querySelector('#fxCls').value; App.log('교사', `지정 배정: ${s.sid} → ${App.className(s.fixed_class)}`); App.changed(); re(); },
    });
    main.querySelectorAll('[data-fx]').forEach((s) => { s.onchange = () => { App.stuByKey(s.dataset.fx).fixed_class = s.value; App.changed(); }; });
    main.querySelectorAll('[data-fxdel]').forEach((b) => { b.onclick = () => { App.stuByKey(b.dataset.fxdel).fixed_class = null; App.changed(); re(); }; });
    main.querySelectorAll('[data-bb]').forEach((c) => { c.onchange = () => { p.balance[c.dataset.bb].enabled = c.checked; App.changed(); }; });
    main.querySelectorAll('[data-bi]').forEach((c) => { c.onchange = () => { p.balance[c.dataset.bi].importance = c.value; App.changed(); }; });
    const F = (id) => p.features.find((f) => f.id === id);
    main.querySelectorAll('[data-fu]').forEach((c) => { c.onchange = () => { const f = F(c.dataset.fu); f.use_in_balance = c.checked; if (c.checked && f.method === 'none') f.method = App.state.defaults.allowed_methods[f.type][0]; App.changed(); }; });
    main.querySelectorAll('[data-fi]').forEach((c) => { c.onchange = () => { F(c.dataset.fi).importance = c.value; App.changed(); }; });
    main.querySelectorAll('[data-fm]').forEach((c) => { c.onchange = () => { F(c.dataset.fm).method = c.value; App.changed(); }; });
    main.querySelectorAll('[data-cu]').forEach((c) => { c.onchange = () => { p.combos.find((x) => x.id === c.dataset.cu).use_in_balance = c.checked; App.changed(); }; });
    main.querySelectorAll('[data-ci]').forEach((c) => { c.onchange = () => { p.combos.find((x) => x.id === c.dataset.ci).importance = c.value; App.changed(); }; });
    main.querySelector('#aiGo').onclick = () => {
      const text = main.querySelector('#aiText').value.trim(); if (!text) return App.toast('요청 문장을 입력하세요.', 'err');
      App.ai.run('settings', { text }, (res) => this.showProposal(main, res, re));
    };
  },

  editor(r, done) {
    const p = App.state.project; const isNew = !r;
    const cur = r ? App.clone(r) : { id: App.uid('r'), kind: 'all_diff', strength: 'must', members: [], pairs: [], max_n: 2, reason: '', importance: 'high' };
    const kinds = [['same', '모두 같은 반', '그룹의 학생 모두를 한 학급에'], ['all_diff', '모두 서로 다른 반', '그룹의 학생이 모두 서로 다른 학급에 (학생 수 ≤ 학급 수)'],
      ['pairs_diff', '특정 학생 쌍끼리 다른 반', '그룹 안에서 지정한 두 학생끼리만 다른 학급에'], ['max_per_class', '각 반에 최대 N명', '그룹의 학생이 한 학급에 N명보다 많이 몰리지 않게']];
    const m = App.modal({
      title: isNew ? '관계 조건 추가' : '관계 조건 편집', wide: true,
      body: `<div class="row"><b>빠른 선택:</b>
          <button class="btn btn-sm" data-q="must,all_diff">반드시 다른 반</button><button class="btn btn-sm" data-q="prefer,all_diff">가급적 다른 반</button>
          <button class="btn btn-sm" data-q="must,same">반드시 같은 반</button><button class="btn btn-sm" data-q="prefer,same">가급적 같은 반</button></div>
        <h3>1. 조건의 강도</h3><label class="chk"><input type="radio" name="rS" value="must"> 🔒 반드시 (필수 조건)</label><label class="chk"><input type="radio" name="rS" value="prefer"> ◇ 가급적 (균형 조건)</label>
        <span id="rImpWrap"> 중요도 ${App.impSelect(cur.importance || 'high', 'id="rImp"')}</span>
        <h3>2. 그룹의 의미</h3>${kinds.map(([k, l, dsc]) => `<label class="chk" style="display:flex;margin:4px 0"><input type="radio" name="rK" value="${k}"> <b>${l}</b> <span class="small muted">— ${dsc}</span></label>`).join('')}
        <div id="rN" class="row"><span>반마다 최대</span><input type="number" id="rMax" min="1" value="${esc(cur.max_n || 2)}" style="width:80px"><span>명</span></div>
        <h3>3. 대상 학생 (이름 또는 학생 ID로 검색 — 동명이인은 ID와 현재 반으로 구분)</h3><div id="rPick"></div><div id="rMem" style="margin-top:6px"></div>
        <div id="rPairs"></div>
        <h3>4. 사유 (선택 · 결과 명단에는 기본적으로 표시되지 않음)</h3><textarea id="rReason" placeholder="예: 교사 판단">${esc(App.state.share ? '' : cur.reason || '')}</textarea>
        <div id="rWarn"></div>`,
      buttons: [{ label: '취소' }, {
        label: '저장', cls: 'btn-pri', onClick: (el) => {
          read(el);
          if (cur.kind !== 'max_per_class' && cur.members.length < 2) { App.toast('학생을 2명 이상 고르세요.', 'err'); return false; }
          if (cur.kind === 'max_per_class' && (!cur.members.length || !(cur.max_n >= 1))) { App.toast('학생을 고르고 최대 인원 N을 1 이상으로 입력하세요.', 'err'); return false; }
          if (cur.kind === 'pairs_diff') { cur.pairs = cur.pairs.filter(([a, b]) => cur.members.includes(a) && cur.members.includes(b)); if (!cur.pairs.length) { App.toast('다른 반이어야 하는 학생 쌍을 1개 이상 추가하세요.', 'err'); return false; } }
          if (App.state.share && r) cur.reason = r.reason;
          if (isNew) p.relations.push(cur); else Object.assign(r, cur);
          App.log('교사', `관계 조건 ${isNew ? '추가' : '수정'}: ${cur.strength === 'must' ? '반드시' : '가급적'} ${App.relKindText(cur)} (${cur.members.length}명)`);
          App.changed(); done(); return true;
        },
      }],
    });
    const el = m.el;
    const read = () => {
      cur.strength = el.querySelector('input[name=rS]:checked').value; cur.kind = el.querySelector('input[name=rK]:checked').value;
      cur.max_n = Number(el.querySelector('#rMax').value); cur.importance = el.querySelector('#rImp').value; cur.reason = el.querySelector('#rReason').value.trim();
    };
    const setRadios = () => { el.querySelector(`input[name=rS][value=${cur.strength}]`).checked = true; el.querySelector(`input[name=rK][value=${cur.kind}]`).checked = true; };
    const refresh = () => {
      el.querySelector('#rImpWrap').classList.toggle('hidden', cur.strength !== 'prefer');
      el.querySelector('#rN').classList.toggle('hidden', cur.kind !== 'max_per_class');
      el.querySelector('#rMem').innerHTML = cur.members.length ? cur.members.map((k) => `<span class="chip">${esc(App.dnFull(App.stuByKey(k)))} <span class="small muted">${esc(App.stuInfo(App.stuByKey(k)))}</span><button data-rm="${esc(k)}" aria-label="빼기">×</button></span>`).join('') : '<span class="muted">아직 고른 학생이 없습니다.</span>';
      App.$$('[data-rm]', el).forEach((b) => { b.onclick = () => { cur.members = cur.members.filter((k) => k !== b.dataset.rm); cur.pairs = cur.pairs.filter((pr) => !pr.includes(b.dataset.rm)); refresh(); }; });
      const pr = el.querySelector('#rPairs');
      if (cur.kind === 'pairs_diff') {
        const opts = cur.members.map((k) => `<option value="${esc(k)}">${esc(App.dnFull(App.stuByKey(k)))}</option>`).join('');
        pr.innerHTML = `<h3>다른 반이어야 하는 학생 쌍</h3><div class="row"><select id="pA">${opts}</select> ↔ <select id="pB">${opts}</select><button class="btn btn-sm" id="pAdd">쌍 추가</button></div>
          <div>${cur.pairs.map(([a, b], i) => `<span class="chip">${esc(App.dnKey(a))} ↔ ${esc(App.dnKey(b))}<button data-pdel="${i}">×</button></span>`).join('') || '<span class="muted">쌍이 없습니다.</span>'}</div>`;
        const pa = pr.querySelector('#pAdd'); if (pa) pa.onclick = () => { const a = pr.querySelector('#pA').value, b = pr.querySelector('#pB').value; if (!a || a === b) return App.toast('서로 다른 두 학생을 고르세요.', 'err'); if (cur.pairs.some(([x, y]) => (x === a && y === b) || (x === b && y === a))) return; cur.pairs.push([a, b]); refresh(); };
        App.$$('[data-pdel]', pr).forEach((b) => { b.onclick = () => { cur.pairs.splice(Number(b.dataset.pdel), 1); refresh(); }; });
      } else pr.innerHTML = '';
      const K = p.classes.length; let w = '';
      const elig = cur.members.filter((k) => App.stuByKey(k) && App.stuByKey(k).eligible !== false).length;
      if (cur.kind === 'all_diff' && cur.strength === 'must' && elig > K) w = `⚠ 학생 ${elig}명을 모두 다른 반에 배치하려면 학급이 ${elig}개 이상 필요하지만 학급은 ${K}개입니다. ‘각 반에 최대 N명’을 검토하세요.`;
      if (cur.kind === 'max_per_class' && elig > cur.max_n * K) w = `⚠ ${elig}명을 ${K}개 학급에 반마다 최대 ${cur.max_n}명씩 배치할 수 없습니다.`;
      if (cur.members.some((k) => App.stuByKey(k) && App.stuByKey(k).eligible === false)) w += ' ⓘ 편성 제외 학생은 이 조건에서 무시됩니다.';
      el.querySelector('#rWarn').innerHTML = w ? `<div class="notice n-warn">${esc(w)}</div>` : '';
    };
    setRadios();
    App.$$('input[name=rS],input[name=rK]', el).forEach((x) => { x.onchange = () => { read(); refresh(); }; });
    el.querySelector('#rMax').onchange = () => { read(); refresh(); };
    App.$$('[data-q]', el).forEach((b) => { b.onclick = () => { const [s, k] = b.dataset.q.split(','); cur.strength = s; cur.kind = k; setRadios(); refresh(); }; });
    App.studentPicker(el.querySelector('#rPick'), { onPick: (k) => { if (!cur.members.includes(k)) cur.members.push(k); refresh(); } });
    refresh();
  },

  showProposal(main, res, done) {
    const out = main.querySelector('#aiOut'); const p = App.state.project; const d = App.state.defaults;
    if (!res.ok) { out.innerHTML = App.ai.errorsHtml(res) + this.listHtml('확인이 필요한 부분', res.unclear) + this.listHtml('필요한 항목·자료가 없음', res.missing); return; }
    const fmt = (o) => o ? [o.use_in_balance === undefined ? '' : (o.use_in_balance ? '반영' : '반영 안 함'), o.method ? d.methods[o.method] : '', o.importance ? '중요도 ' + App.IMP[o.importance] : '',
      o.count_values && o.count_values.length ? '기준값 ' + o.count_values.join('·') : '', o.count_min !== undefined && o.count_min !== null ? '기준 ' + o.count_min + ' 이상' : ''].filter(Boolean).join(' · ') : '';
    out.innerHTML = `<h3>AI 제안 (검증 통과 · ${esc(res.provider)} ${esc(res.model)})</h3>
      ${res.interpretation ? `<p>${esc(res.interpretation)}</p>` : ''}
      ${res.changes.length ? `<table class="tbl compact"><thead><tr><th>적용</th><th>항목</th><th>현재 설정</th><th>→ 제안 설정</th><th>제안 이유</th></tr></thead><tbody>
      ${res.changes.map((c, i) => `<tr><td class="num"><input type="checkbox" class="apSel" value="${i}" checked></td><td><b>${esc(c.name)}</b></td><td class="small">${esc(fmt(c.current))}</td><td class="small"><b>${esc(fmt(c.proposed))}</b></td><td class="small">${esc(c.reason)}</td></tr>`).join('')}</tbody></table>` : '<p class="muted">바꿀 설정 제안이 없습니다.</p>'}
      ${res.new_combos.length ? `<h3>새 특성 조합 제안</h3>${res.new_combos.map((cb, i) => `<div class="panel tight"><label class="chk"><input type="checkbox" class="apCombo" value="${i}"> <b>${esc(cb.name)}</b></label>
        <div class="small">집계 기준: ${esc(App.tabs.features.comboDesc(cb))} 인 학생 · 중요도 ${esc(App.IMP[cb.importance])}</div>${App.state.share ? '' : App.tabs.features.comboStatsHtml(cb)}<div class="small muted">${esc(cb.reason)}</div></div>`).join('')}` : ''}
      ${this.listHtml('확인이 필요한 부분 (적용되지 않음)', res.unclear)}${this.listHtml('필요한 항목·자료가 없음', res.missing)}
      <button class="btn btn-pri" id="apGo">선택한 제안 적용</button> <span class="small muted">적용 내용은 ⑦ 변경 기록에 남고, 그곳에서 되돌릴 수 있습니다.</span>`;
    out.querySelector('#apGo').onclick = () => {
      const sel = App.$$('.apSel:checked', out).map((c) => res.changes[Number(c.value)]);
      const combos = App.$$('.apCombo:checked', out).map((c) => res.new_combos[Number(c.value)]);
      if (!sel.length && !combos.length) return App.toast('적용할 제안을 고르세요.', 'err');
      const before = { features: App.clone(p.features), balance: App.clone(p.balance), combos: App.clone(p.combos) };
      sel.forEach((c) => {
        const pr = c.proposed;
        if (c.target.startsWith('builtin:')) { const b = p.balance[c.target.split(':')[1]]; b.enabled = pr.use_in_balance; b.importance = pr.importance; }
        else if (c.target.startsWith('combo:')) { const cb = p.combos.find((x) => 'combo:' + x.id === c.target); cb.use_in_balance = pr.use_in_balance; cb.importance = pr.importance; }
        else { const f = p.features.find((x) => 'feature:' + x.id === c.target); f.use_in_balance = pr.use_in_balance; f.method = pr.method; f.importance = pr.importance; if (pr.count_values) f.count_values = pr.count_values; if (pr.count_min !== undefined) f.count_min = pr.count_min; }
      });
      combos.forEach((cb) => p.combos.push({ id: App.uid('cb'), name: cb.name, conds: cb.conds, use_in_balance: true, importance: cb.importance }));
      App.log('AI 제안(교사 확인)', `편성 방향 제안 적용: 설정 ${sel.length}건, 새 조합 ${combos.length}개 — ${sel.map((c) => c.name).join(', ')}`, { type: 'settings', before });
      App.changed(); App.toast('선택한 제안을 적용했습니다.', 'ok'); done();
    };
  },
  listHtml: (t, arr) => arr && arr.length ? `<div class="notice n-warn"><b>${esc(t)}</b><ul>${arr.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div>` : '',
};
