/* ② 학생 명단 · ③ 특성 입력 */
'use strict';
App.tabs.students = {
  view: 'basic', q: '', fCls: '', fGender: '', fElig: '', fMissing: false, sort: null, sel: new Set(),

  filtered() {
    const p = App.state.project; const feats = App.activeFeatures();
    let list = p.students.slice();
    const q = this.q.trim().toLowerCase();
    if (q) list = list.filter((s) => (s.name || '').toLowerCase().includes(q) || (s.sid || '').toLowerCase().includes(q) || (!App.state.share && (s.memo || '').toLowerCase().includes(q)));
    if (this.fCls) list = list.filter((s) => (this.fCls === '__none' ? !s.cls : s.cls === this.fCls));
    if (this.fGender) list = list.filter((s) => (this.fGender === '__none' ? !s.gender : s.gender === this.fGender));
    if (this.fElig === 'yes') list = list.filter((s) => s.eligible !== false);
    if (this.fElig === 'no') list = list.filter((s) => s.eligible === false);
    if (this.fElig === 'in') list = list.filter((s) => s.transfer_in);
    if (this.fMissing) list = list.filter((s) => feats.some((f) => App.isMissing(f, (s.traits || {})[f.id])));
    if (this.sort) {
      const { key, dir } = this.sort;
      const val = (s) => { const v = key === 'num' || key === 'grade' ? (s[key] ?? 9999) : (s[key] || ''); return v; };
      list.sort((a, b) => { const x = val(a), y = val(b); return (typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y), 'ko', { numeric: true })) * dir; });
    }
    return list;
  },

  render(main) {
    const p = App.state.project; const share = App.state.share;
    const list = this.filtered();
    const clsList = [...new Set(p.students.map((s) => s.cls).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'ko', { numeric: true }));
    const feats = App.activeFeatures(true);
    const el = p.students.filter((s) => s.eligible !== false).length;
    const dupNames = {}; p.students.forEach((s) => { const n = (s.name || '').trim(); if (n) dupNames[n] = (dupNames[n] || 0) + 1; });
    main.innerHTML = `
      <div class="panel">
        <div class="row"><h2 class="grow">학생 명단 (${p.students.length}명 · 편성 대상 ${el}명)</h2>
          <button class="btn btn-pri" id="sAdd">＋ 학생 추가 (전입 예정 포함)</button>
          <button class="btn" id="sImport">📥 엑셀에서 불러오기</button>
          <button class="btn" id="sTpl">📄 엑셀 입력 양식 받기</button></div>
        <p class="muted small">학생은 <b>학생 ID</b>로 구분합니다(이름이 같아도 다른 학생으로 처리). 필수 입력은 학생 ID와 이름뿐이며 나머지는 비워 둘 수 있습니다. 빈칸은 ‘미입력’으로 저장되고 ‘0’이나 ‘해당 없음’으로 바뀌지 않습니다.</p>
        <div class="row">
          <input type="search" id="sQ" placeholder="이름·학생 ID${share ? '' : '·메모'} 검색" value="${esc(this.q)}" style="min-width:240px">
          <select id="sCls"><option value="">현재 반: 전체</option>${clsList.map((c) => `<option ${this.fCls === c ? 'selected' : ''}>${esc(c)}</option>`).join('')}<option value="__none" ${this.fCls === '__none' ? 'selected' : ''}>현재 반 없음(전입 등)</option></select>
          <select id="sGen"><option value="">성별: 전체</option><option ${this.fGender === '남' ? 'selected' : ''}>남</option><option ${this.fGender === '여' ? 'selected' : ''}>여</option><option value="__none" ${this.fGender === '__none' ? 'selected' : ''}>미입력</option></select>
          <select id="sElig"><option value="">편성 대상: 전체</option><option value="yes" ${this.fElig === 'yes' ? 'selected' : ''}>편성 대상만</option><option value="no" ${this.fElig === 'no' ? 'selected' : ''}>편성 제외만</option><option value="in" ${this.fElig === 'in' ? 'selected' : ''}>전입 예정만</option></select>
          <label class="chk"><input type="checkbox" id="sMiss" ${this.fMissing ? 'checked' : ''}> 미입력 특성이 있는 학생만</label>
          <span class="grow"></span>
          <div class="btn-group" role="group" aria-label="보기 선택"><button class="btn ${this.view === 'basic' ? 'btn-pri' : ''}" data-view="basic">기본 정보</button><button class="btn ${this.view === 'traits' ? 'btn-pri' : ''}" data-view="traits">③ 특성 입력</button></div>
        </div>
        <div class="row" style="margin-top:8px">
          <span>표시 ${list.length}명 · 선택 <b id="selCount">${this.sel.size}</b>명</span>
          <button class="btn btn-sm" id="sBulk" ${this.sel.size ? '' : 'disabled'}>선택 학생 일괄 수정</button>
          <button class="btn btn-sm btn-danger" id="sDel" ${this.sel.size ? '' : 'disabled'}>선택 학생 삭제</button>
          <button class="btn btn-sm" id="sSelNone" ${this.sel.size ? '' : 'disabled'}>선택 해제</button>
        </div>
      </div>
      ${this.view === 'traits' && share ? '<div class="notice n-warn">화면 공유용 보기에서는 학생 특성을 표시하지 않습니다. 특성을 입력하려면 화면 공유용 보기를 끄세요.</div>' : ''}
      ${this.view === 'traits' && !feats.length ? '<div class="notice n-info">활성화된 특성 항목이 없습니다. ‘특성 항목 관리’에서 필요한 항목을 켜세요. <button class="btn btn-sm" data-goto=\'{"tab":"features"}\'>특성 항목 관리로 이동 ▸</button></div>' : ''}
      <div class="tbl-wrap"><table class="tbl compact" id="sTable"><thead>${this.headHtml(feats)}</thead><tbody>
      ${list.map((s) => this.rowHtml(s, feats, dupNames)).join('') || `<tr><td colspan="20" class="muted">학생이 없습니다. ‘학생 추가’ 또는 ‘엑셀에서 불러오기’를 사용하세요.</td></tr>`}
      </tbody></table></div>
      <p class="small muted">· 칸을 고친 뒤 다른 곳을 누르면 바로 저장됩니다. ‘상세’를 누르면 학생 한 명의 정보를 한 화면에서 편집할 수 있습니다. ⚠ 표시는 동명이인입니다(학생 ID로 구분).</p>`;
    this.bind(main, list);
  },

  headHtml(feats) {
    const sh = (k, t) => `<th data-sort="${k}" style="cursor:pointer" title="눌러서 정렬">${t}${this.sort && this.sort.key === k ? (this.sort.dir > 0 ? ' ▲' : ' ▼') : ''}</th>`;
    const chk = '<th class="num"><input type="checkbox" id="sAll" aria-label="표시된 학생 모두 선택"></th>';
    if (this.view === 'traits' && !App.state.share) {
      return `<tr>${chk}${sh('name', '이름')}${sh('sid', '학생 ID')}${sh('cls', '현재 반')}${feats.map((f) => `<th title="${esc(f.desc || '')}">${esc(f.name)}${f.use_in_balance && f.method !== 'none' ? '' : ' <span class="small muted">(참고용)</span>'}</th>`).join('')}<th></th></tr>`;
    }
    return `<tr>${chk}${sh('sid', '학생 ID <span class="req">*</span>')}${sh('name', '이름 <span class="req">*</span>')}${sh('grade', '현재 학년')}${sh('cls', '현재 반')}${sh('num', '현재 번호')}<th>성별</th><th>편성 대상</th><th>전입 예정</th><th>지정 학급</th>${App.state.share ? '' : '<th>교사용 메모</th>'}<th></th></tr>`;
  },

  rowHtml(s, feats, dup) {
    const p = App.state.project; const share = App.state.share;
    const ck = `<td class="num"><input type="checkbox" data-sel="${esc(s.key)}" ${this.sel.has(s.key) ? 'checked' : ''} aria-label="선택"></td>`;
    const dn = App.dn(s);
    const dupMark = !share && dup[(s.name || '').trim()] > 1 ? ' <span title="동명이인 — 학생 ID로 구분" class="badge b-warn">⚠ 동명</span>' : '';
    const det = `<td><button class="btn btn-sm" data-detail="${esc(s.key)}">상세</button></td>`;
    if (this.view === 'traits' && !share) {
      return `<tr data-row="${esc(s.key)}" ${s.eligible === false ? 'style="opacity:.6"' : ''}>${ck}<td>${esc(dn)}${dupMark}${s.eligible === false ? ' <span class="badge b-gray">편성 제외</span>' : ''}</td><td class="mono">${esc(s.sid)}</td><td>${esc(s.cls || (s.transfer_in ? '전입 예정' : ''))}</td>
        ${feats.map((f) => `<td>${this.traitEditor(s, f)}</td>`).join('')}${det}</tr>`;
    }
    const clsOpts = `<option value="">없음</option>${p.classes.map((c) => `<option value="${esc(c.id)}" ${s.fixed_class === c.id ? 'selected' : ''}>${esc(c.name)}</option>`).join('')}`;
    if (share) {
      return `<tr data-row="${esc(s.key)}">${ck}<td>-</td><td>${esc(dn)}</td><td>${esc(s.grade ?? '')}</td><td>${esc(s.cls || '')}</td><td>${esc(s.num ?? '')}</td><td>${esc(s.gender || '미입력')}</td><td>${s.eligible === false ? '✖ 제외' : '✔ 대상'}</td><td>${s.transfer_in ? '예' : ''}</td><td>${esc(s.fixed_class ? App.className(s.fixed_class) : '')}</td>${det}</tr>`;
    }
    return `<tr data-row="${esc(s.key)}" ${s.eligible === false ? 'style="background:#f4f4f4"' : ''}>${ck}
      <td><input type="text" data-f="sid" data-k="${esc(s.key)}" value="${esc(s.sid)}" class="${s.sid ? '' : 'cell-err'}" style="width:90px"></td>
      <td><input type="text" data-f="name" data-k="${esc(s.key)}" value="${esc(s.name)}" class="${s.name ? '' : 'cell-err'}" style="width:100px">${dupMark}</td>
      <td><input type="number" data-f="grade" data-k="${esc(s.key)}" value="${esc(s.grade ?? '')}" style="width:60px"></td>
      <td><input type="text" data-f="cls" data-k="${esc(s.key)}" value="${esc(s.cls || '')}" style="width:70px" placeholder="${s.transfer_in ? '전입' : ''}"></td>
      <td><input type="number" data-f="num" data-k="${esc(s.key)}" value="${esc(s.num ?? '')}" style="width:60px"></td>
      <td><select data-f="gender" data-k="${esc(s.key)}"><option value="">미입력</option><option ${s.gender === '남' ? 'selected' : ''}>남</option><option ${s.gender === '여' ? 'selected' : ''}>여</option></select></td>
      <td><select data-f="eligible" data-k="${esc(s.key)}"><option value="1">✔ 대상</option><option value="0" ${s.eligible === false ? 'selected' : ''}>✖ 제외</option></select></td>
      <td class="num"><input type="checkbox" data-f="transfer_in" data-k="${esc(s.key)}" ${s.transfer_in ? 'checked' : ''} aria-label="전입 예정"></td>
      <td><select data-f="fixed_class" data-k="${esc(s.key)}">${clsOpts}</select></td>
      <td><input type="text" data-f="memo" data-k="${esc(s.key)}" value="${esc(s.memo || '')}" style="min-width:180px"></td>${det}</tr>`;
  },

  traitEditor(s, f) {
    const v = (s.traits || {})[f.id];
    const a = `data-t="${esc(f.id)}" data-k="${esc(s.key)}"`;
    if (f.type === 'single') return `<select ${a}><option value="__m">— 미입력</option>${f.options.map((o) => `<option ${v === o ? 'selected' : ''}>${esc(o)}</option>`).join('')}</select>`;
    if (f.type === 'yesno') return `<select ${a}><option value="__m">— 미입력</option><option value="1" ${v === true ? 'selected' : ''}>예</option><option value="0" ${v === false ? 'selected' : ''}>아니요</option></select>`;
    if (f.type === 'level') {
      const st = App.levelSteps(f);
      if (st.length <= 11) return `<select ${a}><option value="__m">— 미입력</option>${st.map((x) => `<option value="${x}" ${v !== undefined && v !== null && Number(v) === x ? 'selected' : ''}>${esc(App.levelLabel(f, x))}</option>`).join('')}</select>`;
      return `<input type="number" ${a} value="${esc(v ?? '')}" min="${f.min}" max="${f.max}" step="${f.step || 1}" placeholder="미입력" style="width:80px">`;
    }
    if (f.type === 'multi') return `<button class="btn btn-sm" data-multi="${esc(f.id)}" data-k="${esc(s.key)}" style="min-width:110px;text-align:left">${esc(App.traitText(f, v))}</button>`;
    return `<input type="text" ${a} value="${esc(v ?? '')}" placeholder="(메모)">`;
  },

  setTrait(s, f, raw) {
    s.traits = s.traits || {};
    if (raw === '__m' || raw === '' || raw === null || raw === undefined) { delete s.traits[f.id]; return true; }
    if (f.type === 'yesno') s.traits[f.id] = raw === '1' || raw === true;
    else if (f.type === 'level') {
      const x = Number(raw); const st = App.levelSteps(f);
      if (Number.isNaN(x) || !st.some((y) => Math.abs(y - x) < 1e-6)) { App.toast(`‘${f.name}’ 값 ${raw}은(는) 입력 범위·단계가 아닙니다 (${f.min}~${f.max}, 간격 ${f.step || 1}).`, 'err'); return false; }
      s.traits[f.id] = x;
    } else s.traits[f.id] = raw;
    return true;
  },

  setField(s, field, el) {
    const p = App.state.project;
    if (field === 'sid') {
      const v = el.value.trim();
      if (!v) { App.toast('학생 ID는 비울 수 없습니다.', 'err'); el.value = s.sid; return; }
      if (p.students.some((x) => x !== s && x.sid === v)) { App.toast(`학생 ID ‘${v}’는 이미 다른 학생이 쓰고 있습니다.`, 'err'); el.value = s.sid; return; }
      s.sid = v;
    } else if (field === 'name') {
      const v = el.value.trim(); if (!v) { App.toast('이름은 비울 수 없습니다.', 'err'); el.value = s.name; return; } s.name = v;
    } else if (field === 'grade' || field === 'num') s[field] = el.value === '' ? null : Number(el.value);
    else if (field === 'eligible') s.eligible = el.value === '1';
    else if (field === 'transfer_in') s.transfer_in = el.checked;
    else if (field === 'fixed_class') s.fixed_class = el.value || null;
    else s[field] = el.value.trim();
    App.changed();
  },

  bind(main, list) {
    const p = App.state.project;
    const rerender = () => this.render(main);
    main.querySelector('#sQ').oninput = (e) => { this.q = e.target.value; clearTimeout(this._qt); this._qt = setTimeout(() => { rerender(); const i = main.querySelector('#sQ'); i.focus(); i.setSelectionRange(i.value.length, i.value.length); }, 250); };
    main.querySelector('#sCls').onchange = (e) => { this.fCls = e.target.value; rerender(); };
    main.querySelector('#sGen').onchange = (e) => { this.fGender = e.target.value; rerender(); };
    main.querySelector('#sElig').onchange = (e) => { this.fElig = e.target.value; rerender(); };
    main.querySelector('#sMiss').onchange = (e) => { this.fMissing = e.target.checked; rerender(); };
    main.querySelectorAll('[data-view]').forEach((b) => { b.onclick = () => { this.view = b.dataset.view; rerender(); }; });
    main.querySelectorAll('[data-sort]').forEach((th) => { th.onclick = () => { const k = th.dataset.sort; this.sort = this.sort && this.sort.key === k ? (this.sort.dir > 0 ? { key: k, dir: -1 } : null) : { key: k, dir: 1 }; rerender(); }; });
    const all = main.querySelector('#sAll');
    if (all) all.onchange = () => { list.forEach((s) => (all.checked ? this.sel.add(s.key) : this.sel.delete(s.key))); rerender(); };
    main.querySelectorAll('[data-sel]').forEach((c) => { c.onchange = () => { if (c.checked) this.sel.add(c.dataset.sel); else this.sel.delete(c.dataset.sel); rerender(); }; });
    main.querySelectorAll('[data-f]').forEach((el) => { el.onchange = () => this.setField(App.stuByKey(el.dataset.k), el.dataset.f, el); });
    main.querySelectorAll('[data-t]').forEach((el) => {
      el.onchange = () => { const s = App.stuByKey(el.dataset.k); const f = p.features.find((x) => x.id === el.dataset.t); if (this.setTrait(s, f, el.value)) App.changed(); else el.value = (s.traits || {})[f.id] ?? ''; };
    });
    main.querySelectorAll('[data-multi]').forEach((b) => { b.onclick = () => this.multiEditor(App.stuByKey(b.dataset.k), p.features.find((x) => x.id === b.dataset.multi), rerender); });
    main.querySelectorAll('[data-detail]').forEach((b) => { b.onclick = () => this.openDetail(b.dataset.detail); });
    main.querySelector('#sAdd').onclick = () => this.addStudent();
    main.querySelector('#sImport').onclick = () => this.importWizard();
    main.querySelector('#sTpl').onclick = async () => { try { const n = await App.download('template', { project: p }, '학급편성_입력양식.xlsx'); App.toast(`입력 양식(${n})을 내려받았습니다. 현재 켜져 있는 특성 항목이 열로 포함됩니다.`, 'ok'); } catch (e) { App.toast(e.message, 'err'); } };
    main.querySelector('#sBulk').onclick = () => this.bulkEdit(rerender);
    main.querySelector('#sDel').onclick = () => this.deleteStudents([...this.sel], rerender);
    main.querySelector('#sSelNone').onclick = () => { this.sel.clear(); rerender(); };
  },

  multiEditor(s, f, done) {
    const v = (s.traits || {})[f.id];
    App.modal({
      title: `${App.dn(s)} — ${f.name}`,
      body: `<p class="muted">여러 개를 고를 수 있습니다. 한 학생이 여러 선택지에 해당하면 각 선택지에 모두 집계됩니다.</p>
        ${f.options.map((o) => `<label class="chk" style="display:flex;margin:6px 0"><input type="checkbox" value="${esc(o)}" ${Array.isArray(v) && v.includes(o) ? 'checked' : ''}> ${esc(o)}</label>`).join('')}
        <p class="small">현재 값: <b>${esc(App.traitText(f, v))}</b></p>`,
      buttons: [
        { label: '미입력으로 되돌리기', onClick: () => { delete s.traits[f.id]; App.changed(); done(); } },
        { label: '‘해당 없음’으로 저장', onClick: () => { s.traits[f.id] = []; App.changed(); done(); } },
        { label: '선택한 값 저장', cls: 'btn-pri', onClick: (el) => { const vals = App.$$('input[type=checkbox]:checked', el).map((c) => c.value); s.traits = s.traits || {}; s.traits[f.id] = f.options.filter((o) => vals.includes(o)); App.changed(); done(); } },
      ],
    });
  },

  nextSid() {
    const p = App.state.project; let n = p.students.length + 1;
    const used = new Set(p.students.map((s) => s.sid));
    let sid; do { sid = 'S' + String(n).padStart(4, '0'); n++; } while (used.has(sid));
    return sid;
  },

  addStudent() {
    const p = App.state.project;
    const s = { key: App.uid('k'), sid: this.nextSid(), name: '', grade: p.settings.current_grade, cls: '', num: null, gender: '', eligible: true, transfer_in: false, memo: '', fixed_class: null, traits: {} };
    this.openDetail(null, s);
  },

  openDetail(key, newStudent) {
    const p = App.state.project;
    const orig = newStudent || App.stuByKey(key); if (!orig) return;
    const s = App.clone(orig);
    const feats = App.activeFeatures(true);
    const cats = [...new Set(feats.map((f) => f.category || '기타'))];
    const share = App.state.share;
    const rels = p.relations.filter((r) => r.members.includes(s.key));
    const traitRow = (f) => `<tr><td>${esc(f.name)}<div class="small muted">${esc(f.desc || '')}</div></td><td>${this.traitEditor(s, f).replace(/data-t=/g, 'data-dt=').replace(/data-multi=/g, 'data-dmulti=')}</td></tr>`;
    const body = `
      <div class="row">
        <label class="field"><span>학생 ID <span class="req">*</span></span><input type="text" id="dSid" value="${esc(s.sid)}"></label>
        <label class="field grow"><span>이름 <span class="req">*</span></span><input type="text" id="dName" value="${esc(share ? App.dn(orig) : s.name)}" ${share ? 'disabled' : ''}></label>
        <label class="field"><span>성별</span><select id="dGen"><option value="">미입력</option><option ${s.gender === '남' ? 'selected' : ''}>남</option><option ${s.gender === '여' ? 'selected' : ''}>여</option></select></label>
      </div>
      <div class="row">
        <label class="field"><span>현재 학년</span><input type="number" id="dGrade" value="${esc(s.grade ?? '')}" style="width:90px"></label>
        <label class="field"><span>현재 반</span><input type="text" id="dCls" value="${esc(s.cls || '')}" style="width:110px" placeholder="예: 2반"></label>
        <label class="field"><span>현재 번호</span><input type="number" id="dNum" value="${esc(s.num ?? '')}" style="width:90px"></label>
        <label class="field"><span>편성 대상</span><select id="dElig"><option value="1">✔ 편성 대상</option><option value="0" ${s.eligible === false ? 'selected' : ''}>✖ 편성 제외 (전출 예정 등)</option></select></label>
        <label class="chk" style="margin-top:22px"><input type="checkbox" id="dTin" ${s.transfer_in ? 'checked' : ''}> 전입 예정</label>
      </div>
      <label class="field"><span>지정 학급 (필수 조건: 이 학생을 반드시 이 학급에 배정)</span><select id="dFix"><option value="">지정하지 않음</option>${p.classes.map((c) => `<option value="${esc(c.id)}" ${s.fixed_class === c.id ? 'selected' : ''}>${esc(c.name)}</option>`).join('')}</select></label>
      ${share ? '<div class="notice n-warn">화면 공유용 보기에서는 메모와 특성을 표시하지 않습니다.</div>' : `
      <label class="field"><span>교사용 메모 (편성 계산에 자동 반영되지 않음)</span><textarea id="dMemo">${esc(s.memo || '')}</textarea></label>
      ${cats.map((c) => `<h3>${esc(c)}</h3><table class="tbl compact"><tbody>${feats.filter((f) => (f.category || '기타') === c).map(traitRow).join('')}</tbody></table>`).join('')}
      ${feats.length ? '' : '<p class="muted">활성화된 특성 항목이 없습니다.</p>'}`}
      <h3>이 학생이 포함된 관계 조건 (${rels.length}개)</h3>
      ${rels.length ? `<ul>${rels.map((r) => `<li>${App.strengthBadge(r)} ${esc(App.relKindText(r))}: ${r.members.map((k) => esc(App.dnKey(k))).join(', ')} <button class="btn btn-sm" data-goto='${esc(JSON.stringify({ tab: 'relations', relation: r.id }))}'>보기 ▸</button></li>`).join('')}</ul>` : '<p class="muted">없음</p>'}`;
    App.modal({
      title: newStudent ? '학생 추가' : `학생 상세 정보 — ${App.dnFull(orig)}`, wide: true, body,
      buttons: [
        ...(newStudent ? [] : [{ label: '이 학생 삭제', cls: 'btn-danger', onClick: () => { this.deleteStudents([orig.key], () => App.render()); } }]),
        { label: '취소' },
        {
          label: '저장', cls: 'btn-pri', onClick: (el) => {
            const v = (id) => el.querySelector(id);
            const sid = v('#dSid').value.trim(); const name = share ? orig.name : v('#dName').value.trim();
            if (!sid || !name) { App.toast('학생 ID와 이름은 반드시 입력해야 합니다.', 'err'); return false; }
            if (p.students.some((x) => x.key !== s.key && x.sid === sid)) { App.toast(`학생 ID ‘${sid}’는 이미 다른 학생이 쓰고 있습니다.`, 'err'); return false; }
            s.sid = sid; s.name = name; s.gender = v('#dGen').value; s.grade = v('#dGrade').value === '' ? null : Number(v('#dGrade').value);
            s.cls = v('#dCls').value.trim(); s.num = v('#dNum').value === '' ? null : Number(v('#dNum').value);
            s.eligible = v('#dElig').value === '1'; s.transfer_in = v('#dTin').checked; s.fixed_class = v('#dFix').value || null;
            if (!share) {
              s.memo = v('#dMemo').value.trim();
              for (const sel of App.$$('[data-dt]', el)) { const f = p.features.find((x) => x.id === sel.dataset.dt); if (!this.setTrait(s, f, sel.value)) return false; }
            }
            if (newStudent) { p.students.push(s); App.resetStuMap(); App.log('교사', `학생 추가: ${s.sid}`); } else Object.assign(orig, s);
            App.changed(); App.render(); App.toast('저장했습니다.', 'ok');
            return true;
          },
        },
      ],
      onOpen: (el) => {
        App.$$('[data-dmulti]', el).forEach((b) => {
          b.onclick = () => { const f = p.features.find((x) => x.id === b.dataset.dmulti); this.multiEditor(s, f, () => { b.textContent = App.traitText(f, s.traits[f.id]); }); };
        });
      },
    });
  },

  bulkEdit(done) {
    const p = App.state.project; const feats = App.activeFeatures(true).filter((f) => f.type !== 'text');
    const fields = [['grade', '현재 학년'], ['cls', '현재 반'], ['gender', '성별'], ['eligible', '편성 대상'], ['transfer_in', '전입 예정'], ['fixed_class', '지정 학급'],
      ...(App.state.share ? [] : feats.map((f) => ['t:' + f.id, '특성: ' + f.name]))];
    const m = App.modal({
      title: `선택한 ${this.sel.size}명 일괄 수정`,
      body: `<label class="field"><span>바꿀 항목</span><select id="bF">${fields.map(([k, l]) => `<option value="${k}">${esc(l)}</option>`).join('')}</select></label><div id="bV"></div>`,
      buttons: [{ label: '취소' }, {
        label: '적용', cls: 'btn-pri', onClick: async (el) => {
          const fk = el.querySelector('#bF').value; const inp = el.querySelector('#bVal');
          const studs = [...this.sel].map((k) => App.stuByKey(k)).filter(Boolean);
          if (fk.startsWith('t:')) {
            const f = p.features.find((x) => x.id === fk.slice(2));
            if (f.type === 'multi') {
              const mode = el.querySelector('input[name=bmm]:checked').value;
              const vals = App.$$('.bmv:checked', el).map((c) => c.value);
              studs.forEach((s) => { s.traits = s.traits || {}; if (mode === 'missing') delete s.traits[f.id]; else if (mode === 'na') s.traits[f.id] = []; else s.traits[f.id] = f.options.filter((o) => vals.includes(o)); });
            } else { for (const s of studs) { if (!this.setTrait(s, f, inp.value)) return false; } }
          } else {
            studs.forEach((s) => {
              if (fk === 'grade') s.grade = inp.value === '' ? null : Number(inp.value);
              else if (fk === 'eligible') s.eligible = inp.value === '1';
              else if (fk === 'transfer_in') s.transfer_in = inp.value === '1';
              else if (fk === 'fixed_class') s.fixed_class = inp.value || null;
              else s[fk] = inp.value.trim();
            });
          }
          App.log('교사', `학생 ${studs.length}명 일괄 수정 (${fields.find((x) => x[0] === fk)[1]})`);
          App.changed(); done(); App.toast(`${studs.length}명을 수정했습니다.`, 'ok');
        },
      }],
    });
    const upd = () => {
      const fk = m.el.querySelector('#bF').value; const box = m.el.querySelector('#bV'); let h = '';
      if (fk === 'gender') h = '<select id="bVal"><option value="">미입력</option><option>남</option><option>여</option></select>';
      else if (fk === 'eligible') h = '<select id="bVal"><option value="1">✔ 편성 대상</option><option value="0">✖ 편성 제외</option></select>';
      else if (fk === 'transfer_in') h = '<select id="bVal"><option value="1">예</option><option value="0">아니요</option></select>';
      else if (fk === 'fixed_class') h = `<select id="bVal"><option value="">지정하지 않음</option>${p.classes.map((c) => `<option value="${esc(c.id)}">${esc(c.name)}</option>`).join('')}</select>`;
      else if (fk === 'grade') h = '<input type="number" id="bVal">';
      else if (fk === 'cls') h = '<input type="text" id="bVal" placeholder="예: 2반 (비우면 현재 반 없음)">';
      else {
        const f = p.features.find((x) => x.id === fk.slice(2));
        if (f.type === 'multi') h = `<label class="chk"><input type="radio" name="bmm" value="set" checked> 아래 선택지로 설정</label><label class="chk"><input type="radio" name="bmm" value="na"> 해당 없음</label><label class="chk"><input type="radio" name="bmm" value="missing"> 미입력</label><div>${f.options.map((o) => `<label class="chk"><input type="checkbox" class="bmv" value="${esc(o)}"> ${esc(o)}</label>`).join('')}</div>`;
        else h = this.traitEditor({ key: '_', traits: {} }, f).replace(/data-t="[^"]*"/, 'id="bVal"');
      }
      box.innerHTML = `<div class="field"><span>새 값</span>${h}</div>`;
    };
    m.el.querySelector('#bF').onchange = upd; upd();
  },

  async deleteStudents(keys, done) {
    const p = App.state.project; if (!keys.length) return;
    const rels = p.relations.filter((r) => r.members.some((k) => keys.includes(k)));
    const html = `<p>선택한 학생 ${keys.length}명을 명단에서 삭제합니다.</p>
      <p class="small">전출 예정 등으로 편성에서만 빼려면 삭제 대신 ‘편성 대상’을 ‘제외’로 바꾸세요 (명단은 유지됨).</p>
      ${rels.length ? `<div class="notice n-warn">이 학생이 포함된 관계 조건 ${rels.length}개에서 해당 학생이 빠집니다. 학생이 2명 미만으로 남는 조건은 삭제됩니다.</div>` : ''}`;
    if (!await App.confirm('학생 삭제', html, '삭제', true)) return;
    const ks = new Set(keys);
    p.students = p.students.filter((s) => !ks.has(s.key));
    p.relations.forEach((r) => { r.members = r.members.filter((k) => !ks.has(k)); r.pairs = (r.pairs || []).filter(([a, b]) => !ks.has(a) && !ks.has(b)); });
    p.relations = p.relations.filter((r) => r.members.length >= (r.kind === 'max_per_class' ? 1 : 2) && (r.kind !== 'pairs_diff' || r.pairs.length));
    p.plans.forEach((pl) => { keys.forEach((k) => { delete pl.assignment[k]; delete (pl.locks || {})[k]; delete (pl.original || {})[k]; delete (pl.new_numbers || {})[k]; }); });
    keys.forEach((k) => this.sel.delete(k));
    App.resetStuMap(); App.log('교사', `학생 ${keys.length}명 삭제`); App.changed(); done();
  },

  /* ---------------- 엑셀 불러오기 ---------------- */
  async importWizard() {
    const file = await App.pickFile('.xlsx,.xlsm,.csv'); if (!file) return;
    const p = App.state.project;
    let parsed;
    try {
      const url = await App.readFile(file); const b64 = url.split(',')[1];
      parsed = await App.api('POST', 'import/parse', { data: b64, filename: file.name, project: p });
    } catch (e) { return App.toast(e.message, 'err'); }
    const sheets = parsed.sheets.filter((s) => s.headers.length);
    if (!sheets.length) return App.toast('파일에서 표(머리글 행)를 찾지 못했습니다.', 'err');
    const stuSheet = sheets.find((s) => s.name === '학생 명단') || sheets.find((s) => s.guess_students.sid !== undefined && s.guess_students.name !== undefined) || sheets[0];
    const relSheet = sheets.find((s) => s.name === '학생 간 관계' && s.rows.length);
    const fields = [['sid', '학생 ID *'], ['name', '이름 *'], ['grade', '현재 학년'], ['cls', '현재 반'], ['num', '현재 번호'], ['gender', '성별'], ['eligible', '편성 대상'], ['transfer_in', '전입 예정'], ['fixed_class', '지정 학급'], ['memo', '교사용 메모'],
      ...App.activeFeatures(true).map((f) => ['feature:' + f.id, '특성: ' + f.name])];
    const relFields = [['strength', '강도 *'], ['kind', '조건 *'], ['members', '학생 ID 목록 *'], ['pairs', '다른 반 쌍 목록'], ['max_n', '최대 인원(N)'], ['importance', '중요도'], ['reason', '사유']];
    const mapSel = (sheet, guess, fid) => `<select data-map="${fid}"><option value="">(연결 안 함)</option>${sheet.headers.map((h, i) => `<option value="${i}" ${guess[fid] === i ? 'selected' : ''}>${esc(h || '(빈 머리글 ' + (i + 1) + '열)')}</option>`).join('')}</select>`;
    const body = `
      ${parsed.seen_before ? '<div class="notice n-warn">⚠ 이 파일은 이 프로젝트에 이미 불러온 적이 있는 파일과 내용이 같습니다 (동일 자료 중복 불러오기). 이미 있는 학생은 아래 검사에서 표시됩니다.</div>' : ''}
      <p>파일: <b>${esc(parsed.filename)}</b> · 시트 ${sheets.length}개</p>
      <h3>1. 학생 명단 시트와 열 연결</h3>
      <label class="field"><span>학생 명단이 있는 시트</span><select id="iSheet">${sheets.map((s) => `<option ${s === stuSheet ? 'selected' : ''}>${esc(s.name)}</option>`).join('')}</select></label>
      <p class="small muted">학교마다 열 이름이 다를 수 있습니다. 파일의 어떤 열이 프로그램의 어떤 항목인지 연결하세요. (예: ‘성명’ 열 → ‘이름’)</p>
      <div id="iMap"></div>
      <div class="field"><span>이미 명단에 있는 학생 ID가 있을 때</span><label class="chk"><input type="radio" name="iPol" value="skip" checked> 기존 정보 유지 (건너뛰기)</label><label class="chk"><input type="radio" name="iPol" value="update"> 이 파일의 내용으로 갱신</label></div>
      ${relSheet ? `<h3>2. 학생 간 관계 시트 (${relSheet.rows.length}행)</h3><label class="chk"><input type="checkbox" id="iRel" checked> 관계 조건도 함께 불러오기</label><div id="iRelMap"><table class="tbl compact"><tbody>${relFields.map(([k, l]) => `<tr><td>${esc(l)}</td><td>${mapSel(relSheet, relSheet.guess_relations, k)}</td></tr>`).join('')}</tbody></table></div>` : ''}
      <div id="iResult"></div>`;
    let lastCheck = null;
    const m = App.modal({
      title: '엑셀에서 학생 명단 불러오기', wide: true, body,
      buttons: [{ label: '취소' }, { label: '검사하기 (미리보기)', onClick: () => { check(); return false; } }, { label: '불러오기', cls: 'btn-pri', id: 'iGo', disabled: true, onClick: () => apply() }],
    });
    const el = m.el;
    const sheetByName = (n) => sheets.find((s) => s.name === n);
    const renderMap = () => {
      const sh = sheetByName(el.querySelector('#iSheet').value);
      el.querySelector('#iMap').innerHTML = `<table class="tbl compact"><thead><tr><th>프로그램 항목</th><th>파일의 열</th><th>첫 행 값</th></tr></thead><tbody>${fields.map(([k, l]) => `<tr><td>${esc(l)}</td><td>${mapSel(sh, sh.guess_students, k)}</td><td class="small muted" data-first="${k}"></td></tr>`).join('')}</tbody></table>`;
      const showFirst = () => App.$$('#iMap [data-map]', el).forEach((s) => { const td = el.querySelector(`[data-first="${s.dataset.map}"]`); td.textContent = s.value === '' || !sh.rows[0] ? '' : (sh.rows[0].values[Number(s.value)] || '(빈칸)'); });
      App.$$('#iMap [data-map]', el).forEach((s) => { s.onchange = () => { showFirst(); invalidate(); }; }); showFirst();
    };
    const invalidate = () => { lastCheck = null; el.querySelector('#iGo').disabled = true; };
    el.querySelector('#iSheet').onchange = () => { renderMap(); invalidate(); };
    App.$$('input[name=iPol]', el).forEach((r) => { r.onchange = invalidate; });
    renderMap();
    const getMap = (sel) => { const mp = {}; App.$$(sel + ' [data-map]', el).forEach((s) => { if (s.value !== '') mp[s.dataset.map] = Number(s.value); }); return mp; };
    const check = async () => {
      const sh = sheetByName(el.querySelector('#iSheet').value);
      const mp = getMap('#iMap'); const pol = el.querySelector('input[name=iPol]:checked').value;
      const used = Object.values(mp); if (new Set(used).size !== used.length) return App.toast('한 열을 두 항목에 연결할 수 없습니다.', 'err');
      try {
        const sr = await App.api('POST', 'import/students', { project: p, sheet: sh, mapping: mp, existing_policy: pol });
        let rr = null;
        if (relSheet && el.querySelector('#iRel') && el.querySelector('#iRel').checked) {
          rr = await App.api('POST', 'import/relations', { project: p, sheet: relSheet, mapping: getMap('#iRelMap'), extra_sids: sr.students.filter((s) => s._ok).map((s) => s.sid) });
        }
        lastCheck = { sr, rr, pol };
        const errs = sr.errors.concat(rr ? rr.errors.map((e) => ({ ...e, field: '[관계] ' + e.field })) : []);
        const errRows = [...new Set(sr.errors.map((e) => e.row))];
        el.querySelector('#iResult').innerHTML = `<h3>검사 결과</h3>
          <div class="notice ${errs.length ? 'n-bad' : 'n-ok'}">전체 ${sr.summary.total}행 · 새 학생 <b>${sr.summary.new}</b>명 · 갱신 ${sr.summary.update}명 · 같은 자료라서 건너뜀 ${sr.summary.skip_same}명 · 기존 유지 ${sr.summary.skip_diff}명 · <b>오류 ${errs.length}건</b>
          ${rr ? ` · 관계 조건 ${rr.relations.length}개 (이미 있는 조건 ${rr.relations.filter((x) => x._duplicate).length}개는 건너뜀)` : ''}</div>
          ${errs.length ? `<p><b>오류는 자동으로 고치거나 버리지 않습니다.</b> 엑셀 파일을 고친 뒤 다시 올리거나, 아래에서 오류 행을 명시적으로 제외할 수 있습니다.</p>
          <div class="tbl-wrap" style="max-height:260px"><table class="tbl compact"><thead><tr><th class="num">행 번호</th><th>항목</th><th>수정할 내용</th></tr></thead><tbody>${errs.map((e) => `<tr><td class="num">${esc(e.row ?? '-')}</td><td>${esc(e.field)}</td><td>${esc(e.message)}</td></tr>`).join('')}</tbody></table></div>
          ${errRows.length && !(rr && rr.errors.length) ? `<label class="chk" style="margin-top:8px"><input type="checkbox" id="iSkipErr"> 오류가 있는 ${errRows.length}개 행(${errRows.slice(0, 15).join(', ')}${errRows.length > 15 ? '…' : ''}행)은 불러오지 않고 나머지만 불러오기</label>` : ''}` : ''}
          ${sr.notes.length ? `<details ${sr.notes.length < 8 ? 'open' : ''}><summary>안내 ${sr.notes.length}건</summary><ul>${sr.notes.map((n) => `<li>${esc(n.row)}행: ${esc(n.message)}</li>`).join('')}</ul></details>` : ''}
          <details><summary>불러올 자료 미리보기 (처음 8명)</summary><table class="tbl compact"><thead><tr><th>행</th><th>학생 ID</th><th>이름</th><th>현재 반</th><th>번호</th><th>성별</th><th>편성 대상</th><th>입력된 특성 수</th></tr></thead><tbody>
          ${sr.students.slice(0, 8).map((s) => `<tr><td>${s._row}</td><td>${esc(s.sid)}</td><td>${esc(App.state.share ? '○○' : s.name)}</td><td>${esc(s.cls || '')}</td><td>${esc(s.num ?? '')}</td><td>${esc(s.gender || '미입력')}</td><td>${s.eligible === false ? '제외' : '대상'}</td><td>${Object.keys(s.traits || {}).length}</td></tr>`).join('')}</tbody></table></details>`;
        const go = el.querySelector('#iGo');
        const upd = () => { const skip = el.querySelector('#iSkipErr'); go.disabled = !(sr.summary.new + sr.summary.update + (rr ? rr.relations.length : 0)) || (errs.length > 0 && !(skip && skip.checked)); };
        const sk = el.querySelector('#iSkipErr'); if (sk) sk.onchange = upd; upd();
      } catch (e) { App.toast(e.message, 'err'); }
    };
    const apply = () => {
      if (!lastCheck) return false;
      const { sr, rr, pol } = lastCheck;
      const bySid = {}; p.students.forEach((s) => { bySid[s.sid] = s; });
      let added = 0, updated = 0;
      sr.students.filter((s) => s._ok).forEach((s) => {
        const clean = { sid: s.sid, name: s.name, grade: s.grade, cls: s.cls, num: s.num, gender: s.gender, eligible: s.eligible, transfer_in: s.transfer_in, memo: s.memo, fixed_class: s.fixed_class, traits: s.traits };
        if (bySid[s.sid]) { if (s._existing === 'different' && pol === 'update') { const ex = bySid[s.sid]; Object.assign(ex, clean, { traits: Object.assign({}, ex.traits, s.traits) }); updated++; } }
        else { const ns = Object.assign({ key: App.uid('k') }, clean); p.students.push(ns); bySid[s.sid] = ns; added++; }
      });
      let rels = 0;
      if (rr) {
        rr.relations.filter((r) => !r._duplicate).forEach((r) => {
          const mem = r.member_sids.map((x) => bySid[x] && bySid[x].key).filter(Boolean);
          if (mem.length !== r.member_sids.length) return;
          p.relations.push({ id: App.uid('r'), kind: r.kind, strength: r.strength, members: mem, pairs: r.pair_sids.map(([a, b]) => [bySid[a].key, bySid[b].key]), max_n: r.max_n, importance: r.importance, reason: r.reason });
          rels++;
        });
      }
      p.import_hashes = p.import_hashes || []; if (!p.import_hashes.includes(parsed.hash)) p.import_hashes.push(parsed.hash);
      App.resetStuMap(); App.log('교사', `엑셀 불러오기: 새 학생 ${added}명, 갱신 ${updated}명, 관계 ${rels}개 (${parsed.filename})`);
      App.changed(); App.render(); App.toast(`불러오기 완료: 새 학생 ${added}명, 갱신 ${updated}명, 관계 조건 ${rels}개`, 'ok');
      return true;
    };
  },
};
