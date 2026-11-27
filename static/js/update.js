/* 새 버전 확인과 자동 업데이트 */
'use strict';
App.update = {
  st: null, info: null,

  async init() {
    const b = App.$('#updBtn'); b.onclick = () => this.open();
    try { this.st = await App.api('GET', 'update/status'); } catch (_) { return; }
    this.label();
    if (!this.st.auto_check) return;
    try {
      const r = await App.api('POST', 'update/check', {});
      if (r.ok) { this.info = r; this.label(); if (r.newer) App.toast(`새 버전 ${r.latest}이(가) 나왔습니다. 오른쪽 위 ‘⬆ 새 버전’ 버튼을 누르세요.`, 'ok'); }
    } catch (_) { /* 인터넷이 없어도 조용히 넘어감 */ }
  },

  label() {
    const b = App.$('#updBtn'); const nw = this.info && this.info.newer;
    b.textContent = nw ? `⬆ 새 버전 ${this.info.latest}` : '⬆ 업데이트';
    b.classList.toggle('upd-new', !!nw);
    b.title = this.st ? `현재 버전 ${this.st.version} (${this.st.mode_label})` : '';
  },

  async open() {
    const m = App.modal({ title: '⬆ 프로그램 업데이트', wide: true, body: '<p>새 버전을 확인하는 중…</p>', buttons: [{ label: '닫기' }] });
    let st = this.st, r;
    try { st = this.st = await App.api('GET', 'update/status'); r = await App.api('POST', 'update/check', {}); } catch (e) { r = { ok: false, error: e.message }; }
    if (r.ok) this.info = r;
    this.label();
    const body = m.el.querySelector('.modal-b'); const foot = m.el.querySelector('.modal-f');
    let html = `<div class="kv"><b>현재 버전</b><span>${esc(st.version)} <span class="badge b-gray">${esc(st.mode_label)}</span></span>`;
    if (r.ok) html += `<b>최신 버전</b><span>${esc(r.latest)}${r.published_at ? ` <span class="muted small">(${esc(r.published_at.slice(0, 10))} 게시)</span>` : ''}</span>`;
    html += '</div>';
    if (!r.ok) html += `<div class="notice n-warn">⚠ ${esc(r.error)}</div>`;
    else if (!r.newer) html += '<div class="notice n-ok">✔ 최신 버전을 사용하고 있습니다.</div>';
    else {
      html += `<div class="notice n-info"><b>새 버전 ${esc(r.latest)}이(가) 있습니다.</b> `;
      if (st.mode === 'installer') html += r.setup ? '‘지금 업데이트’를 누르면 내려받아 설치하고 프로그램을 다시 엽니다. 학생 자료와 설정은 그대로 유지됩니다.' : '설치 파일이 아직 준비 중입니다. 몇 분 뒤 다시 확인하세요.';
      else if (st.mode === 'portable') html += '휴대용(zip)은 자동으로 바꿀 수 없습니다. 내려받기 페이지에서 새 zip(또는 설치 파일)을 받으세요. 학생 자료는 따로 저장되어 있어 그대로 이어서 쓸 수 있습니다.';
      else html += '소스 실행 중에는 자동 업데이트를 하지 않습니다. 내려받기 페이지에서 새 버전을 받으세요.';
      html += '</div>';
      if (r.notes) html += `<details open><summary>바뀐 점</summary><pre class="payload">${esc(r.notes)}</pre></details>`;
    }
    html += `<label class="chk" style="margin-top:10px"><input type="checkbox" id="updAuto" ${st.auto_check ? 'checked' : ''}> 프로그램을 켤 때 새 버전 자동 확인</label>
      <p class="small muted">확인할 때는 GitHub에서 최신 버전 정보만 받아옵니다. 학생 이름·특성·메모 등 어떤 자료도 보내지 않습니다. 인터넷이 없으면 확인만 건너뜁니다.</p>`;
    body.innerHTML = html;
    body.querySelector('#updAuto').onchange = async (e) => { try { this.st = await App.api('POST', 'update/settings', { auto_update_check: e.target.checked }); } catch (err) { App.toast(err.message, 'err'); } };
    if (r.ok && r.newer) {
      const b = document.createElement('button'); b.className = 'btn btn-pri';
      if (st.mode === 'installer' && r.setup) { b.textContent = `지금 업데이트 (${r.latest})`; b.onclick = () => { m.close(); this.install(r); }; }
      else { b.textContent = '내려받기 페이지 열기'; b.onclick = () => window.open(r.page, '_blank', 'noopener'); }
      foot.appendChild(b);
    }
  },

  async install(r) {
    if (!await App.confirm('업데이트 설치', `<p>새 버전 <b>${esc(r.latest)}</b>을(를) 내려받아 설치합니다.</p>
      <ul><li>지금까지 작업한 내용은 먼저 저장됩니다.</li><li>설치하는 동안 프로그램(검은 창)이 잠시 꺼졌다가 자동으로 다시 열립니다.</li><li>이 브라우저 화면은 닫지 말고 그대로 두세요. 다시 열리면 자동으로 새로 고쳐집니다.</li></ul>`, '업데이트 시작')) return;
    if (App.state.dirty || App.state.saving) await App.save();
    if (App.state.saveError) return App.toast('저장에 실패하여 업데이트를 시작하지 않았습니다: ' + App.state.saveError, 'err');
    const wait = App.modal({ title: '업데이트 중', closable: false, buttons: [], body: '<p id="updMsg">새 버전을 내려받고 확인하는 중입니다… (인터넷 속도에 따라 1분 정도 걸릴 수 있습니다)</p><div class="progress"><div style="width:15%"></div></div>' });
    const msg = wait.el.querySelector('#updMsg'); const bar = wait.el.querySelector('.progress > div');
    let res;
    try { res = await App.api('POST', 'update/install', {}); } catch (e) {
      wait.close(); return App.alert('업데이트하지 못했습니다', `<div class="notice n-bad">${esc(e.message)}</div><p>프로그램은 그대로 사용할 수 있습니다.</p>`);
    }
    msg.textContent = res.message; bar.style.width = '45%';
    App.state.dirty = false;
    const oldPid = (App.state.info || {}).pid;
    const started = Date.now(); let wentDown = false;
    const poll = async () => {
      let info = null;
      try { const x = await fetch('/api/info', { cache: 'no-store' }); if (x.ok) info = await x.json(); } catch (_) { info = null; }
      if (!info) { wentDown = true; bar.style.width = '70%'; }
      else if (wentDown || (oldPid && info.pid !== oldPid)) { bar.style.width = '100%'; msg.textContent = `업데이트 완료 (버전 ${info.version}). 화면을 새로 고칩니다…`; setTimeout(() => location.reload(), 800); return; }
      if (Date.now() - started > 5 * 60 * 1000) { msg.innerHTML = '프로그램이 자동으로 다시 열리지 않았습니다. 바탕화면이나 시작 메뉴의 <b>학급 편성 도우미</b>를 직접 실행한 뒤 이 화면을 새로 고치세요.'; return; }
      setTimeout(poll, 2000);
    };
    setTimeout(poll, 2500);
  },
};
