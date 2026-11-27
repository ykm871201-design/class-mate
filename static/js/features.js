/* 특성 항목 관리 · 특성 조합 · 메모 태그 후보 */
'use strict';
App.tabs.features = {
  render(main) {
    const p = App.state.project; const d = App.state.defaults;
    const cats = [...new Set(p.features.map((f) => f.category || '기타'))];
    const elig = App.eligible();
    const status = (f) => { if (f.type === 'text') return ''; const miss = elig.filter((s) => App.isMissing(f, (s.traits || {})[f.id])).length; return `입력 ${elig.length - miss}명 · 미입력 ${miss}명`; };
    main.innerHTML = `
      <div class="panel"><div class="row"><h2 class="grow">특성 항목 관리</h2><button class="btn btn-pri" id="fAdd">＋ 새 특성 항목</button></div>
        <div class="notice n-info">· 예시 항목이 준비되어 있습니다. <b>필요한 항목만 ‘사용’을 켜세요.</b> 켠 항목만 학생 명단의 ‘③ 특성 입력’ 화면과 엑셀 양식에 나타납니다.<br>
        · 특성은 교사가 입력한 정보만 사용하며, 프로그램이 학생 특성을 추정하거나 진단하지 않습니다. 학생을 낙인찍는 표현 대신 ‘지원 필요 정도’처럼 표현하세요.<br>
        · ‘편성 반영’을 끄면 참고용으로만 보관됩니다 (예: 숫자로 입력하지만 균형 계산에 쓰지 않는 항목). 자유 메모는 편성에 자동 반영되지 않습니다.<br>
        · 선택지·단계가 많아도 영향이 커지지 않도록 항목마다 정규화하여 계산합니다.</div></div>
      ${cats.map((c) => `<div class="panel"><h3 style="margin-top:0">${esc(c)}</h3><div class="tbl-wrap" style="max-height:none"><table class="tbl compact"><thead><tr><th>사용</th><th>항목명</th><th>입력 형식</th><th>선택지·범위</th><th>편성 반영</th><th>균형 배치 방식</th><th>중요도</th><th>결과 파일 포함</th><th>입력 현황</th><th></th></tr></thead><tbody>
        ${p.features.filter((f) => (f.category || '기타') === c).map((f) => `<tr data-fid="${esc(f.id)}" ${f.active ? '' : 'style="opacity:.65"'}>
          <td class="num"><input type="checkbox" data-fa="${esc(f.id)}" ${f.active ? 'checked' : ''} aria-label="사용"></td>
          <td><b>${esc(f.name)}</b><div class="small muted">${esc(f.desc || '')}</div></td>
          <td>${esc(d.feature_types[f.type])}</td>
          <td class="small">${esc(this.rangeText(f))}</td>
          <td class="num">${f.type === 'text' ? '-' : `<input type="checkbox" data-fu="${esc(f.id)}" ${f.use_in_balance ? 'checked' : ''} aria-label="편성 반영">`}</td>
          <td>${f.type === 'text' ? '<span class="muted small">사용 안 함</span>' : `<select data-fm="${esc(f.id)}">${d.allowed_methods[f.type].map((m) => `<option value="${m}" ${f.method === m ? 'selected' : ''}>${esc(d.methods[m])}</option>`).join('')}</select>${f.method === 'count' ? `<div class="small muted">${esc(this.countText(f))}</div>` : ''}`}</td>
          <td>${f.type === 'text' ? '-' : App.impSelect(f.importance, `data-fi="${esc(f.id)}"`)}</td>
          <td class="num"><input type="checkbox" data-fe="${esc(f.id)}" ${f.include_in_export ? 'checked' : ''} aria-label="결과 파일 포함"></td>
          <td class="small">${f.active ? status(f) : ''}</td>
          <td><div class="btn-group"><button class="btn btn-sm" data-fedit="${esc(f.id)}">편집</button><button class="btn btn-sm btn-danger" data-fdel="${esc(f.id)}">삭제</button></div></td></tr>`).join('')}
        </tbody></table></div></div>`).join('')}
      <div class="panel" id="comboPanel"><div class="row"><h2 class="grow">특성 조합 (여러 특성을 함께 고려)</h2><button class="btn" id="cAdd">＋ 조합 만들기</button></div>
        <p class="muted small">예: ‘기초학습 지원 필요=예’ <b>그리고</b> ‘또래 관계 지원 필요 정도=3’ 인 학생의 분포. 여러 특성을 합쳐 학생의 우열을 매기는 종합 점수를 만들지 않으며, 조건에 모두 해당하는 학생 수만 셉니다.
        조건 항목 중 하나라도 미입력인 학생은 ‘판단 불가’로 따로 셉니다. 편성에 반영하기 전에 아래 집계 기준과 학급별 현황을 확인하세요.</p>
        ${this.combosHtml()}</div>
      ${this.memoHtml()}`;
    this.bind(main);
  },

  rangeText(f) {
    if (f.type === 'single' || f.type === 'multi') return (f.options || []).join(', ');
    if (f.type === 'level') { const st = App.levelSteps(f); return st.length <= 7 ? st.map((x) => App.levelLabel(f, x)).join(' / ') : `${f.min} ~ ${f.max} (간격 ${f.step || 1}, 5개 구간으로 묶어 분포 계산)`; }
    if (f.type === 'yesno') return '예 / 아니요 / 미입력';
    return '자유 입력';
  },
  countText(f) {
    if (f.type === 'yesno') return '‘예’인 학생 수를 고르게';
    if (f.type === 'level') { const th = f.count_min ?? App.levelSteps(f).slice(-1)[0]; return `${App.levelLabel(f, th)} 이상인 학생 수를 고르게`; }
    const v = (f.count_values && f.count_values.length) ? f.count_values : (f.options || []).slice(0, 1);
    return `‘${v.join('·')}’ 학생 수를 고르게`;
  },

  comboMembers(cb) {
    const p = App.state.project; const feats = Object.fromEntries(p.features.map((f) => [f.id, f]));
    const mem = [], miss = [];
    App.eligible().forEach((s) => {
      let ok = true, ms = false;
      (cb.conds || []).forEach((c) => {
        const f = feats[c.feature_id]; if (!f) { ok = false; return; }
        const v = (s.traits || {})[f.id];
        if (App.isMissing(f, v)) { ms = true; ok = false; return; }
        const vals = c.values || [];
        let hit;
        if (f.type === 'yesno') hit = vals.some((x) => (x === true || x === '예') === v);
        else if (f.type === 'multi') hit = Array.isArray(v) && v.some((x) => vals.includes(x));
        else if (f.type === 'level') hit = vals.some((x) => Math.abs(Number(x) - Number(v)) < 1e-9);
        else hit = vals.includes(v);
        if (!hit) ok = false;
      });
      if (ok && (cb.conds || []).length) mem.push(s); else if (ms) miss.push(s);
    });
    return { mem, miss };
  },
  comboDesc(cb) {
    const p = App.state.project;
    return (cb.conds || []).map((c) => { const f = p.features.find((x) => x.id === c.feature_id); if (!f) return '(삭제된 항목)'; return `${f.name} = ${(c.values || []).map((v) => (f.type === 'yesno' ? (v === true || v === '예' ? '예' : '아니요') : f.type === 'level' ? App.levelLabel(f, v) : v)).join(' 또는 ')}`; }).join('  그리고  ');
  },
  comboStatsHtml(cb) {
    const { mem, miss } = this.comboMembers(cb); const plan = App.plan(); const p = App.state.project;
    let per = '';
    if (plan) per = `<div class="small">현재 편성안(${esc(plan.name)}) 학급별: ${p.classes.map((c) => `${esc(c.name)} ${mem.filter((s) => plan.assignment[s.key] === c.id).length}명`).join(' · ')}</div>`;
    return `<div class="small">해당 학생 <b>${mem.length}명</b> · 판단 불가(미입력) ${miss.length}명</div>${per}`;
  },
  combosHtml() {
    const p = App.state.project;
    if (!p.combos.length) return '<p class="muted">만든 조합이 없습니다.</p>';
    return `<table class="tbl compact"><thead><tr><th>이름</th><th>집계 기준</th><th>현황</th><th>편성 반영</th><th>중요도</th><th></th></tr></thead><tbody>
      ${p.combos.map((cb) => `<tr><td><b>${esc(cb.name)}</b></td><td class="small">${esc(this.comboDesc(cb))} 인 학생</td><td>${App.state.share ? '<span class="muted">(공유 보기에서 숨김)</span>' : this.comboStatsHtml(cb)}</td>
        <td class="num"><input type="checkbox" data-cu="${esc(cb.id)}" ${cb.use_in_balance ? 'checked' : ''} aria-label="편성 반영"></td><td>${App.impSelect(cb.importance, `data-ci="${esc(cb.id)}"`)}</td>
        <td><div class="btn-group"><button class="btn btn-sm" data-cedit="${esc(cb.id)}">편집</button><button class="btn btn-sm btn-danger" data-cdel="${esc(cb.id)}">삭제</button></div></td></tr>`).join('')}</tbody></table>`;
  },

  memoHtml() {
    if (App.state.share) return '<div class="panel"><h2>메모에서 태그 후보 제안 (AI 보조)</h2><p class="muted">화면 공유용 보기에서는 메모를 표시하지 않습니다.</p></div>';
    const withMemo = App.state.project.students.filter((s) => (s.memo || '').trim());
    return `<div class="panel" id="memoPanel"><h2>메모에서 태그 후보 제안 (AI 보조 · 선택 기능)</h2>
      <p class="muted small">자유 메모는 기본적으로 편성과 AI 분석에서 <b>제외</b>됩니다. 교사가 아래에서 고른 메모에 한해서만, 이미 있는 선택형 특성의 선택지 중에서 태그 후보를 제안받을 수 있습니다.
      제안은 교사가 확인하고 ‘저장’한 것만 반영됩니다. 메모를 근거로 질병·장애·성격·가정환경을 추정하거나 진단하지 않습니다. 메모 속 학생 이름·연락처·날짜는 가린 뒤 처리합니다.</p>
      ${withMemo.length ? `<div class="row"><label class="chk"><input type="checkbox" id="mAll"> 모두 선택</label><button class="btn" id="mRun">선택한 메모로 태그 후보 받기</button></div>
      <div class="tbl-wrap" style="max-height:260px"><table class="tbl compact"><tbody>${withMemo.map((s) => `<tr><td class="num"><input type="checkbox" class="mSel" value="${esc(s.key)}"></td><td>${esc(App.dnFull(s))}</td><td>${esc(s.memo)}</td></tr>`).join('')}</tbody></table></div>` : '<p class="muted">메모가 있는 학생이 없습니다.</p>'}
      <div id="mOut"></div></div>`;
  },

  bind(main) {
    const p = App.state.project; const F = (id) => p.features.find((f) => f.id === id);
    const re = () => this.render(main);
    main.querySelectorAll('[data-fa]').forEach((c) => { c.onchange = () => { F(c.dataset.fa).active = c.checked; App.changed(); re(); }; });
    main.querySelectorAll('[data-fu]').forEach((c) => { c.onchange = () => { F(c.dataset.fu).use_in_balance = c.checked; App.changed(); }; });
    main.querySelectorAll('[data-fm]').forEach((c) => { c.onchange = () => { F(c.dataset.fm).method = c.value; App.changed(); re(); }; });
    main.querySelectorAll('[data-fi]').forEach((c) => { c.onchange = () => { F(c.dataset.fi).importance = c.value; App.changed(); }; });
    main.querySelectorAll('[data-fe]').forEach((c) => { c.onchange = () => { F(c.dataset.fe).include_in_export = c.checked; App.changed(); }; });
    main.querySelectorAll('[data-fedit]').forEach((b) => { b.onclick = () => this.editor(F(b.dataset.fedit), re); });
    main.querySelectorAll('[data-fdel]').forEach((b) => { b.onclick = () => this.remove(F(b.dataset.fdel), re); });
    main.querySelector('#fAdd').onclick = () => this.editor(null, re);
    main.querySelector('#cAdd').onclick = () => this.comboEditor(null, re);
    main.querySelectorAll('[data-cu]').forEach((c) => { c.onchange = () => { p.combos.find((x) => x.id === c.dataset.cu).use_in_balance = c.checked; App.changed(); }; });
    main.querySelectorAll('[data-ci]').forEach((c) => { c.onchange = () => { p.combos.find((x) => x.id === c.dataset.ci).importance = c.value; App.changed(); }; });
    main.querySelectorAll('[data-cedit]').forEach((b) => { b.onclick = () => this.comboEditor(p.combos.find((x) => x.id === b.dataset.cedit), re); });
    main.querySelectorAll('[data-cdel]').forEach((b) => { b.onclick = async () => { if (!await App.confirm('조합 삭제', '이 특성 조합을 삭제합니다. 학생 자료는 바뀌지 않습니다.', '삭제', true)) return; p.combos = p.combos.filter((x) => x.id !== b.dataset.cdel); App.changed(); re(); }; });
    const mAll = main.querySelector('#mAll'); if (mAll) mAll.onchange = () => App.$$('.mSel', main).forEach((c) => { c.checked = mAll.checked; });
    const mRun = main.querySelector('#mRun'); if (mRun) mRun.onclick = () => this.memoTags(main, re);
  },

  editor(f, done) {
    const p = App.state.project; const d = App.state.defaults; const isNew = !f;
    const cur = f ? App.clone(f) : { id: App.uid('f_'), category: '기타', name: '', desc: '', type: 'single', options: ['선택지 1', '선택지 2'], min: 1, max: 3, step: 1, labels: {}, use_in_balance: true, method: 'distribution', importance: 'normal', count_values: [], count_min: null, include_in_export: false, active: true };
    const cats = [...new Set(p.features.map((x) => x.category || '기타').concat(['학습 관련', '생활 및 관계 관련', '교육적 지원 관련', '기타']))];
    const used = f ? p.students.filter((s) => !App.isMissing(f, (s.traits || {})[f.id])).length : 0;
    const m = App.modal({
      title: isNew ? '새 특성 항목' : `특성 항목 편집 — ${f.name}`, wide: true,
      body: `<div class="row"><label class="field grow"><span>항목명</span><input type="text" id="eName" value="${esc(cur.name)}"></label>
        <label class="field"><span>분류</span><input type="text" id="eCat" list="eCats" value="${esc(cur.category || '')}"><datalist id="eCats">${cats.map((c) => `<option>${esc(c)}</option>`).join('')}</datalist></label></div>
        <label class="field"><span>설명 (입력하는 교사에게 보이는 안내)</span><input type="text" id="eDesc" value="${esc(cur.desc || '')}"></label>
        <label class="field"><span>입력 형식</span><select id="eType">${Object.entries(d.feature_types).map(([k, v]) => `<option value="${k}" ${cur.type === k ? 'selected' : ''}>${esc(v)}</option>`).join('')}</select>
        ${used ? `<span class="small muted">이 항목에는 이미 ${used}명의 값이 입력되어 있습니다. 형식을 바꾸면 기존 값을 지워야 합니다(확인 후 진행).</span>` : ''}</label>
        <div id="eTypeBox"></div>
        <div class="row"><label class="chk"><input type="checkbox" id="eUse" ${cur.use_in_balance ? 'checked' : ''}> 편성에 반영</label>
        <label class="field"><span>균형 배치 방식</span><select id="eMethod"></select></label>
        <label class="field"><span>중요도</span>${App.impSelect(cur.importance, 'id="eImp"')}</label>
        <label class="chk"><input type="checkbox" id="eExp" ${cur.include_in_export ? 'checked' : ''}> 담당 교사용 결과 파일에 포함</label>
        <label class="chk"><input type="checkbox" id="eAct" ${cur.active ? 'checked' : ''}> 사용(입력 화면에 표시)</label></div>
        <div id="eCountBox"></div>`,
      buttons: [{ label: '취소' }, { label: '저장', cls: 'btn-pri', onClick: (el) => save(el) }],
    });
    const el = m.el;
    const optRows = () => (cur.options || []).map((o, i) => `<div class="row" style="margin:3px 0"><input type="text" class="eOpt" data-i="${i}" data-orig="${esc(o)}" value="${esc(o)}"><button class="btn btn-sm btn-danger" data-odel="${i}">삭제</button></div>`).join('');
    const typeBox = () => {
      const t = el.querySelector('#eType').value; const box = el.querySelector('#eTypeBox');
      if (t === 'single' || t === 'multi') {
        box.innerHTML = `<div class="field"><span>선택지 (이름을 고치면 이미 입력된 학생 값도 함께 바뀝니다)</span><div id="eOpts">${optRows()}</div><div class="row"><input type="text" id="eNewOpt" placeholder="새 선택지"><button class="btn btn-sm" id="eAddOpt">추가</button></div></div>`;
        box.querySelector('#eAddOpt').onclick = () => { const v = box.querySelector('#eNewOpt').value.trim(); if (!v) return; if (cur.options.includes(v)) return App.toast('같은 선택지가 있습니다.', 'err'); syncOpts(); cur.options.push(v); typeBox(); };
        App.$$('[data-odel]', box).forEach((b) => { b.onclick = () => { syncOpts(); cur.options.splice(Number(b.dataset.odel), 1); cur._removed = (cur._removed || []).concat([b.parentNode.querySelector('.eOpt').dataset.orig]); typeBox(); }; });
      } else if (t === 'level') {
        const st = App.levelSteps(cur);
        box.innerHTML = `<div class="row"><label class="field"><span>최솟값</span><input type="number" id="eMin" value="${esc(cur.min)}"></label><label class="field"><span>최댓값</span><input type="number" id="eMax" value="${esc(cur.max)}"></label><label class="field"><span>간격</span><input type="number" id="eStep" value="${esc(cur.step || 1)}" step="any"></label></div>
          ${st.length <= 11 ? `<div class="field"><span>단계 이름 (선택)</span>${st.map((x) => `<div class="row"><span style="width:40px">${App.fmtNum(x)}</span><input type="text" class="eLab" data-v="${App.fmtNum(x)}" value="${esc((cur.labels || {})[App.fmtNum(x)] || '')}" placeholder="예: 보통"></div>`).join('')}</div>` : '<p class="small muted">단계가 많아 분포는 5개 구간으로 묶어 계산합니다.</p>'}`;
        ['#eMin', '#eMax', '#eStep'].forEach((id) => { box.querySelector(id).onchange = () => { syncLevel(); typeBox(); methodBox(); }; });
      } else box.innerHTML = t === 'text' ? '<p class="muted small">자유 메모는 편성 계산에 사용하지 않습니다.</p>' : '';
      methodBox();
    };
    const syncOpts = () => { const ins = App.$$('.eOpt', el); if (ins.length) { cur._rename = cur._rename || {}; ins.forEach((i) => { const nv = i.value.trim(); if (nv && nv !== i.dataset.orig) cur._rename[i.dataset.orig] = nv; cur.options[Number(i.dataset.i)] = nv; }); } };
    const syncLevel = () => { const g = (id) => el.querySelector(id); if (!g('#eMin')) return; cur.min = Number(g('#eMin').value); cur.max = Number(g('#eMax').value); cur.step = Number(g('#eStep').value) || 1; cur.labels = cur.labels || {}; App.$$('.eLab', el).forEach((i) => { if (i.value.trim()) cur.labels[i.dataset.v] = i.value.trim(); else delete cur.labels[i.dataset.v]; }); };
    const methodBox = () => {
      const t = el.querySelector('#eType').value; const ms = el.querySelector('#eMethod');
      const allowed = d.allowed_methods[t]; if (!allowed.includes(cur.method)) cur.method = allowed[0];
      ms.innerHTML = allowed.map((x) => `<option value="${x}" ${cur.method === x ? 'selected' : ''}>${esc(d.methods[x])}</option>`).join('');
      ms.onchange = () => { cur.method = ms.value; countBox(); }; countBox();
    };
    const countBox = () => {
      const t = el.querySelector('#eType').value; const box = el.querySelector('#eCountBox');
      if (cur.method !== 'count' || t === 'yesno') { box.innerHTML = t === 'yesno' && cur.method === 'count' ? '<p class="small muted">‘예’인 학생 수를 학급마다 고르게 맞춥니다. (미입력은 ‘아니요’로 보지 않고 따로 셉니다)</p>' : ''; return; }
      if (t === 'level') { syncLevel(); const st = App.levelSteps(cur); box.innerHTML = `<label class="field"><span>기준: 이 값 이상인 학생 수를 고르게</span><select id="eCMin">${st.map((x) => `<option value="${x}" ${Number(cur.count_min ?? st[st.length - 1]) === x ? 'selected' : ''}>${esc(App.levelLabel(cur, x))}</option>`).join('')}</select></label>`; return; }
      syncOpts();
      box.innerHTML = `<div class="field"><span>이 값에 해당하는 학생 수를 고르게</span>${cur.options.map((o) => `<label class="chk"><input type="checkbox" class="eCV" value="${esc(o)}" ${(cur.count_values || []).includes(o) ? 'checked' : ''}> ${esc(o)}</label>`).join('')}</div>`;
    };
    el.querySelector('#eType').onchange = () => { cur.type = el.querySelector('#eType').value; if ((cur.type === 'single' || cur.type === 'multi') && !(cur.options || []).length) cur.options = ['선택지 1', '선택지 2']; typeBox(); };
    typeBox();
    const save = async (el2) => {
      const name = el2.querySelector('#eName').value.trim();
      if (!name) { App.toast('항목명을 입력하세요.', 'err'); return false; }
      if (p.features.some((x) => x.name === name && x.id !== cur.id)) { App.toast('같은 이름의 항목이 있습니다.', 'err'); return false; }
      const t = el2.querySelector('#eType').value;
      if (t === 'single' || t === 'multi') { syncOpts(); cur.options = cur.options.filter(Boolean); if (cur.options.length < 1) { App.toast('선택지를 1개 이상 입력하세요.', 'err'); return false; } if (new Set(cur.options).size !== cur.options.length) { App.toast('같은 선택지가 두 번 있습니다.', 'err'); return false; } }
      if (t === 'level') { syncLevel(); if (!(cur.max > cur.min)) { App.toast('최댓값은 최솟값보다 커야 합니다.', 'err'); return false; } }
      const studs = p.students.filter((s) => s.traits && s.traits[cur.id] !== undefined);
      if (!isNew && f.type !== t && studs.length) {
        if (!await App.confirm('입력 형식 변경', `<p>입력 형식을 바꾸면 이미 입력된 ${studs.length}명의 값이 새 형식과 맞지 않으므로 <b>모두 지워집니다(미입력)</b>. 계속할까요?</p>`, '값을 지우고 형식 변경', true)) return false;
        studs.forEach((s) => { delete s.traits[cur.id]; });
      }
      if (!isNew && t === f.type) {
        const rn = cur._rename || {}; const rm = (cur._removed || []).filter((o) => !cur.options.includes(o) && !rn[o]);
        if (t === 'level') {
          const st = App.levelSteps(cur); const bad = studs.filter((s) => !st.some((x) => Math.abs(x - Number(s.traits[cur.id])) < 1e-9));
          if (bad.length && !await App.confirm('범위 변경', `<p>새 범위·간격에 맞지 않는 값이 ${bad.length}명 있습니다. 이 값들은 <b>미입력</b>으로 바뀝니다.</p>`, '계속', true)) return false;
          bad.forEach((s) => { delete s.traits[cur.id]; });
        }
        const affected = rm.length ? studs.filter((s) => (Array.isArray(s.traits[cur.id]) ? s.traits[cur.id].some((v) => rm.includes(v)) : rm.includes(s.traits[cur.id]))) : [];
        if (affected.length && !await App.confirm('선택지 삭제', `<p>삭제한 선택지(${rm.map(esc).join(', ')})를 가진 학생 ${affected.length}명이 있습니다. 단일 선택은 <b>미입력</b>으로, 다중 선택은 해당 선택지만 빠집니다.</p>`, '계속', true)) return false;
        studs.forEach((s) => {
          let v = s.traits[cur.id];
          if (Array.isArray(v)) { v = v.map((x) => rn[x] || x).filter((x) => !rm.includes(x)); s.traits[cur.id] = cur.options.filter((o) => v.includes(o)); }
          else if (typeof v === 'string' && (t === 'single')) { if (rn[v]) s.traits[cur.id] = rn[v]; else if (rm.includes(v)) delete s.traits[cur.id]; }
        });
        if (cur.count_values) cur.count_values = cur.count_values.map((x) => rn[x] || x).filter((x) => cur.options.includes(x));
        p.combos.forEach((cb) => cb.conds.forEach((c) => { if (c.feature_id === cur.id) c.values = c.values.map((x) => rn[x] || x); }));
      }
      cur.name = name; cur.category = el2.querySelector('#eCat').value.trim() || '기타'; cur.desc = el2.querySelector('#eDesc').value.trim(); cur.type = t;
      cur.use_in_balance = t !== 'text' && el2.querySelector('#eUse').checked; cur.method = t === 'text' ? 'none' : el2.querySelector('#eMethod').value;
      cur.importance = el2.querySelector('#eImp').value; cur.include_in_export = el2.querySelector('#eExp').checked; cur.active = el2.querySelector('#eAct').checked;
      const cm = el2.querySelector('#eCMin'); if (cm) cur.count_min = Number(cm.value);
      const cvs = App.$$('.eCV', el2); if (cvs.length) cur.count_values = cvs.filter((c) => c.checked).map((c) => c.value);
      delete cur._rename; delete cur._removed;
      if (isNew) p.features.push(cur); else Object.assign(f, cur);
      App.log('교사', `특성 항목 ${isNew ? '추가' : '수정'}: ${cur.name}`); App.changed(); done(); return true;
    };
  },

  async remove(f, done) {
    const p = App.state.project;
    const n = p.students.filter((s) => s.traits && s.traits[f.id] !== undefined).length;
    const cb = p.combos.filter((c) => c.conds.some((x) => x.feature_id === f.id));
    if (!await App.confirm('특성 항목 삭제', `<p>‘${esc(f.name)}’ 항목을 삭제합니다.${n ? ` 입력된 학생 ${n}명의 값도 함께 삭제됩니다.` : ''}${cb.length ? ` 이 항목을 쓰는 특성 조합 ${cb.length}개도 삭제됩니다.` : ''}</p><p class="small">잠시 쓰지 않으려면 삭제 대신 ‘사용’을 끄세요 (값이 보존됨).</p>`, '삭제', true)) return;
    p.students.forEach((s) => { if (s.traits) delete s.traits[f.id]; });
    p.combos = p.combos.filter((c) => !cb.includes(c));
    p.features = p.features.filter((x) => x !== f);
    App.log('교사', `특성 항목 삭제: ${f.name}`); App.changed(); done();
  },

  comboEditor(cb, done) {
    const p = App.state.project; const isNew = !cb;
    const cur = cb ? App.clone(cb) : { id: App.uid('cb'), name: '', conds: [], use_in_balance: false, importance: 'normal' };
    const feats = App.activeFeatures();
    if (feats.length < 2) return App.toast('조합을 만들려면 사용 중인 특성 항목이 2개 이상 있어야 합니다.', 'err');
    if (!cur.conds.length) cur.conds = [{ feature_id: feats[0].id, values: [] }, { feature_id: feats[1].id, values: [] }];
    const valOpts = (f) => f.type === 'yesno' ? [[true, '예'], [false, '아니요']] : f.type === 'level' ? App.levelSteps(f).map((x) => [x, App.levelLabel(f, x)]) : (f.options || []).map((o) => [o, o]);
    const m = App.modal({
      title: isNew ? '특성 조합 만들기' : '특성 조합 편집', wide: true,
      body: `<label class="field"><span>조합 이름</span><input type="text" id="kName" value="${esc(cur.name)}" placeholder="예: 학습 지원 + 또래 관계 지원"></label><div id="kConds"></div><button class="btn btn-sm" id="kAdd">＋ 조건 추가</button>
        <h3>집계 기준과 현황 (반영 전 확인)</h3><div id="kStat" class="notice n-info"></div>
        <label class="chk"><input type="checkbox" id="kUse" ${cur.use_in_balance ? 'checked' : ''}> 확인했습니다 — 이 조합의 학생 수를 학급마다 고르게 맞추도록 편성에 반영</label> 중요도 ${App.impSelect(cur.importance, 'id="kImp"')}`,
      buttons: [{ label: '취소' }, {
        label: '저장', cls: 'btn-pri', onClick: (el) => {
          read(); cur.name = el.querySelector('#kName').value.trim() || this.comboDesc(cur).slice(0, 40);
          if (cur.conds.length < 2 || cur.conds.some((c) => !c.values.length)) { App.toast('조건을 2개 이상, 각 조건마다 값을 1개 이상 고르세요.', 'err'); return false; }
          cur.use_in_balance = el.querySelector('#kUse').checked; cur.importance = el.querySelector('#kImp').value;
          if (isNew) p.combos.push(cur); else Object.assign(cb, cur);
          App.log('교사', `특성 조합 ${isNew ? '추가' : '수정'}: ${cur.name}`); App.changed(); done(); return true;
        },
      }],
    });
    const el = m.el;
    const read = () => { cur.conds = App.$$('.kc', el).map((row) => { const f = p.features.find((x) => x.id === row.querySelector('.kf').value); return { feature_id: f.id, values: App.$$('.kv:checked', row).map((c) => (f.type === 'yesno' ? c.value === 'true' : f.type === 'level' ? Number(c.value) : c.value)) }; }); };
    const draw = () => {
      el.querySelector('#kConds').innerHTML = cur.conds.map((c, i) => { const f = p.features.find((x) => x.id === c.feature_id) || feats[0]; return `<div class="kc panel tight"><div class="row"><b>조건 ${i + 1}</b><select class="kf">${feats.map((x) => `<option value="${esc(x.id)}" ${x.id === f.id ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}</select>${i >= 2 ? `<button class="btn btn-sm btn-danger" data-kdel="${i}">삭제</button>` : ''}</div>
        <div>${valOpts(f).map(([v, l]) => `<label class="chk"><input type="checkbox" class="kv" value="${esc(String(v))}" ${c.values.some((x) => String(x) === String(v)) ? 'checked' : ''}> ${esc(l)}</label>`).join('')}</div></div>`; }).join('');
      App.$$('.kf', el).forEach((s, i) => { s.onchange = () => { read(); cur.conds[i] = { feature_id: s.value, values: [] }; draw(); }; });
      App.$$('.kv', el).forEach((c) => { c.onchange = () => { read(); stat(); }; });
      App.$$('[data-kdel]', el).forEach((b) => { b.onclick = () => { read(); cur.conds.splice(Number(b.dataset.kdel), 1); draw(); }; });
      stat();
    };
    const stat = () => { el.querySelector('#kStat').innerHTML = `<div><b>집계 기준:</b> ${esc(this.comboDesc(cur))} 인 학생 (모든 조건을 만족해야 함)</div>${App.state.share ? '' : this.comboStatsHtml(cur)}`; };
    el.querySelector('#kAdd').onclick = () => { read(); cur.conds.push({ feature_id: feats[0].id, values: [] }); draw(); };
    draw();
  },

  memoTags(main, done) {
    const keys = App.$$('.mSel:checked', main).map((c) => c.value);
    if (!keys.length) return App.toast('메모를 분석할 학생을 고르세요.', 'err');
    App.ai.run('memo_tags', { keys }, (res) => {
      const out = main.querySelector('#mOut');
      if (!res.ok) { out.innerHTML = App.ai.errorsHtml(res); return; }
      if (!res.suggestions.length) { out.innerHTML = '<div class="notice n-info">제안할 태그 후보가 없습니다.</div>'; return; }
      const p = App.state.project;
      out.innerHTML = `<h3>태그 후보 (확인한 항목만 저장됩니다)</h3><table class="tbl compact"><thead><tr><th>저장</th><th>학생</th><th>항목</th><th>현재 값</th><th>제안 값</th><th>근거</th></tr></thead><tbody>
        ${res.suggestions.map((s, i) => { const f = p.features.find((x) => x.id === s.feature_id); return `<tr><td class="num"><input type="checkbox" class="tgSel" value="${i}"></td><td>${esc(App.dnKey(s.key))}</td><td>${esc(s.feature)}</td><td>${esc(App.traitText(f, s.current))}</td><td><b>${esc(App.traitText(f, s.proposed))}</b></td><td class="small">${esc(s.basis)}</td></tr>`; }).join('')}</tbody></table>
        <button class="btn btn-pri" id="tgSave" style="margin-top:8px">선택한 태그 저장</button>`;
      out.querySelector('#tgSave').onclick = () => {
        const sel = App.$$('.tgSel:checked', out).map((c) => res.suggestions[Number(c.value)]);
        if (!sel.length) return App.toast('저장할 후보를 고르세요.', 'err');
        const before = sel.map((s) => ({ key: s.key, fid: s.feature_id, v: (App.stuByKey(s.key).traits || {})[s.feature_id] }));
        sel.forEach((s) => { const st = App.stuByKey(s.key); st.traits = st.traits || {}; st.traits[s.feature_id] = s.proposed; });
        App.log('AI 제안(교사 확인)', `메모 태그 후보 ${sel.length}건 저장`, { type: 'traits', before });
        App.changed(); App.toast(`${sel.length}건을 저장했습니다.`, 'ok'); done();
      };
    });
  },
};
