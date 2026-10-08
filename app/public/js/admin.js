// Admin panel: users (an account page per user and a form for new credentials), requests, channels.
import { api, copy, errorText, esc, fmtDate, fmtWhen, haptic, icon, openSheet, segHTML, setBack, t, tg, toast } from './lib.js';

const ROLES = ['analyst', 'economist', 'admin'];
const TERMS = ['30', '90', '0'];
const STATES = ['active', 'pending', 'expired', 'blocked'];
const TERM_DAYS = { 30: 30, 90: 90, 0: null };
// the server (_auth.py) enforces the same rules; these only explain them while the admin types
const LOGIN_RE = /^[a-z][a-z0-9._-]{2,31}$/;
const RESERVED = ['admin'];
const PW_RULES = ['length', 'mix', 'space', 'login'];

export function passwordProblems(pw, login) {
  const out = [];
  if (pw.length < 8 || pw.length > 64) out.push('length');
  if (!(/\p{L}/u.test(pw) && /\d/.test(pw))) out.push('mix');
  if (/\s/.test(pw)) out.push('space');
  if (login && pw.toLowerCase().includes(login.toLowerCase())) out.push('login');
  return out;
}

const initials = (login) => {
  const [prefix, num] = String(login).split('.');
  return (prefix === 'admin' ? 'AD' : prefix.charAt(0).toUpperCase()) + (num && /^\d+$/.test(num) ? String(parseInt(num, 10)) : '');
};

