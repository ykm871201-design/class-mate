/* AI 보조 기능: 연결 설정, 전송 전 확인, 결과 전달 */
'use strict';
App.ai = {};

App.ai.settingsModal = async function () {
  let s;
  try { s = await App.api('GET', 'ai/settings'); } catch (e) { return App.toast(e.message, 'err'); }
  const provOpts = Object.entries(s.providers).map(([k, v]) => `<label class="chk" style="display:flex;margin:6px 0"><input type="radio" name="prov" value="${k}" ${s.provider === k ? 'checked' : ''}> ${esc(v)}</label>`).join('');
  const body = `
    <div class="notice n-info">AI 보조 기능은 <b>선택 기능</b>입니다. 꺼져 있어도 학생 관리·자동 편성·수동 조정·저장·엑셀 출력은 모두 그대로 작동합니다.
    AI는 요청 해석·조건 제안·결과 설명·수정 조건 변환만 돕고, 실제 배정은 편성 프로그램이 필수 조건을 검증하여 계산합니다.</div>
    <label class="chk"><input type="checkbox" id="aiEnabled" ${s.enabled ? 'checked' : ''}> <b>AI 보조 기능 사용</b> (기본값: 꺼짐)</label>
    <h3>연결 방식</h3>${provOpts}
    <div class="field"><span>사용 모델 이름</span><input type="text" id="aiModel" value="${esc(s.model || '')}" placeholder="비워 두면 기본값 사용"></div>
    <div class="field" id="aiEpWrap"><span>서버 주소 (OpenAI 호환 서버)</span><input type="text" id="aiEndpoint" value="${esc(s.endpoint || '')}" placeholder="예: http://127.0.0.1:11434/v1"></div>
    <div class="field" id="aiKeyWrap"><span>API 키 ${s.has_key ? '<span class="badge b-ok">✔ 이 PC에 저장된 키 있음</span>' : '<span class="badge b-gray">저장된 키 없음</span>'}</span>
      <input type="password" id="aiKey" autocomplete="off" placeholder="새 키를 입력할 때만 채우세요 (저장 후 화면에 다시 표시되지 않음)">
      <span class="small muted">키는 이 PC의 data 폴더(${esc(s.key_location)})에만 저장되며, 브라우저 화면·프로젝트 파일·백업 파일에는 포함되지 않습니다.</span>
      ${s.has_key ? '<label class="chk"><input type="checkbox" id="aiClearKey"> 저장된 키 삭제</label>' : ''}</div>
    <div id="aiAnth" class="notice n-warn ${s.anthropic_installed ? 'hidden' : ''}">Anthropic 연결 구성요소가 아직 설치되지 않았습니다. 사용하려면 프로그램 폴더의 <b>AI구성요소_설치.bat</b>을 한 번 실행하세요.</div>
    <h3>외부 전송</h3>
    <div class="notice n-warn">외부 AI 서비스를 사용하면 <b>별도의 이용 비용</b>이 발생할 수 있습니다. 학생 자료를 외부로 보낼지는 <b>학교의 개인정보 처리 기준</b>에 따라 결정하세요.
    프로그램은 이름 대신 임시 ID와 학급별 집계 위주로 보내지만, 특성 조합으로 학생을 알아볼 가능성이 있어 완전한 익명 정보라고 단정할 수 없습니다.</div>
    <label class="chk"><input type="checkbox" id="aiExt" ${s.allow_external ? 'checked' : ''}> 외부 AI로 자료 전송 허용 (매번 전송 전에 보낼 내용을 확인합니다)</label>`;
  const m = App.modal({
    title: '🤖 AI 연결 설정', body, wide: true,
    buttons: [{ label: '취소' }, {
      label: '저장', cls: 'btn-pri', onClick: async (el) => {
        const d = {
          enabled: el.querySelector('#aiEnabled').checked, provider: el.querySelector('input[name=prov]:checked').value,
          model: el.querySelector('#aiModel').value.trim(), endpoint: el.querySelector('#aiEndpoint').value.trim(),
          allow_external: el.querySelector('#aiExt').checked,
        };
        const k = el.querySelector('#aiKey').value.trim(); if (k) d.api_key = k;
        const ck = el.querySelector('#aiClearKey'); if (ck && ck.checked) d.clear_key = true;
        try { await App.api('POST', 'ai/settings', d); App.toast('AI 연결 설정을 저장했습니다.', 'ok'); App.state.info.ai.enabled = d.enabled; } catch (e) { App.toast(e.message, 'err'); return false; }
        return true;
      },
    }],
  });
  const upd = () => {
    const pv = m.el.querySelector('input[name=prov]:checked').value;
    m.el.querySelector('#aiEpWrap').classList.toggle('hidden', pv !== 'openai_compat');
    m.el.querySelector('#aiKeyWrap').classList.toggle('hidden', pv === 'builtin');
    m.el.querySelector('#aiAnth').classList.toggle('hidden', pv !== 'anthropic' || s.anthropic_installed);
    m.el.querySelector('#aiModel').placeholder = '비워 두면 기본값: ' + s.default_models[pv];
  };
  m.el.querySelectorAll('input[name=prov]').forEach((r) => { r.onchange = upd; }); upd();
};

