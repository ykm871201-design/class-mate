/* ① 프로젝트 */
'use strict';
App.tabs.project = {
  async render(main) {
    main.innerHTML = '<div class="panel">불러오는 중…</div>';
    try { const r = await App.api('GET', 'projects'); App.state.projects = r.projects; App.state.projectsDir = r.dir; } catch (e) { main.innerHTML = `<div class="notice n-bad">${esc(e.message)}</div>`; return; }
    const p = App.state.project;
    main.innerHTML = `
      ${p ? this.workflowHtml(p) : ''}
      <div class="panel">
        <h2>편성 프로젝트</h2>
        <p class="muted">프로젝트마다 학생 명단·특성 항목·관계·조건·편성안·고정 상태가 함께 저장됩니다. 저장 위치: <span class="mono">${esc(App.state.projectsDir)}</span></p>
        <div class="row" style="margin:10px 0">
          <button class="btn btn-pri" id="newProj">＋ 새 프로젝트 만들기</button>
          <button class="btn" id="sampleProj">🧪 가상 예시 프로젝트 만들기 (가상 학생 120명·5학급)</button>
          <button class="btn" id="restoreProj">📂 백업 파일에서 불러오기</button>
        </div>
        ${App.state.projects.length ? `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>프로젝트 이름</th><th class="num">학년도</th><th class="num">진급 학년</th><th class="num">학생 수</th><th class="num">편성안</th><th>마지막 저장</th><th></th></tr></thead><tbody>
          ${App.state.projects.map((x) => `<tr ${p && p.id === x.id ? 'style="background:#eef5ff"' : ''}><td>${p && p.id === x.id ? '▶ <b>' + esc(x.name) + '</b> (열려 있음)' : esc(x.name)}</td><td class="num">${esc(x.school_year)}</td><td class="num">${esc(x.next_grade)}학년</td>
            <td class="num">${x.n_students}</td><td class="num">${x.n_plans}</td><td>${esc(App.timeText(x.updated_at))}</td>
            <td><div class="btn-group"><button class="btn btn-sm" data-open="${esc(x.id)}">열기</button><button class="btn btn-sm btn-danger" data-del="${esc(x.id)}" data-name="${esc(x.name)}">삭제</button></div></td></tr>`).join('')}
        </tbody></table></div>` : '<div class="notice n-info">아직 프로젝트가 없습니다. 새 프로젝트를 만들거나, 실제 학생 자료 없이 기능을 체험하려면 가상 예시 프로젝트를 만들어 보세요.</div>'}
      </div>
      ${p ? this.settingsHtml(p) : ''}`;
    main.querySelector('#newProj').onclick = () => this.newDialog();
    main.querySelector('#sampleProj').onclick = async () => {
      const np = await App.api('POST', 'projects/sample'); await App.openProject(np.id); App.toast('가상 예시 프로젝트를 만들었습니다. (실존 인물과 무관한 가상 자료)', 'ok'); App.render();
    };
    main.querySelector('#restoreProj').onclick = () => this.restore();
    main.querySelectorAll('[data-open]').forEach((b) => { b.onclick = async () => { if (App.state.dirty) await App.save(); await App.openProject(b.dataset.open); App.render(); }; });
    main.querySelectorAll('[data-del]').forEach((b) => {
      b.onclick = async () => {
        if (!await App.confirm('프로젝트 삭제', `<p>‘${esc(b.dataset.name)}’ 프로젝트와 자동 백업본을 이 PC에서 삭제합니다. 되돌릴 수 없습니다.</p><p>필요하면 먼저 ⑦ 저장 및 출력에서 백업 파일을 내보내세요.</p>`, '삭제', true)) return;
        await App.api('DELETE', 'projects/' + b.dataset.del);
        if (App.state.project && App.state.project.id === b.dataset.del) { App.state.project = null; try { localStorage.removeItem('cp_last'); } catch (_) { /* 무시 */ } App.updateSaveBadge(); }
        App.toast('프로젝트를 삭제했습니다.'); App.render();
      };
    });
    if (p) this.bindSettings(main, p);
  },

  workflowHtml(p) {
    const el = p.students.filter((s) => s.eligible !== false).length;
    const feats = p.features.filter((f) => f.active && f.type !== 'text');
    let filled = 0, total = 0;
    p.students.forEach((s) => { if (s.eligible === false) return; feats.forEach((f) => { total++; if (!App.isMissing(f, (s.traits || {})[f.id])) filled++; }); });
    const plan = App.plan();
    const st = [
      ['①', '프로젝트 설정', `${p.classes.length}개 학급 · 최대 ${p.classes.reduce((a, c) => a + Number(c.max || 0), 0)}명`, 'project'],
      ['②', '학생 명단', `${p.students.length}명 (편성 대상 ${el}명)`, 'students'],
      ['③', '학생 특성 입력', total ? `입력률 ${Math.round(filled / total * 100)}% (${feats.length}개 항목)` : '활성 항목 없음', 'students'],
      ['④', '관계·편성 조건', `관계 조건 ${p.relations.length}개`, 'relations'],
      ['⑤', '자동 편성', `편성안 ${p.plans.length}개`, 'solve'],
      ['⑥', '결과 확인·조정', plan ? `현재: ${plan.name}` : '편성안 없음', 'results'],
      ['⑦', '확정·엑셀 출력', p.plans.some((x) => x.confirmed) ? '✔ 확정된 편성안 있음' : '확정 전', 'output'],
    ];
    return `<div class="panel"><h2>작업 순서</h2><div class="steps">${st.map(([n, t, d, tab]) => `<div class="step" tabindex="0" data-step="${tab}"><div class="n">${n} ${t}</div><div class="small muted">${esc(d)}</div></div>`).join('')}</div></div>`;
  },

  settingsHtml(p) {
    const s = p.settings || {};
    const el = p.students.filter((x) => x.eligible !== false).length;
    const cap = p.classes.reduce((a, c) => a + Number(c.max || 0), 0);
    const tg = p.classes.reduce((a, c) => a + Number(c.target || 0), 0);
    return `<div class="panel" id="projSettings"><h2>현재 프로젝트 설정</h2>
      <div class="row">
        <label class="field grow"><span>프로젝트 이름</span><input type="text" id="pName" value="${esc(p.name)}"></label>
        <label class="field"><span>학년도</span><input type="number" id="pYear" value="${esc(s.school_year)}" style="width:110px"></label>
        <label class="field"><span>현재 학년</span><input type="number" id="pCur" value="${esc(s.current_grade)}" min="1" max="6" style="width:90px"></label>
        <label class="field"><span>진급 학년</span><input type="number" id="pNext" value="${esc(s.next_grade)}" min="1" max="6" style="width:90px"></label>
      </div>
      <h3>편성할 학급 (${p.classes.length}개)</h3>
      <p class="muted small">학급 이름은 가반·나반 또는 1반·2반 등 자유롭게 바꿀 수 있습니다. 목표 인원은 균형 계산의 기준이고, 최대 인원은 반드시 지키는 필수 조건입니다. 학급별 정원이 다르면 규모에 비례하여 분포를 비교합니다.</p>
      <div class="row" style="margin-bottom:8px">
        <button class="btn btn-sm" id="nameGa">이름을 가반·나반… 으로</button><button class="btn btn-sm" id="nameNum">이름을 1반·2반… 으로</button>
        <span class="muted">|</span> 모든 학급 목표 <input type="number" id="allT" style="width:80px"> 최대 <input type="number" id="allM" style="width:80px"> <button class="btn btn-sm" id="applyAll">일괄 적용</button>
      </div>
      <table class="tbl" style="max-width:760px"><thead><tr><th>순서</th><th>학급 이름</th><th>목표 인원</th><th>최대 인원</th><th></th></tr></thead><tbody>
      ${p.classes.map((c, i) => `<tr><td class="num">${i + 1}</td><td><input type="text" data-cn="${i}" value="${esc(c.name)}"></td><td><input type="number" data-ct="${i}" value="${esc(c.target)}" min="0"></td><td><input type="number" data-cm="${i}" value="${esc(c.max)}" min="0"></td>
        <td><button class="btn btn-sm btn-danger" data-cdel="${i}">삭제</button></td></tr>`).join('')}
      </tbody></table>
      <div class="row" style="margin-top:8px"><button class="btn" id="addClass">＋ 학급 추가</button></div>
      <div class="notice ${el > cap ? 'n-bad' : 'n-info'}" style="margin-top:10px">편성 대상 학생 <b>${el}명</b> · 목표 인원 합계 <b>${tg}명</b> · 최대 인원 합계 <b>${cap}명</b>
      ${el > cap ? ' — ✖ 최대 인원 합계가 학생 수보다 적어 편성할 수 없습니다.' : (tg !== el ? ' — ⓘ 목표 인원 합계와 학생 수가 다릅니다 (목표 인원 비율로 균형을 맞춥니다).' : ' — ✔ 인원 설정이 맞습니다.')}</div>
    </div>`;
  },

  bindSettings(main, p) {
    main.querySelectorAll('[data-step]').forEach((d) => { d.onclick = () => App.go(d.dataset.step); d.onkeydown = (e) => { if (e.key === 'Enter') App.go(d.dataset.step); }; });
    const bind = (id, fn) => { const el = main.querySelector(id); if (el) el.onchange = () => { fn(el.value); App.changed(); App.render(); }; };
    bind('#pName', (v) => { p.name = v.trim() || p.name; });
    bind('#pYear', (v) => { p.settings.school_year = Number(v) || p.settings.school_year; });
    bind('#pCur', (v) => { p.settings.current_grade = Number(v) || p.settings.current_grade; });
    bind('#pNext', (v) => { p.settings.next_grade = Number(v) || p.settings.next_grade; });
    main.querySelectorAll('[data-cn]').forEach((el) => { el.onchange = () => { const v = el.value.trim(); if (!v) { el.value = p.classes[el.dataset.cn].name; return App.toast('학급 이름은 비울 수 없습니다.', 'err'); } if (p.classes.some((c, i) => c.name === v && i !== Number(el.dataset.cn))) { el.value = p.classes[el.dataset.cn].name; return App.toast('같은 이름의 학급이 이미 있습니다.', 'err'); } p.classes[el.dataset.cn].name = v; App.changed(); }; });
    main.querySelectorAll('[data-ct]').forEach((el) => { el.onchange = () => { p.classes[el.dataset.ct].target = Math.max(0, Number(el.value) || 0); App.changed(); App.render(); }; });
    main.querySelectorAll('[data-cm]').forEach((el) => { el.onchange = () => { p.classes[el.dataset.cm].max = Math.max(0, Number(el.value) || 0); App.changed(); App.render(); }; });
    const rename = (pat) => { const ga = '가나다라마바사아자차카타파하'; p.classes.forEach((c, i) => { c.name = pat === 'ga' && i < ga.length ? ga[i] + '반' : (i + 1) + '반'; }); App.changed(); App.render(); };
    main.querySelector('#nameGa').onclick = () => rename('ga');
    main.querySelector('#nameNum').onclick = () => rename('num');
    main.querySelector('#applyAll').onclick = () => {
      const t = main.querySelector('#allT').value, m = main.querySelector('#allM').value;
      p.classes.forEach((c) => { if (t !== '') c.target = Number(t); if (m !== '') c.max = Number(m); }); App.changed(); App.render();
    };
    main.querySelector('#addClass').onclick = () => {
      let n = p.classes.length + 1; let id = 'c' + n; while (p.classes.some((c) => c.id === id)) { n++; id = 'c' + n; }
      const last = p.classes[p.classes.length - 1] || { target: 24, max: 26 };
      p.classes.push({ id, name: `${p.classes.length + 1}반`, target: last.target, max: last.max }); App.changed(); App.render();
    };
    main.querySelectorAll('[data-cdel]').forEach((b) => {
      b.onclick = async () => {
        const c = p.classes[b.dataset.cdel];
        const fixed = p.students.filter((s) => s.fixed_class === c.id);
        const inPlans = p.plans.filter((pl) => Object.values(pl.assignment || {}).includes(c.id));
        let html = `<p>‘${esc(c.name)}’ 학급을 삭제합니다.</p>`;
        if (fixed.length) html += `<div class="notice n-warn">이 학급에 지정 배정된 학생 ${fixed.length}명의 지정 배정이 해제됩니다.</div>`;
        if (inPlans.length) html += `<div class="notice n-warn">편성안 ${inPlans.length}개에서 이 학급 학생들이 ‘미배정’ 상태가 되어 필수 조건 위반으로 표시됩니다. 다시 편성하거나 수동으로 옮겨야 합니다.</div>`;
        if (!await App.confirm('학급 삭제', html, '삭제', true)) return;
        fixed.forEach((s) => { s.fixed_class = null; });
        p.plans.forEach((pl) => { Object.keys(pl.assignment).forEach((k) => { if (pl.assignment[k] === c.id) delete pl.assignment[k]; }); Object.keys(pl.locks || {}).forEach((k) => { if (pl.locks[k] === c.id) delete pl.locks[k]; }); });
        p.classes.splice(b.dataset.cdel, 1); App.log('교사', `학급 ‘${c.name}’ 삭제`); App.changed(); App.render();
      };
    });
  },

  newDialog() {
    App.modal({
      title: '새 편성 프로젝트 만들기',
      body: `<div class="field"><span>프로젝트 이름</span><input type="text" id="nName" value="${new Date().getFullYear() + 1}학년도 학급 편성"></div>
        <div class="row"><label class="field"><span>학년도</span><input type="number" id="nYear" value="${new Date().getFullYear() + 1}"></label>
        <label class="field"><span>현재 학년</span><input type="number" id="nCur" value="3" min="1" max="6"></label>
        <label class="field"><span>진급 학년</span><input type="number" id="nNext" value="4" min="1" max="6"></label></div>
        <div class="row"><label class="field"><span>편성할 학급 수</span><input type="number" id="nK" value="5" min="1" max="20"></label>
        <label class="field"><span>학급 이름</span><select id="nPat"><option value="ga">가반, 나반, 다반…</option><option value="number">1반, 2반, 3반…</option></select></label>
        <label class="field"><span>학급별 목표 인원</span><input type="number" id="nT" value="24"></label><label class="field"><span>학급별 최대 인원</span><input type="number" id="nM" value="26"></label></div>
        <p class="small muted">학급 이름과 인원은 만든 뒤에도 학급마다 따로 바꿀 수 있습니다. 기본 예시 특성 항목은 모두 ‘꺼짐’ 상태로 만들어지며, 필요한 항목만 켜서 쓰면 됩니다.</p>`,
      buttons: [{ label: '취소' }, {
        label: '만들기', cls: 'btn-pri', onClick: async (el) => {
          const v = (id) => el.querySelector(id).value;
          const np = await App.api('POST', 'projects', { name: v('#nName'), school_year: v('#nYear'), current_grade: v('#nCur'), next_grade: v('#nNext'), n_classes: v('#nK'), pattern: v('#nPat'), target: v('#nT'), max: v('#nM') });
          await App.openProject(np.id); App.toast('새 프로젝트를 만들었습니다.', 'ok'); App.render();
        },
      }],
    });
  },

  async restore() {
    const f = await App.pickFile('.json'); if (!f) return;
    try {
      const txt = await App.readFile(f, true); const j = JSON.parse(txt);
      const proj = j.project || j;
      const np = await App.api('POST', 'projects/import-backup', { project: proj });
      await App.openProject(np.id); App.toast('백업 파일에서 프로젝트를 복원했습니다. (새 프로젝트로 추가됨)', 'ok'); App.render();
    } catch (e) { App.toast('백업 파일을 불러오지 못했습니다: ' + e.message, 'err'); }
  },
};