export function renderAdmin(root, nav, state, opts = {}) {
  let data = null, error = '', busy = false;
  let view = opts.view || 'users';    // tab: users | requests | channels
  let page = null;                    // {type: 'create' | 'account' | 'creds', ...} over the tabs
  let lastKey = '';                   // the page animates in when it changes, not on every refresh
  let chanInput = '';
  // credential form: kept outside the markup so a re-render does not lose what was typed
  let form = null;
  let loginCheck = { value: '', status: '' }, checkSeq = 0, checkTimer = null;

  const back = () => {
    haptic();
    if (page) { page = null; form = null; draw(); window.scrollTo(0, 0); } else nav.go('dashboard');
  };
  setBack(back);

  async function load() {
    let r = null;
    try { r = await api('admin'); } catch (e) { r = null; }
    if (r && r.ok) { data = r; error = ''; } else { error = errorText(r); }
    if (page && page.type === 'account' && data && !account(page.id)) page = null;
    draw();
  }
  async function act(action, body) {
    haptic();
    let r = null;
    try { r = await api(action, body); } catch (e) { r = null; }
    if (!r || !r.ok) { haptic('error'); toast(errorText(r)); return null; }
    return r;
  }
  const account = (id) => ((data && data.accounts) || []).find((a) => String(a.id) === String(id));
  const findReq = (id) => ((data && data.requests) || []).find((r) => String(r.id) === String(id));

  // ------------------------------------------------------------ pieces ----
  const credsHTML = (c) => `
    <div class="creds" role="status">
      <div class="ok">${icon('check', 16, 2.2)}${esc(c.title)}</div>
      <div class="secret"><div><small>Login</small><span class="mono">${esc(c.login)}</span></div>
        <button class="icon-btn" data-copy="${esc(c.login)}" aria-label="${esc(t('admin.copyLogin'))}">${icon('copy', 16)}</button></div>
      <div class="secret"><div><small>${esc(t('auth.password'))}</small><span class="mono">${esc(c.password)}</span></div>
        <button class="icon-btn" data-copy="${esc(c.password)}" aria-label="${esc(t('admin.copyPassword'))}">${icon('copy', 16)}</button></div>
      ${c.delivered === true ? `<p class="note">${esc(t('admin.delivered'))}</p>` : ''}
      ${c.delivered === false ? `<p class="note">${esc(t('admin.notDelivered'))}</p>` : ''}
      <p class="note">${esc(c.note || t('admin.once'))}</p>
    </div>`;
  const topbar = (title, mono = false, extra = '') => `
    <header class="topbar">
      <button class="icon-btn" id="back" aria-label="${esc(t('back'))}">${icon('back', 18, 2)}</button>
      <h1${mono ? ' class="mono"' : ''}>${esc(title)}</h1>${extra}
    </header>`;
  const userMeta = (a) =>
    t('roles.' + a.role) + ' · ' + (a.expires_at ? t('admin.until', { d: fmtDate(a.expires_at) }) : t('admin.noExpiry'));
  const requester = (r) => [r.organization,
    r.tg_username ? '@' + r.tg_username : (r.tg_name !== r.full_name ? r.tg_name : '')].filter(Boolean).join(' · ');
  const statePill = (s) => `<span class="pill ${s}"><span class="dot"></span>${esc(t('admin.stats.' + s))}</span>`;

  // a login and a password the admin may type, with live checks
  const pwField = (label) => `
    <div class="field">
      <div class="label-row"><span class="label">${esc(label)}</span>
        <div class="seg compact" role="group">${segHTML([['auto', t('admin.auto')], ['manual', t('admin.manual')]], form.pwMode, 'pwmode')}</div></div>
      ${form.pwMode === 'auto' ? `<div class="readonly">${icon('lock', 18)}<span>${esc(t('admin.pwAuto'))}</span></div>` : `
      <div class="input-wrap">${icon('lock', 18)}
        <input id="pw" class="mono" type="${form.showPw ? 'text' : 'password'}" autocomplete="new-password" autocapitalize="none"
               autocorrect="off" spellcheck="false" maxlength="64" placeholder="${esc(t('admin.pwPh'))}">
        <button type="button" class="icon-btn ghost" id="eye" aria-label="${esc(t(form.showPw ? 'auth.hidePw' : 'auth.showPw'))}">${icon(form.showPw ? 'eyeOff' : 'eye', 18)}</button></div>
      <p class="hint" id="pwHint" aria-live="polite"></p>
      <ul class="rules" id="pwRules">${PW_RULES.map((k) => `<li data-rule="${k}">${icon('check', 14, 2.2)}<span>${esc(t('admin.rules.' + k))}</span></li>`).join('')}</ul>`}
    </div>`;
  const loginField = () => `
    <div class="field">
      <div class="label-row"><span class="label">Login</span>
        <div class="seg compact" role="group">${segHTML([['auto', t('admin.auto')], ['manual', t('admin.manual')]], form.loginMode, 'loginmode')}</div></div>
      ${form.loginMode === 'auto'
        ? `<div class="readonly">${icon('user', 18)}<span class="mono">${esc((data.next_login || {})[form.role] || '')}</span></div>`
        : `<div class="input-wrap">${icon('user', 18)}
            <input id="login" class="mono" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false"
                   maxlength="32" placeholder="${esc(t('admin.loginPh'))}" value="${esc(form.login)}"></div>
          <p class="hint" id="loginHint" aria-live="polite"></p>`}
    </div>`;

  // ------------------------------------------------------------- views ----
  function draw() {
    const key = page ? `${page.type}:${page.id || ''}:${page.action || ''}` : view;
    const fx = data && key !== lastKey ? ' fade' : '';
    if (data) lastKey = key;
    if (!data) {
      root.innerHTML = `<main class="screen">${topbar(t('admin.title'))}
        ${error ? `<p class="form-error" role="alert">${esc(error)}</p><button class="btn primary" id="reload">${esc(t('retry'))}</button>`
                : '<div class="boot"><span class="spinner"></span></div>'}</main>`;
      return bind();
    }
    const pw = root.querySelector('#pw');
    if (pw && form) form.pw = pw.value;                   // the password lives only in the DOM and here
    let body;
    if (page && page.type === 'create') body = createHTML();
    else if (page && page.type === 'account') body = accountHTML();
    else if (page && page.type === 'creds') body = `${topbar(page.title)}${credsHTML(page.creds)}
      <button class="btn primary" id="doneBtn" style="margin-top:12px">${esc(t('admin.doneBtn'))}</button>`;
    else body = tabsHTML();
    root.innerHTML = `<main class="screen${fx}">${body}</main>`;
    bind();
    if (fx) window.scrollTo(0, 0);
  }

  function tabsHTML() {
    const reqs = data.requests || [];
    const tabs = [['users', t('admin.tabUsers')], ['requests', t('admin.tabRequests')], ['channels', t('admin.tabChannels')]];
    return `${topbar(t('admin.title'))}
      ${error ? `<p class="form-error" role="alert">${esc(error)}</p>` : ''}
      <div class="seg admin-tabs" role="group">${tabs.map(([id, label]) => `
        <button type="button" data-view="${id}" aria-pressed="${id === view}">${esc(label)}${
          id === 'requests' && reqs.length ? `<span class="count">${reqs.length}</span>` : ''}</button>`).join('')}</div>
      ${view === 'users' ? usersHTML() : view === 'requests' ? requestsHTML() : channelsHTML()}`;
  }

  function usersHTML() {
    const c = data.count || {}, accounts = data.accounts || [];
    return `
      <div class="stats">${STATES.map((s) => `<div class="stat"><span>${esc(t('admin.stats.' + s))}</span><b>${c[s] || 0}</b></div>`).join('')}</div>
      <button class="btn primary" id="newUser">${icon('plus', 18, 2)}${esc(t('admin.newUser'))}</button>
      <section class="card users" aria-label="${esc(t('admin.list'))}">
        ${accounts.length ? accounts.map((a) => `
          <button type="button" class="user" data-acc="${a.id}">
            <span class="avatar">${esc(initials(a.login))}</span>
            <span class="who">
              <span class="line1"><span class="mono">${esc(a.login)}</span>${statePill(a.state)}</span>
              ${a.full_name || a.tg_username ? `<span class="line2">${esc(a.full_name || '@' + a.tg_username)}</span>` : ''}
              <span class="line2">${esc(userMeta(a))}</span>
            </span>
            <span class="chev">${icon('chevronRight', 18)}</span>
          </button>`).join('') : `<p class="empty">${esc(t('admin.empty'))}</p>`}
      </section>`;
  }

  function requestsHTML() {
    const reqs = data.requests || [], handled = data.handled || [];
    const main = (r) => {
      if (r.reason === 'reset' && r.account) return `<button class="btn primary small" data-reset-req="${r.id}">${esc(t('admin.reset'))}</button>`;
      if (r.account && r.reason !== 'access') return `<button class="btn primary small" data-open-acc="${r.account.id}">${esc(t('admin.openAccount'))}</button>`;
      return `<button class="btn primary small" data-approve="${r.id}">${esc(t('admin.approve'))}</button>`;
    };
    return `
      <section class="card stack" aria-label="${esc(t('admin.tabRequests'))}">
        ${reqs.length ? `<div>${reqs.map((r) => `
          <div class="req">
            <div class="top"><span class="who">${esc(r.full_name)}</span><span class="pill">${esc(fmtWhen(r.created_at))}</span></div>
            ${requester(r) ? `<span class="meta">${esc(requester(r))}</span>` : ''}
            <span class="tags"><span class="pill">${esc(t('contact.reasons.' + r.reason))}</span>
              ${r.account ? `<span class="pill ${r.account.state}"><span class="mono">${esc(r.account.login)}</span> · ${esc(t('admin.stats.' + r.account.state))}</span>` : ''}</span>
            ${r.message ? `<span class="msg">${esc(r.message)}</span>` : ''}
            <div class="actions">
              <button class="btn secondary small" data-close-req="${r.id}">${esc(t('close'))}</button>${main(r)}
            </div>
            ${r.tg_username ? `<button type="button" class="link write" data-write="${esc(r.tg_username)}">${icon('send', 15)}${esc(t('admin.write'))}</button>` : ''}
          </div>`).join('')}</div>` : `<p class="empty">${esc(t('admin.requestsEmpty'))}</p>`}
      </section>
      ${handled.length ? `
      <section class="card" aria-label="${esc(t('admin.handled'))}">
        <h2>${esc(t('admin.handled'))}</h2>
        <div class="hist">${handled.map((r) => `
          <div class="hrow">
            <span class="who"><b>${esc(r.full_name)}</b><small>${esc([t('contact.reasons.' + r.reason), fmtWhen(r.handled_at || r.created_at)].join(' · '))}</small></span>
            <span class="pill ${r.status === 'rejected' ? 'blocked' : 'active'}">${esc(t(r.status === 'rejected' ? 'admin.statusRejected' : 'admin.statusDone'))}</span>
          </div>`).join('')}</div>
      </section>` : ''}`;
  }

  function channelsHTML() {
    const list = data.channels || [];
    return `
      <section class="card stack" aria-label="${esc(t('admin.chanAdd'))}">
        <div class="card-head"><span class="tile">${icon('send', 18)}</span>
          <div><h2>${esc(t('admin.chanAdd'))}</h2><p class="sub">${esc(t('admin.chanSub'))}</p></div></div>
        <form class="chan-add" id="chanForm" novalidate>
          <input id="chanInput" class="input mono" autocomplete="off" autocapitalize="none" spellcheck="false"
                 placeholder="${esc(t('admin.chanPh'))}" value="${esc(chanInput)}">
          <button class="btn primary" type="submit" ${busy ? 'disabled' : ''}>
            ${busy ? '<span class="spinner sm"></span>' : esc(t('admin.chanAddBtn'))}</button>
        </form>
      </section>
      <section class="card users" aria-label="${esc(t('admin.tabChannels'))}">
        ${list.map((c) => `
          <div class="user">
            <span class="avatar">${esc((c.title || c.handle.slice(1)).charAt(0).toUpperCase())}</span>
            <span class="who">
              <span class="line1"><b>${esc(c.title || c.handle)}</b>
                <span class="pill ${c.active ? 'active' : 'expired'}"><span class="dot"></span>${esc(t(c.active ? 'admin.chanActive' : 'admin.chanPaused'))}</span></span>
              <span class="line2 mono">${esc(c.handle)}</span>
              <span class="line2">${esc(t('admin.chanSince', { d: fmtDate(c.changed_at || c.added_at) }))}</span>
            </span>
            <button class="icon-btn ghost" data-chan="${esc(c.handle)}" aria-label="${esc(c.title || c.handle)}">${icon('more', 18)}</button>
          </div>`).join('')}
      </section>`;
  }

  function createHTML() {
    const rq = page.request;
    return `${topbar(t(rq ? 'admin.approve' : 'admin.newUser'))}
      ${rq ? `<div class="context"><span>${esc(t('admin.forRequest', { name: rq.full_name }))}</span></div>` : ''}
      <section class="card stack">
        <div class="field"><span class="label" id="roleLabel">${esc(t('admin.role'))}</span>
          <div class="seg" role="group" aria-labelledby="roleLabel">${segHTML(ROLES.map((r) => [r, t('roles.' + r)]), form.role, 'role')}</div></div>
        <div class="field"><span class="label" id="termLabel">${esc(t('admin.term'))}</span>
          <div class="seg" role="group" aria-labelledby="termLabel">${segHTML(TERMS.map((x) => [x, t('admin.terms.' + x)]), form.term, 'term')}</div></div>
      </section>
      <section class="card stack">${loginField()}${pwField(t('auth.password'))}</section>
      <button class="btn primary" id="submit" style="margin-top:12px" disabled>${esc(t('admin.createBtn'))}</button>`;
  }

  function accountHTML() {
    const a = account(page.id);
    const rows = [
      [t('admin.f.name'), a.full_name], [t('admin.f.org'), a.organization],
      ['Telegram', a.tg_username ? '@' + a.tg_username : a.tg_name],
      [t('admin.role'), t('roles.' + a.role)],
      [t('admin.f.valid'), a.expires_at ? t('admin.until', { d: fmtDate(a.expires_at) }) : t('admin.noExpiry')],
      [t('admin.f.seen'), a.last_seen_at ? fmtWhen(a.last_seen_at) : t('admin.notSignedIn')],
      [t('admin.f.created'), fmtDate(a.created_at)],
    ].filter(([, v]) => v);
    return `${topbar(a.login, true, statePill(a.state))}
      <section class="card"><dl class="kv">${rows.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl></section>
      ${page.creds ? `<section class="card stack">${credsHTML(page.creds)}
          <button class="btn secondary" id="credsDone">${esc(t('admin.doneBtn'))}</button></section>`
        : page.action ? actionHTML(a) : `
      <section class="card menu-card"><div class="menu">
        <button data-do="password"><span class="ic">${icon('key', 18)}</span>${esc(t('admin.changePw'))}</button>
        <button data-do="extend"><span class="ic">${icon('calendar', 18)}</span>${esc(t('admin.extend'))}</button>
        ${a.status === 'blocked'
          ? `<button data-do="unblock"><span class="ic">${icon('unlock', 18)}</span>${esc(t('admin.unblock'))}</button>`
          : `<button data-do="block" class="danger"><span class="ic">${icon('ban', 18)}</span>${esc(t('admin.block'))}</button>`}
        <button data-do="delete" class="danger"><span class="ic">${icon('trash', 18)}</span>${esc(t('admin.removeUser'))}</button>
      </div></section>`}`;
  }

  function actionHTML(a) {
    const buttons = (label, danger) => `
      <div class="pair">
        <button class="btn secondary" data-cancel>${esc(t('cancel'))}</button>
        <button class="btn primary${danger ? ' danger' : ''}" id="confirm" ${busy ? 'disabled' : ''}>
          ${busy ? '<span class="spinner sm"></span>' : esc(label)}</button>
      </div>`;
    if (page.action === 'password') {
      const rq = page.request;
      return `<section class="card stack">
        <h2>${esc(t(rq ? 'admin.reset' : 'admin.changePw'))}</h2>
        ${rq ? `<div class="context"><span>${esc(t('admin.forRequest', { name: rq.full_name }))}</span></div>` : ''}
        ${pwField(t('admin.newPassword'))}
        <p class="note">${esc(t('admin.resetNote'))}</p>
        ${buttons(t('admin.confirm'))}</section>`;
    }
    if (page.action === 'extend') {
      const days = TERM_DAYS[form.term];
      const base = Math.max(Date.now(), a.expires_at ? new Date(a.expires_at).getTime() : 0);
      const result = days == null ? t('admin.newForever') : t('admin.newUntil', { d: fmtDate(new Date(base + days * 864e5).toISOString()) });
      return `<section class="card stack">
        <h2>${esc(t('admin.extend'))}</h2>
        <div class="seg" role="group">${segHTML(TERMS.map((x) => [x, t('admin.terms.' + x)]), form.term, 'term')}</div>
        <p class="note">${esc(a.expires_at ? t('admin.nowUntil', { d: fmtDate(a.expires_at) }) : t('admin.nowForever'))}<br><b>${esc(result)}</b></p>
        ${buttons(t('admin.confirm'))}</section>`;
    }
    if (page.action === 'delete') {
      return `<section class="card stack">
        <h2>${esc(t('admin.removeUser'))}</h2>
        <p class="note">${esc(t('admin.removeUserNote'))}</p>
        ${buttons(t('admin.remove'), true)}</section>`;
    }
    const blocking = page.action === 'block';
    return `<section class="card stack">
      <h2>${esc(t(blocking ? 'admin.block' : 'admin.unblock'))}</h2>
      <p class="note">${esc(t(blocking ? 'admin.blockNote' : 'admin.unblockNote'))}</p>
      ${buttons(t(blocking ? 'admin.block' : 'admin.unblock'), blocking)}</section>`;
  }

  // ------------------------------------------------------- live checks ----
  const formLogin = () => (form.loginMode === 'manual' ? form.login : ((data.next_login || {})[form.role] || ''));

  function checkPassword() {
    const rules = root.querySelector('#pwRules');
    if (!rules) return true;
    const pw = root.querySelector('#pw').value;
    const login = page.type === 'account' ? account(page.id).login : formLogin();
    const bad = passwordProblems(pw, login);
    rules.querySelectorAll('li').forEach((li) => {
      const ok = pw && !bad.includes(li.dataset.rule);
      li.className = pw ? (ok ? 'ok' : 'bad') : '';
      li.querySelector('svg').outerHTML = icon(pw && !ok ? 'close' : 'check', 14, 2.2);
    });
    const hint = root.querySelector('#pwHint');
    hint.className = 'hint' + (pw ? (bad.length ? ' bad' : ' ok') : '');
    hint.textContent = pw ? t(bad.length ? 'admin.pwInvalid' : 'admin.pwValid') : '';
    return !!pw && !bad.length;
  }

  function showLogin() {
    const hint = root.querySelector('#loginHint');
    if (!hint) return true;
    const v = form.login;
    let cls = '', text = '';
    if (!v) { /* nothing typed yet */ }
    else if (!LOGIN_RE.test(v)) { cls = 'bad'; text = t('admin.loginBad'); }
    else if (RESERVED.includes(v)) { cls = 'bad'; text = t('admin.loginTaken'); }
    else if (loginCheck.value !== v || !loginCheck.status) { text = t('admin.checking'); }
    else if (loginCheck.status === 'free') { cls = 'ok'; text = t('admin.loginFree'); }
    else { cls = 'bad'; text = t(loginCheck.status === 'taken' ? 'admin.loginTaken' : 'admin.loginBad'); }
    hint.className = 'hint' + (cls ? ' ' + cls : '');
    hint.innerHTML = text ? `${cls ? icon(cls === 'ok' ? 'check' : 'close', 14, 2.2) : '<span class="spinner xs"></span>'}<span>${esc(text)}</span>` : '';
    return cls === 'ok';
  }

  function checkLogin() {
    const v = form.login;
    clearTimeout(checkTimer);
    if (!v || !LOGIN_RE.test(v) || RESERVED.includes(v) || loginCheck.value === v) return;
    loginCheck = { value: v, status: '' };
    const seq = ++checkSeq;
    checkTimer = setTimeout(async () => {
      let r = null;
      try { r = await api('check_login', { login: v }); } catch (e) { r = null; }
      if (seq !== checkSeq) return;                       // a newer value is being checked
      loginCheck = { value: v, status: r && r.ok ? r.state : '' };
      if (!loginCheck.status) loginCheck.value = '';      // network trouble: check again on the next key
      showLogin(); refreshSubmit();
    }, 350);
  }

  function refreshSubmit() {
    const btn = root.querySelector('#submit');
    if (btn) {
      const loginOk = form.loginMode === 'auto' || showLogin();
      const pwOk = form.pwMode === 'auto' || checkPassword();
      btn.disabled = busy || !loginOk || !pwOk;
    }
    const conf = root.querySelector('#confirm');
    if (conf && page && page.action === 'password') conf.disabled = busy || (form.pwMode === 'manual' && !checkPassword());
  }

  // -------------------------------------------------------------- open ----
  function openCreate(request) {
    form = { role: 'analyst', term: '30', loginMode: 'auto', pwMode: 'auto', login: '', pw: '', showPw: false };
    page = { type: 'create', request: request || null };
    draw();
  }
  function openAccount(id, action, request) {
    page = { type: 'account', id, action: action || null, request: request || null };
    form = { term: '30', pwMode: 'auto', pw: '', showPw: false };
    draw();
  }
  function closeRequest(rq) {
    const close = openSheet(document.body, rq.full_name, `
      <div class="menu">
        <button data-finish="close"><span class="ic">${icon('check', 18)}</span>
          <span>${esc(t('admin.markDone'))}<small>${esc(t('admin.markDoneNote'))}</small></span></button>
        <button data-finish="reject" class="danger"><span class="ic">${icon('ban', 18)}</span>
          <span>${esc(t('admin.reject'))}<small>${esc(t('admin.rejectNote'))}</small></span></button>
      </div>`, (body) => {
      body.querySelectorAll('[data-finish]').forEach((b) => b.addEventListener('click', async () => {
        if (b.disabled) return;
        body.querySelectorAll('button').forEach((x) => { x.disabled = true; });
        if (await act(b.dataset.finish, { request_id: rq.id })) { close(); setBack(back); toast(t('admin.done')); load(); }
        else body.querySelectorAll('button').forEach((x) => { x.disabled = false; });
      }));
    });
  }
  /** A channel's actions: pause or switch back on, delete; pausing and deleting ask first. */
  function channelSheet(c) {
    const menu = `<div class="menu">
        ${c.active
          ? `<button data-step="pause"><span class="ic">${icon('pause', 18)}</span>${esc(t('admin.pause'))}</button>`
          : `<button data-step="resume"><span class="ic">${icon('play', 18)}</span>${esc(t('admin.resume'))}</button>`}
        <button data-step="delete" class="danger"><span class="ic">${icon('trash', 18)}</span>${esc(t('admin.removeChannel'))}</button>
      </div>`;
    const confirm = (note, label) => `
      <p class="note">${esc(note)}</p>
      <div class="pair">
        <button class="btn secondary" data-step="menu">${esc(t('cancel'))}</button>
        <button class="btn primary danger" data-ok>${esc(label)}</button>
      </div>`;
    let close = null;
    const run = async (action, button) => {
      button.disabled = true;
      if (await act(action, { handle: c.handle })) {
        close(); setBack(back); toast(t(action === 'channel_delete' ? 'admin.removed' : 'admin.done')); load();
      } else button.disabled = false;
    };
    const mount = (body, _close, fill) => {
      body.querySelectorAll('[data-step]').forEach((b) => b.addEventListener('click', () => {
        haptic();
        const step = b.dataset.step;
        if (step === 'menu') return fill(menu);
        if (step === 'resume') return run('channel_resume', b);
        fill(step === 'pause' ? confirm(t('admin.pauseNote'), t('admin.pause'))
          : confirm(t('admin.removeChannelNote'), t('admin.remove')));
        body.querySelector('[data-ok]').addEventListener('click', (e) =>
          run(step === 'pause' ? 'channel_pause' : 'channel_delete', e.currentTarget));
      }));
    };
    close = openSheet(document.body, c.title || c.handle, menu, mount);
  }

  // -------------------------------------------------------------- bind ----
  function bind() {
    const $ = (s) => root.querySelector(s);
    const on = (sel, fn) => root.querySelectorAll(sel).forEach((el) => el.addEventListener('click', (e) => fn(el, e)));
    if ($('#back')) $('#back').addEventListener('click', back);
    if ($('#reload')) $('#reload').addEventListener('click', () => { haptic(); error = ''; draw(); load(); });
    on('[data-view]', (el) => { haptic(); view = el.dataset.view; draw(); });
    on('[data-copy]', (el) => copy(el.dataset.copy));
    if ($('#newUser')) $('#newUser').addEventListener('click', () => { haptic(); openCreate(null); });
    on('[data-acc]', (el) => { haptic(); openAccount(el.dataset.acc); });
    on('[data-open-acc]', (el) => { haptic(); openAccount(el.dataset.openAcc); });
    on('[data-approve]', (el) => { haptic(); openCreate(findReq(el.dataset.approve)); });
    on('[data-reset-req]', (el) => {
      const rq = findReq(el.dataset.resetReq);
      haptic(); openAccount(rq.account.id, 'password', rq);
    });
    on('[data-close-req]', (el) => { haptic(); closeRequest(findReq(el.dataset.closeReq)); });
    on('[data-write]', (el) => {
      haptic();
      const url = 'https://t.me/' + el.dataset.write;
      try { tg.openTelegramLink(url); } catch (e) { window.open(url, '_blank'); }
    });
    if ($('#doneBtn')) $('#doneBtn').addEventListener('click', () => { const b = page.back; page = null; form = null; view = b || view; draw(); });

    // channels
    if ($('#chanForm')) $('#chanForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      chanInput = $('#chanInput').value.trim();
      if (!chanInput) return;
      busy = true; draw();
      const r = await act('channel_add', { handle: chanInput });
      busy = false;
      if (r) { haptic('success'); chanInput = ''; toast(t('admin.chanAdded')); await load(); } else draw();
    });
    on('[data-chan]', (el) => {
      haptic();
      channelSheet((data.channels || []).find((x) => x.handle === el.dataset.chan));
    });

    // credential form (new user) and account actions share the segmented choices
    on('[data-role]', (el) => { haptic(); form.role = el.dataset.role; draw(); });
    on('[data-term]', (el) => { haptic(); form.term = el.dataset.term; draw(); });
    on('[data-loginmode]', (el) => { haptic(); form.loginMode = el.dataset.loginmode; draw(); });
    on('[data-pwmode]', (el) => { haptic(); form.pwMode = el.dataset.pwmode; form.pw = ''; draw(); });
    const pw = $('#pw');
    if (pw) {
      pw.value = form.pw || '';
      pw.addEventListener('input', () => { form.pw = pw.value; refreshSubmit(); });
      $('#eye').addEventListener('click', (e) => {
        form.showPw = !form.showPw;                      // in place: a re-render would clear the password
        pw.type = form.showPw ? 'text' : 'password';
        e.currentTarget.innerHTML = icon(form.showPw ? 'eyeOff' : 'eye', 18);
        e.currentTarget.setAttribute('aria-label', t(form.showPw ? 'auth.hidePw' : 'auth.showPw'));
        pw.focus();
      });
    }
    const login = $('#login');
    if (login) login.addEventListener('input', () => {
      const v = login.value.trim().toLowerCase();
      if (v !== login.value) { const at = login.selectionStart; login.value = v; login.setSelectionRange(at, at); }
      form.login = v;
      checkLogin(); refreshSubmit();
    });
    if (page && form) { if (form.loginMode === 'manual') checkLogin(); refreshSubmit(); }

    if ($('#submit')) $('#submit').addEventListener('click', async () => {
      const body = { role: form.role, term: form.term, request_id: page.request ? page.request.id : null };
      if (form.loginMode === 'manual') body.login = form.login;
      if (form.pwMode === 'manual') body.password = $('#pw').value;
      busy = true; refreshSubmit();
      const r = await act('create', body);
      busy = false;
      if (!r) {
        if (form.loginMode === 'manual') { loginCheck = { value: '', status: '' }; checkLogin(); }
        return refreshSubmit();
      }
      haptic('success');
      const fromRequest = !!page.request;
      page = { type: 'creds', title: t(fromRequest ? 'admin.approve' : 'admin.newUser'), back: fromRequest ? 'requests' : 'users',
               creds: { title: t('admin.ready'), login: r.account.login, password: r.password,
                        delivered: fromRequest ? r.delivered : undefined } };
      form = null;
      draw(); load();
    });

    // account page
    on('[data-do]', (el) => { haptic(); page.action = el.dataset.do; form = { term: '30', pwMode: 'auto', pw: '', showPw: false }; draw(); });
    on('[data-cancel]', () => {
      haptic();
      if (page.request) { page = null; view = 'requests'; } else page.action = null;
      draw();
    });
    if ($('#credsDone')) $('#credsDone').addEventListener('click', () => {
      haptic();
      if (page.request) { page = null; view = 'requests'; } else { page.creds = null; page.action = null; }
      draw();
    });
    if ($('#confirm')) $('#confirm').addEventListener('click', async () => {
      const a = account(page.id), what = page.action;
      let body = { id: a.id };
      if (what === 'password') {
        body = page.request ? { request_id: page.request.id } : { id: a.id };
        if (form.pwMode === 'manual') body.password = $('#pw').value;
      } else if (what === 'extend') body.term = form.term;
      busy = true; draw();
      const r = await act(what === 'password' ? 'reset' : what, body);
      busy = false;
      if (!r) return draw();
      haptic('success');
      if (what === 'delete') { page = null; form = null; toast(t('admin.removed')); draw(); return load(); }
      if (what === 'password') {
        page.creds = { title: t('admin.newPassword'), login: r.account.login, password: r.password,
                       delivered: page.request ? r.delivered : undefined, note: t('admin.resetNote') };
      } else { page.action = null; toast(t('admin.done')); }
      draw(); load();
    });
  }

  draw();
  load();
}