/* task: settings | explain | fix | memo_tags.  전송 전 실제 내용을 보여주고 교사가 승인해야 보낸다. */
App.ai.run = async function (task, args, onResult) {
  let prep;
  try { prep = await App.api('POST', 'ai/prepare', { task, project: App.state.project, args }); } catch (e) {
    App.modal({ title: 'AI 보조 기능', body: `<div class="notice n-warn">${esc(e.message)}</div>`, buttons: [{ label: '닫기' }, { label: 'AI 연결 설정 열기', cls: 'btn-pri', onClick: () => App.ai.settingsModal() }] });
    return;
  }
  const blocked = prep.external && !prep.allow_external;
  const body = `
    <div class="kv"><b>처리 위치</b><span>${esc(prep.destination)} ${prep.external ? '<span class="badge b-warn">⚠ 외부 전송</span>' : '<span class="badge b-ok">✔ 외부 전송 없음</span>'}</span>
    <b>연결 방식</b><span>${esc(prep.provider_label)}</span><b>모델</b><span>${esc(prep.model)}</span></div>
    <div class="notice ${prep.external ? 'n-warn' : 'n-info'}">${esc(prep.notice)}</div>
    <div class="grid2"><div><b>✔ 포함되는 항목</b><ul>${prep.included.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div>
    <div><b>✖ 포함되지 않는 항목</b><ul>${prep.excluded.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div></div>
    <details ${prep.external ? 'open' : ''}><summary>실제로 보낼 내용 전체 보기 (이 내용 그대로 전송됩니다)</summary>
    <p class="small muted">지시문</p><pre class="payload">${esc(prep.system_text)}</pre><p class="small muted">자료</p><pre class="payload">${esc(prep.payload_text)}</pre></details>
    ${blocked ? '<div class="notice n-bad">외부 전송이 허용되어 있지 않아 보낼 수 없습니다. ‘AI 연결 설정’에서 교사가 직접 허용해야 합니다.</div>' : ''}`;
  App.modal({
    title: '전송 내용 확인', body, wide: true,
    buttons: [{ label: '취소' }, {
      label: prep.external ? '확인했습니다 — 전송' : '확인 — 실행', cls: 'btn-pri', disabled: blocked, onClick: async (el) => {
        const btn = el.querySelector('.btn-pri'); btn.disabled = true; btn.textContent = '처리 중…';
        try {
          const res = await App.api('POST', 'ai/send', { token: prep.token });
          onResult(res);
        } catch (e) { App.modal({ title: 'AI 처리 실패', body: `<div class="notice n-bad">${esc(e.message)}</div><p>기본 편성 작업과 저장된 자료는 그대로 유지됩니다.</p>` }); }
        return true;
      },
    }],
  });
};
App.ai.errorsHtml = (res) => `<div class="notice n-bad"><b>✖ AI 응답 검증 실패 — 아무것도 변경하지 않았습니다.</b><ul>${(res.errors || []).map((e) => `<li>${esc(e)}</li>`).join('')}</ul></div>
  ${res.raw ? `<details><summary>AI 원본 응답 보기</summary><pre class="payload">${esc(res.raw)}</pre></details>` : ''}`;
