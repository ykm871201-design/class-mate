/* 학급 편성 도우미 — 공통 기능 (외부 라이브러리·외부 전송 없음) */
'use strict';
const App = {
  state: {
    project: null, info: null, defaults: null, tab: 'project', share: false,
    dirty: false, saving: false, pendingSave: false, lastSaved: null, savePath: '', saveError: null,
    evalCache: {}, hist: {}, projects: [],
  },
  tabs: {},
  IMP: { low: '낮음', normal: '보통', high: '높음', very_high: '매우 높음' },
};

/* ---------------- 유틸 ---------------- */
App.esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const esc = App.esc;
App.fmtNum = (x) => {
  if (x === null || x === undefined || x === '') return '';
  if (typeof x === 'boolean') return x ? '예' : '아니요';
  const n = Number(x); if (Number.isInteger(n)) return String(n);
  return String(Math.round(n * 100) / 100);
};
App.uid = (p) => p + Math.random().toString(16).slice(2, 12);
App.nowIso = () => { const d = new Date(); const z = (n) => String(n).padStart(2, '0'); return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}T${z(d.getHours())}:${z(d.getMinutes())}:${z(d.getSeconds())}`; };
App.timeText = (iso) => iso ? iso.replace('T', ' ') : '';
App.clone = (o) => JSON.parse(JSON.stringify(o));
App.$ = (sel, root) => (root || document).querySelector(sel);
App.$$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

/* ---------------- 서버 통신 ---------------- */
App.api = async function (method, url, body) {
  const opt = { method, headers: {} };
  if (body !== undefined) { opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(body); }
  let r;
  try { r = await fetch('/api/' + url, opt); } catch (e) { throw new Error('프로그램 서버에 연결할 수 없습니다. 검은 실행 창이 켜져 있는지 확인하세요.'); }
  const j = await r.json().catch(() => ({ error: '응답을 읽을 수 없습니다.' }));
  if (!r.ok) throw new Error(j.error || '오류가 발생했습니다.');
  return j;
};
App.download = async function (url, body, fallbackName) {
  const r = await fetch('/api/' + url, { method: body ? 'POST' : 'GET', headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) { const j = await r.json().catch(() => ({})); throw new Error(j.error || '파일을 만들지 못했습니다.'); }
  const blob = await r.blob();
  let name = fallbackName;
  const cd = r.headers.get('Content-Disposition') || '';
  const m = cd.match(/filename\*=UTF-8''([^;]+)/);
  if (m) name = decodeURIComponent(m[1]);
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  return name;
};
App.readFile = (file, asText) => new Promise((res, rej) => {
  const fr = new FileReader();
  fr.onload = () => res(fr.result); fr.onerror = () => rej(new Error('파일을 읽지 못했습니다.'));
  if (asText) fr.readAsText(file, 'utf-8'); else fr.readAsDataURL(file);
});
App.pickFile = (accept) => new Promise((res) => {
  const inp = document.createElement('input'); inp.type = 'file'; inp.accept = accept; inp.style.display = 'none';
  document.body.appendChild(inp);
  inp.onchange = () => { res(inp.files[0] || null); inp.remove(); };
  inp.click();
});

/* ---------------- 저장 (자동 저장) ---------------- */
App.changed = function (opts) {
  if (!App.state.project) return;
  App.state.dirty = true;
  if (!opts || !opts.keepEval) App.state.evalCache = {};
  App.updateSaveBadge();
  clearTimeout(App._saveTimer);
  App._saveTimer = setTimeout(() => App.save(), 700);
};
App.save = async function () {
  const p = App.state.project; if (!p) return;
  if (App.state.saving) { App.state.pendingSave = true; return; }
  App.state.saving = true; App.state.dirty = false; App.updateSaveBadge();
  try {
    const r = await App.api('PUT', 'projects/' + p.id, p);
    p.updated_at = r.saved_at; App.state.lastSaved = r.saved_at; App.state.savePath = r.path; App.state.saveError = null;
  } catch (e) { App.state.saveError = e.message; App.state.dirty = true; }
  App.state.saving = false; App.updateSaveBadge();
  if (App.state.pendingSave) { App.state.pendingSave = false; App.save(); }
};
App.updateSaveBadge = function () {
  const b = App.$('#saveBadge'); const s = App.state;
  b.classList.toggle('err', !!s.saveError);
  if (!s.project) b.textContent = '저장할 내용 없음';
  else if (s.saveError) b.textContent = '⚠ 저장 실패 — ' + s.saveError;
  else if (s.saving) b.textContent = '⏳ 저장 중…';
  else if (s.dirty) b.textContent = '✎ 변경됨 (곧 자동 저장)';
  else b.textContent = '✔ 저장됨 ' + (s.lastSaved ? s.lastSaved.slice(11) : '');
  b.title = s.savePath ? '저장 위치: ' + s.savePath : '';
};
window.addEventListener('beforeunload', (e) => {
  if (App.state.dirty || App.state.saving) {
    const p = App.state.project;
    if (p) { try { fetch('/api/projects/' + p.id, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(p), keepalive: true }); } catch (_) { /* 무시 */ } }
    e.preventDefault(); e.returnValue = '';
  }
});

App.log = function (source, text, undo) {
  const p = App.state.project; if (!p) return;
  p.change_log = p.change_log || [];
  p.change_log.push({ id: App.uid('l'), at: App.nowIso(), source, text, undo: undo || null });
  if (p.change_log.length > 300) p.change_log.splice(0, p.change_log.length - 300);
};

/* ---------------- 알림/모달 ---------------- */
App.toast = function (msg, kind) {
  const t = document.createElement('div'); t.className = 'toast ' + (kind || ''); t.textContent = msg;
  App.$('#toastRoot').appendChild(t); setTimeout(() => t.remove(), kind === 'err' ? 7000 : 3800);
};
App.modal = function ({ title, body, buttons, wide, onOpen, closable = true }) {
  const back = document.createElement('div'); back.className = 'modal-back';
  back.innerHTML = `<div class="modal ${wide ? 'wide' : ''}" role="dialog" aria-modal="true" aria-label="${esc(title)}">
    <div class="modal-h"><span>${esc(title)}</span>${closable ? '<button class="x" aria-label="닫기">×</button>' : ''}</div>
    <div class="modal-b"></div><div class="modal-f"></div></div>`;
  const b = back.querySelector('.modal-b');
  if (typeof body === 'string') b.innerHTML = body; else if (body) b.appendChild(body);
  const close = () => { back.remove(); document.removeEventListener('keydown', onKey); };
  const onKey = (e) => { if (e.key === 'Escape' && closable) close(); };
  document.addEventListener('keydown', onKey);
  if (closable) back.querySelector('.x').onclick = close;
  const f = back.querySelector('.modal-f');
  (buttons || [{ label: '닫기' }]).forEach((bt) => {
    const el = document.createElement('button'); el.className = 'btn ' + (bt.cls || ''); el.textContent = bt.label;
    if (bt.id) el.id = bt.id;
    if (bt.disabled) el.disabled = true;
    el.onclick = async () => { if (bt.onClick) { const r = await bt.onClick(back); if (r === false) return; } close(); };
    f.appendChild(el);
  });
  App.$('#modalRoot').appendChild(back);
  if (onOpen) onOpen(back, close);
  const first = back.querySelector('input,select,textarea,button.btn-pri');
  if (first) setTimeout(() => first.focus(), 30);
  return { el: back, close };
};
App.confirm = (title, html, okLabel, danger) => new Promise((res) => {
  App.modal({ title, body: html, buttons: [{ label: '취소', onClick: () => res(false) }, { label: okLabel || '확인', cls: danger ? 'btn-danger solid' : 'btn-pri', onClick: () => res(true) }] });
});
App.alert = (title, html) => App.modal({ title, body: html });

/* ---------------- 학생 표시 (화면 공유 보기) ---------------- */
App.stuByKey = function (k) { const p = App.state.project; if (!App._stuMap || App._stuMapSrc !== p.students) { App._stuMap = {}; p.students.forEach((s, i) => { App._stuMap[s.key] = s; s._seq = i + 1; }); App._stuMapSrc = p.students; } return App._stuMap[k]; };
App.resetStuMap = () => { App._stuMapSrc = null; };
App.dn = function (s) { if (!s) return '(삭제된 학생)'; App.stuByKey(s.key); return App.state.share ? `학생 ${s._seq}` : (s.name || '(이름 없음)'); };
App.dnFull = function (s) { if (!s) return '(삭제된 학생)'; App.stuByKey(s.key); return App.state.share ? `학생 ${s._seq}` : `${s.name || '(이름 없음)'} (${s.sid})`; };
App.dnKey = (k) => App.dnFull(App.stuByKey(k));
App.stuInfo = function (s) { if (App.state.share) return ''; return [s.cls || (s.transfer_in ? '전입 예정' : ''), s.num ? s.num + '번' : '', s.gender].filter(Boolean).join(' · '); };
App.setShare = function (on) {
  App.state.share = on;
  const b = App.$('#shareBtn'); b.setAttribute('aria-pressed', on ? 'true' : 'false'); b.textContent = '🖥 화면 공유용 보기: ' + (on ? '켜짐' : '꺼짐');
  App.$('#shareBanner').classList.toggle('hidden', !on);
  try { localStorage.setItem('cp_share', on ? '1' : '0'); } catch (_) { /* 무시 */ }
  App.render();
};

/* ---------------- 특성 도우미 ---------------- */
App.levelSteps = function (f) {
  const lo = Number(f.min ?? 1), hi = Number(f.max ?? 5), st = Number(f.step || 1) || 1; const out = [];
  for (let v = lo, g = 0; v <= hi + 1e-9 && g < 1000; v += st, g++) out.push(Math.round(v * 1e6) / 1e6);
  return out;
};
App.levelLabel = (f, v) => { const k = App.fmtNum(v); const lab = (f.labels || {})[k]; return lab ? `${k} (${lab})` : k; };
App.isMissing = (f, v) => v === null || v === undefined || ((f.type === 'single' || f.type === 'text') && v === '');
App.traitText = function (f, v, short) {
  if (App.isMissing(f, v)) return '미입력';
  if (f.type === 'multi') return v.length ? v.join(', ') : '해당 없음';
  if (f.type === 'yesno') return v ? '예' : '아니요';
  if (f.type === 'level') return short ? App.fmtNum(v) : App.levelLabel(f, v);
  return String(v);
};
App.activeFeatures = (withText) => (App.state.project.features || []).filter((f) => f.active && (withText || f.type !== 'text'));
App.eligible = () => App.state.project.students.filter((s) => s.eligible !== false);
App.classById = (id) => App.state.project.classes.find((c) => c.id === id);
App.className = (id) => (App.classById(id) || {}).name || '-';
App.impSelect = (val, attrs) => `<select ${attrs || ''}>${Object.entries(App.IMP).map(([k, v]) => `<option value="${k}" ${k === val ? 'selected' : ''}>${v}</option>`).join('')}</select>`;
App.statusBadge = function (st, label) {
  const cls = { good: 'b-ok', caution: 'b-warn', bad: 'b-bad', no_data: 'b-gray' }[st] || 'b-gray';
  return `<span class="badge ${cls}">${esc(label || st)}</span>`;
};
App.relKindText = function (r) {
  const m = { same: '모두 같은 반', all_diff: '모두 서로 다른 반', pairs_diff: '특정 학생 쌍끼리 다른 반', max_per_class: `반마다 최대 ${r.max_n}명` };
  return m[r.kind] || r.kind;
};
App.strengthBadge = (r) => r.strength === 'must' ? '<span class="badge b-must">🔒 반드시</span>' : '<span class="badge b-prefer">◇ 가급적</span>';

/* ---------------- 편성안 / 실행 취소 ---------------- */
App.plan = function () { const p = App.state.project; if (!p) return null; return (p.plans || []).find((x) => x.id === p.active_plan_id) || null; };
App.hist = function (plan) { const h = App.state.hist; if (!h[plan.id]) h[plan.id] = { undo: [], redo: [] }; return h[plan.id]; };
App.pushHistory = function (plan, label) {
  const h = App.hist(plan); h.undo.push({ a: App.clone(plan.assignment), l: App.clone(plan.locks || {}), label }); if (h.undo.length > 80) h.undo.shift(); h.redo = [];
};
App.evaluatePlan = async function (plan, force) {
  if (!plan) return null;
  if (!force && App.state.evalCache[plan.id]) return App.state.evalCache[plan.id];
  const rep = await App.api('POST', 'evaluate', { project: App.state.project, assignment: plan.assignment, locks: plan.locks || {} });
  App.state.evalCache[plan.id] = rep; return rep;
};

/* ---------------- 화면 전환 ---------------- */
App.go = function (tab, opts) {
  App.state.tab = tab; App.state.gotoOpts = opts || null;
  try { localStorage.setItem('cp_tab', tab); } catch (_) { /* 무시 */ }
  App.render(); App.$('#main').focus();
};
App.goto = function (g) {
  if (!g || !g.tab) return;
  App.go(g.tab, g);
  if (g.student) setTimeout(() => App.tabs.students.openDetail(g.student), 50);
};
App.render = function () {
  App.$$('#tabs button').forEach((b) => b.classList.toggle('active', b.dataset.tab === App.state.tab));
  const p = App.state.project;
  App.$('#projName').textContent = p ? `📁 ${p.name}` : '프로젝트를 열거나 만드세요';
  const main = App.$('#main');
  const t = App.tabs[App.state.tab];
  if (!p && App.state.tab !== 'project') { App.state.tab = 'project'; return App.render(); }
  try { t.render(main, App.state.gotoOpts); } catch (e) { console.error(e); main.innerHTML = `<div class="notice n-bad">화면을 그리는 중 문제가 생겼습니다: ${esc(e.message)}</div>`; }
  App.state.gotoOpts = null;
};
App.flashRow = function (sel) {
  setTimeout(() => { const el = App.$(sel); if (el) { el.scrollIntoView({ block: 'center' }); el.classList.add('flash'); } }, 60);
};
App.openProject = async function (id) {
  const p = await App.api('GET', 'projects/' + id);
  App.state.project = p; App.state.evalCache = {}; App.state.hist = {}; App.resetStuMap();
  App.state.lastSaved = p.updated_at; App.state.dirty = false; App.state.saveError = null;
  try { localStorage.setItem('cp_last', id); } catch (_) { /* 무시 */ }
  App.updateSaveBadge();
};
App.issueHtml = function (it) {
  const ic = { error: '✖', warning: '⚠', info: 'ⓘ' }[it.level];
  const cls = { error: 'n-bad', warning: 'n-warn', info: 'n-info' }[it.level];
  const lab = { error: '편성 불가 (필수 조건 충돌)', warning: '주의', info: '안내' }[it.level];
  const go = it.goto && it.goto.tab ? `<button class="btn btn-sm" data-goto='${esc(JSON.stringify(it.goto))}'>해당 설정으로 이동 ▸</button>` : '';
  const studs = (it.students || []).length ? `<div class="small">관련 학생: ${it.students.slice(0, 12).map((k) => esc(App.dnKey(k))).join(', ')}${it.students.length > 12 ? ` 외 ${it.students.length - 12}명` : ''}</div>` : '';
  let msg = it.message;
  if (App.state.share) msg = msg.replace(/[가-힣A-Za-z]+\(S?[\w-]+\)/g, '○○');
  return `<div class="issue ${cls}"><span class="ic" aria-hidden="true">${ic}</span><div class="grow"><div class="tt">[${lab}] ${esc(it.title)}</div><div>${esc(msg)}</div>${studs}</div>${go}</div>`;
};
document.addEventListener('click', (e) => {
  const b = e.target.closest('[data-goto]');
  if (b) { e.preventDefault(); App.$$('.modal-back').forEach((m) => m.remove()); App.goto(JSON.parse(b.dataset.goto)); }
});

/* 학생 검색 선택기 (관계 설정 등에서 사용) */
App.studentPicker = function (container, { onPick, filter, placeholder }) {
  container.innerHTML = `<input type="search" class="sp-in" placeholder="${esc(placeholder || '이름 또는 학생 ID로 검색')}" style="width:100%"><div class="search-results sp-res hidden"></div>`;
  const inp = container.querySelector('.sp-in'), res = container.querySelector('.sp-res');
  const run = () => {
    const q = inp.value.trim().toLowerCase();
    if (!q) { res.classList.add('hidden'); return; }
    const list = App.state.project.students.filter((s) => (!filter || filter(s)) && ((s.name || '').toLowerCase().includes(q) || (s.sid || '').toLowerCase().includes(q))).slice(0, 30);
    res.innerHTML = list.length ? list.map((s) => `<div tabindex="0" data-k="${esc(s.key)}">${esc(App.dnFull(s))} <span class="muted small">${esc(App.stuInfo(s))}${s.eligible === false ? ' · 편성 제외' : ''}</span></div>`).join('') : '<div class="muted">검색 결과 없음</div>';
    res.classList.remove('hidden');
  };
  inp.addEventListener('input', run);
  res.addEventListener('click', (e) => { const d = e.target.closest('[data-k]'); if (d) { onPick(d.dataset.k); inp.value = ''; res.classList.add('hidden'); inp.focus(); } });
  res.addEventListener('keydown', (e) => { if (e.key === 'Enter') { const d = e.target.closest('[data-k]'); if (d) d.click(); } });
  inp.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); const d = res.querySelector('[data-k]'); if (d) d.click(); } if (e.key === 'ArrowDown') { const d = res.querySelector('[data-k]'); if (d) d.focus(); } });
};

App.start = async function () {
  App.$$('#tabs button').forEach((b) => { b.onclick = () => App.go(b.dataset.tab); });
  App.$('#shareBtn').onclick = () => App.setShare(!App.state.share);
  App.$('#aiBtn').onclick = () => App.ai.settingsModal();
  try {
    App.state.info = await App.api('GET', 'info');
    App.state.defaults = await App.api('GET', 'defaults');
  } catch (e) { App.$('#main').innerHTML = `<div class="notice n-bad">${esc(e.message)}</div>`; return; }
  let share = false, last = null, tab = 'project';
  try { share = localStorage.getItem('cp_share') === '1'; last = localStorage.getItem('cp_last'); tab = localStorage.getItem('cp_tab') || 'project'; } catch (_) { /* 무시 */ }
  if (last) { try { await App.openProject(last); App.state.tab = tab; App.toast('지난번 작업하던 프로젝트를 다시 열었습니다.', 'ok'); } catch (_) { App.state.tab = 'project'; } }
  App.state.share = share;
  App.setShare(share);
  App.update.init();
};
