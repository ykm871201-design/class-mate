/* ⑦ 저장 및 출력 */
'use strict';
App.tabs.output = {
  mode: 'public', previewed: null,
  async render(main) {
    const p = App.state.project; const d = App.state.defaults; const plan = App.plan();
    let rep = null; if (plan) { try { rep = await App.evaluatePlan(plan); } catch (_) { rep = null; } }
    const feats = App.activeFeatures(true);
    this.opts = this.opts || { columns: d.default_public.slice(), features: null, include_conditions: true, include_reasons: false, include_memo: false, include_excluded: true };
    if (this.opts.features === null) this.opts.features = feats.filter((f) => f.include_in_export).map((f) => f.id);
    const o = this.opts;
    main.innerHTML = `
      <div class="panel"><h2>저장 상태</h2>
        <div class="kv"><b>저장 방식</b><span>변경할 때마다 이 PC에 자동 저장 (외부로 전송하지 않음) · 10분마다 자동 백업본 보관(최근 10개)</span>
        <b>저장 위치</b><span class="mono">${esc(App.state.savePath || (App.state.info.projects_dir + '\\' + p.id + '.json'))}</span>
        <b>자동 백업 위치</b><span class="mono">${esc(App.state.info.backups_dir)}</span>
        <b>마지막 저장</b><span id="oSaved">${App.state.dirty ? '✎ 저장 대기 중' : '✔ ' + esc(App.timeText(App.state.lastSaved || p.updated_at))}</span></div>
        <div class="row" style="margin-top:10px"><button class="btn" id="oSave">지금 저장</button><button class="btn" id="oBackup">💾 프로젝트 백업 파일 내보내기</button><button class="btn" id="oRestore">📂 백업 파일 불러오기</button></div>
        <p class="small muted">백업 파일에는 학생 명단·특성·관계·조건·편성안·고정 상태가 모두 들어 있으므로 안전한 곳에 보관하세요. AI API 키는 백업 파일에 포함되지 않습니다.</p></div>
      <div class="panel"><h2>최종 확정 및 새 번호</h2>
        ${plan ? `<p>현재 편성안: <b>${esc(plan.name)}</b> ${plan.confirmed ? '<span class="badge b-ok">✅ 확정됨</span>' : '<span class="badge b-gray">확정 전</span>'} ${rep ? (rep.hard.ok ? '<span class="badge b-ok">✔ 필수 조건 충족</span>' : '<span class="badge b-bad">✖ 필수 조건 위반 — 확정 불가</span>') : ''}
          <span class="small muted">(편성안은 ⑥ 결과 화면에서 바꿀 수 있습니다)</span></p>
          <div class="row">${plan.confirmed ? '<button class="btn" id="oUnconf">확정 해제</button>' : `<button class="btn btn-pri" id="oConf" ${rep && rep.hard.ok ? '' : 'disabled'}>이 편성안으로 최종 확정</button>`}
          <label class="field"><span>새 번호 부여 기준</span><select id="oRule">${Object.entries(d.number_rules).map(([k, v]) => `<option value="${k}" ${plan.numbering_rule === k ? 'selected' : ''}>${esc(v)}</option>`).join('')}</select></label>
          <button class="btn" id="oNum" ${plan.confirmed ? '' : 'disabled'}>새 번호 부여</button></div>
          <p class="small muted">새 번호는 최종 확정 후 부여합니다. 현재 번호는 별도로 그대로 보존됩니다.</p>
          ${Object.keys(plan.new_numbers || {}).length ? `<details><summary>새 번호 미리보기 (${esc(d.number_rules[plan.numbering_rule] || '')})</summary><div class="grid2">${p.classes.map((c) => `<div><b>${esc(c.name)}</b><table class="tbl compact"><thead><tr><th class="num">새 번호</th><th>이름</th><th>현재 반·번호</th></tr></thead><tbody>${Object.keys(plan.assignment).filter((k) => plan.assignment[k] === c.id && App.stuByKey(k)).sort((a, b) => (plan.new_numbers[a] || 999) - (plan.new_numbers[b] || 999)).map((k) => { const s = App.stuByKey(k); return `<tr><td class="num">${plan.new_numbers[k] ?? '-'}</td><td>${esc(App.dn(s))}</td><td>${esc(App.state.share ? '' : (s.cls || '') + ' ' + (s.num ?? ''))}</td></tr>`; }).join('')}</tbody></table></div>`).join('')}</div></details>` : ''}`
        : '<p class="muted">편성안이 없습니다.</p>'}</div>
      <div class="panel"><h2>엑셀로 내보내기</h2>
        ${plan ? `<div class="row"><label class="chk"><input type="radio" name="oMode" value="public" ${this.mode === 'public' ? 'checked' : ''}> <b>일반 배부용</b> — 필요한 명단 항목만 (학생 특성·메모·관계 사유는 숨김 시트나 숨김 열로도 포함하지 않음)</label></div>
          <div class="row"><label class="chk"><input type="radio" name="oMode" value="staff" ${this.mode === 'staff' ? 'checked' : ''}> <b>담당 교사용</b> — 선택한 특성과 조건 포함 (외부 배부 금지)</label></div>
          <h3>명단 항목</h3><div>${d.public_columns.map(([k, l]) => `<label class="chk"><input type="checkbox" class="oCol" value="${k}" ${o.columns.includes(k) ? 'checked' : ''}> ${esc(l)}</label>`).join('')}</div>
          <div id="oStaff" class="${this.mode === 'staff' ? '' : 'hidden'}"><h3>포함할 특성 (담당 교사용)</h3><div>${feats.map((f) => `<label class="chk"><input type="checkbox" class="oFeat" value="${esc(f.id)}" ${o.features.includes(f.id) ? 'checked' : ''}> ${esc(f.name)}</label>`).join('') || '<span class="muted">사용 중인 특성 없음</span>'}</div>
            <div style="margin-top:6px"><label class="chk"><input type="checkbox" id="oCond" ${o.include_conditions ? 'checked' : ''}> ⑤ 조건 설정 및 충족 현황 시트</label><label class="chk"><input type="checkbox" id="oReason" ${o.include_reasons ? 'checked' : ''}> 관계 사유 포함</label>
            <label class="chk"><input type="checkbox" id="oMemo" ${o.include_memo ? 'checked' : ''}> 교사용 메모 포함</label><label class="chk"><input type="checkbox" id="oExcl" ${o.include_excluded ? 'checked' : ''}> 편성 제외 학생 목록</label></div></div>
          <div class="row" style="margin-top:10px"><button class="btn" id="oPrev">① 포함될 항목 미리보기</button><button class="btn btn-pri" id="oExport" ${this.previewed ? '' : 'disabled'}>② 엑셀 파일 받기</button></div>
          <div id="oPrevBox">${this.previewed ? this.previewHtml(this.previewed) : '<p class="small muted">내보내기 전에 포함될 시트와 항목을 먼저 확인하세요.</p>'}</div>`
        : '<p class="muted">편성안이 없습니다.</p>'}</div>
      <div class="panel"><h2>변경 기록</h2><p class="small muted">AI 제안 적용과 주요 변경 내용이 기록됩니다. ‘되돌리기’가 있는 항목은 적용 전 상태로 돌릴 수 있습니다.</p>
        <div class="tbl-wrap" style="max-height:300px"><table class="tbl compact"><thead><tr><th>시각</th><th>구분</th><th>내용</th><th></th></tr></thead><tbody>
        ${(p.change_log || []).slice().reverse().map((l) => `<tr><td class="small">${esc(App.timeText(l.at))}</td><td>${esc(l.source)}</td><td class="small">${esc(l.text)}</td><td>${l.undo ? `<button class="btn btn-sm" data-undo="${esc(l.id)}">되돌리기</button>` : ''}</td></tr>`).join('') || '<tr><td colspan="4" class="muted">기록 없음</td></tr>'}</tbody></table></div></div>
      <div class="panel"><h2>자료 삭제</h2><div class="row"><button class="btn btn-danger" id="oDelProj">이 프로젝트 삭제</button><button class="btn btn-danger solid" id="oDelAll">전체 자료 삭제 (모든 프로젝트·백업·AI 설정)</button></div></div>`;
    this.bind(main, plan, rep);
  },

  collect(main) {
    const o = this.opts;
    o.columns = App.$$('.oCol:checked', main).map((c) => c.value);
    if (this.mode === 'staff') {
      o.features = App.$$('.oFeat:checked', main).map((c) => c.value);
      o.include_conditions = main.querySelector('#oCond').checked; o.include_reasons = main.querySelector('#oReason').checked;
      o.include_memo = main.querySelector('#oMemo').checked; o.include_excluded = main.querySelector('#oExcl').checked;
    }
    return { plan_id: App.state.project.active_plan_id, mode: this.mode, columns: o.columns, features: this.mode === 'staff' ? o.features : [],
      include_conditions: this.mode === 'staff' && o.include_conditions, include_reasons: this.mode === 'staff' && o.include_reasons,
      include_memo: this.mode === 'staff' && o.include_memo, include_excluded: this.mode === 'staff' && o.include_excluded };
  },

  previewHtml(pv) {
    return `<div class="notice ${pv.mode === 'public' ? 'n-ok' : 'n-warn'}"><b>${pv.mode === 'public' ? '일반 배부용' : '담당 교사용 (외부 배부 금지)'}</b> — 편성안: ${esc(pv.plan_name)} ${pv.confirmed ? '(✅ 확정)' : '(⚠ 아직 확정 전)'}</div>
      ${pv.warning ? `<div class="notice n-warn">${esc(pv.warning)}</div>` : ''}
      <table class="tbl compact"><thead><tr><th>시트</th><th>포함 항목</th></tr></thead><tbody>${pv.sheets.map((s) => `<tr><td><b>${esc(s.name)}</b></td><td class="small">${s.columns.map(esc).join(', ')}</td></tr>`).join('')}</tbody></table>
      ${pv.excluded.length ? `<p><b>포함하지 않는 항목:</b> ${pv.excluded.map(esc).join(', ')}</p>` : ''}
      ${pv.mode === 'public' ? '<p class="small muted">일반 배부용 파일은 만든 직후 프로그램이 파일 전체(숨김 시트·숨김 열 포함)를 다시 검사하여, 특성·메모·관계 사유가 들어 있으면 내보내기를 중단합니다.</p>' : ''}`;
  },

  bind(main, plan, rep) {
    const p = App.state.project; const re = () => this.render(main);
    main.querySelector('#oSave').onclick = async () => { await App.save(); App.toast(App.state.saveError ? '저장 실패: ' + App.state.saveError : '저장했습니다: ' + App.state.savePath, App.state.saveError ? 'err' : 'ok'); re(); };
    main.querySelector('#oBackup').onclick = async () => { if (App.state.dirty) await App.save(); try { const n = await App.download('projects/' + p.id + '/backup', null, 'backup.json'); App.toast('백업 파일을 내려받았습니다: ' + n, 'ok'); } catch (e) { App.toast(e.message, 'err'); } };
    main.querySelector('#oRestore').onclick = () => App.tabs.project.restore();
    const cf = main.querySelector('#oConf');
    if (cf) cf.onclick = async () => { if (!await App.confirm('최종 확정', `<p>‘${esc(plan.name)}’을(를) 최종 편성안으로 확정합니다. 확정 후에는 수정이 잠기며, 필요하면 확정을 해제할 수 있습니다.</p>`, '확정')) return; plan.confirmed = true; plan.confirmed_at = App.nowIso(); App.log('교사', `최종 확정: ${plan.name}`); App.changed({ keepEval: true }); re(); };
    const uc = main.querySelector('#oUnconf'); if (uc) uc.onclick = () => { plan.confirmed = false; App.log('교사', `확정 해제: ${plan.name}`); App.changed({ keepEval: true }); re(); };
    const nb = main.querySelector('#oNum');
    if (nb) nb.onclick = async () => { const rule = main.querySelector('#oRule').value; const r = await App.api('POST', 'numbering', { project: p, assignment: plan.assignment, rule }); plan.new_numbers = r.numbers; plan.numbering_rule = rule; App.log('교사', `새 번호 부여 (${App.state.defaults.number_rules[rule]})`); App.changed({ keepEval: true }); this.previewed = null; App.toast('새 번호를 부여했습니다. 현재 번호는 그대로 보존됩니다.', 'ok'); re(); };
    main.querySelectorAll('input[name=oMode]').forEach((r) => { r.onchange = () => { this.collect(main); this.mode = r.value; this.previewed = null; re(); }; });
    main.querySelectorAll('.oCol,.oFeat,#oCond,#oReason,#oMemo,#oExcl').forEach((c) => { c.onchange = () => { this.collect(main); this.previewed = null; main.querySelector('#oExport').disabled = true; main.querySelector('#oPrevBox').innerHTML = '<p class="small muted">선택이 바뀌었습니다. 다시 미리보기를 확인하세요.</p>'; }; });
    const pv = main.querySelector('#oPrev');
    if (pv) pv.onclick = async () => { const opt = this.collect(main); if (!opt.columns.length) return App.toast('명단 항목을 하나 이상 고르세요.', 'err'); try { this.previewed = await App.api('POST', 'export/preview', { project: p, options: opt }); this.previewed._opt = opt; } catch (e) { return App.toast(e.message, 'err'); } re(); };
    const ex = main.querySelector('#oExport');
    if (ex) ex.onclick = async () => { try { const n = await App.download('export', { project: p, options: this.previewed._opt }, '학급편성결과.xlsx'); App.log('교사', `엑셀 내보내기 (${this.mode === 'staff' ? '담당 교사용' : '일반 배부용'})`); App.changed({ keepEval: true }); App.toast('엑셀 파일을 내려받았습니다: ' + n, 'ok'); } catch (e) { App.toast(e.message, 'err'); } };
    main.querySelectorAll('[data-undo]').forEach((b) => {
      b.onclick = async () => {
        const l = p.change_log.find((x) => x.id === b.dataset.undo); if (!l || !l.undo) return;
        if (!await App.confirm('되돌리기', `<p>‘${esc(l.text)}’ 적용 전 상태로 되돌립니다.</p>`, '되돌리기')) return;
        if (l.undo.type === 'settings') { p.features = l.undo.before.features; p.balance = l.undo.before.balance; p.combos = l.undo.before.combos; }
        if (l.undo.type === 'traits') l.undo.before.forEach((x) => { const s = App.stuByKey(x.key); if (!s) return; if (x.v === undefined || x.v === null) delete s.traits[x.fid]; else s.traits[x.fid] = x.v; });
        l.undo = null; App.log('교사', `되돌리기: ${l.text}`); App.changed(); re();
      };
    });
    main.querySelector('#oDelProj').onclick = async () => {
      if (!await App.confirm('이 프로젝트 삭제', `<p>‘${esc(p.name)}’ 프로젝트와 자동 백업본을 삭제합니다. 되돌릴 수 없습니다.</p>`, '삭제', true)) return;
      await App.api('DELETE', 'projects/' + p.id); App.state.project = null; try { localStorage.removeItem('cp_last'); } catch (_) { /* 무시 */ } App.updateSaveBadge(); App.go('project');
    };
    main.querySelector('#oDelAll').onclick = () => {
      App.modal({
        title: '전체 자료 삭제', body: '<div class="notice n-bad">이 PC에 저장된 <b>모든 프로젝트, 자동 백업본, AI 연결 설정과 API 키</b>를 삭제합니다. 되돌릴 수 없습니다.</div><p>계속하려면 아래 칸에 <b>전체 삭제</b>라고 입력하세요.</p><input type="text" id="delAllTxt" style="width:100%">',
        buttons: [{ label: '취소' }, {
          label: '모두 삭제', cls: 'btn-danger solid', onClick: async (el) => {
            const t = el.querySelector('#delAllTxt').value.trim(); if (t !== '전체 삭제') { App.toast('확인 문구가 일치하지 않습니다.', 'err'); return false; }
            await App.api('POST', 'delete-all', { confirm: t }); App.state.project = null; try { localStorage.clear(); } catch (_) { /* 무시 */ } App.updateSaveBadge(); App.toast('모든 자료를 삭제했습니다.', 'ok'); App.go('project'); return true;
          },
        }],
      });
    };
  },
};
