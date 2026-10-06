// Admin panel: access requests, new credentials, user list and per-user actions.
import { api, copy, errorText, esc, fmtDate, fmtWhen, haptic, icon, segHTML, setBack, t, toast } from './lib.js';

const ROLES = ['analyst', 'economist', 'admin'];
const TERMS = ['30', '90', '0'];
const STATES = ['active', 'pending', 'expired', 'blocked'];

const initials = (login) => {
  const [prefix, num] = String(login).split('.');
  return (prefix === 'admin' ? 'AD' : prefix.charAt(0).toUpperCase()) + (num ? String(parseInt(num, 10)) : '');
};

export function renderAdmin(root, nav) {
  setBack(() => nav.go('dashboard'));
  let data = null, error = '', busy = false, shown = false;
  let form = { role: 'analyst', term: '30', request: null };
  let creds = null;          // {title, login, password, delivered}
  let sheet = null;          // {account, mode: 'menu' | 'extend' | 'creds'}

  async function load() {
    let r = null;
    try { r = await api('admin'); } catch (e) { r = null; }
    if (r && r.ok) { data = r; error = ''; } else { error = errorText(r); }
    draw();
  }
  async function act(action, body) {
    haptic();
    let r = null;
    try { r = await api(action, body); } catch (e) { r = null; }
    if (!r || !r.ok) { haptic('error'); toast(errorText(r)); return null; }
    return r;
  }

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

  const userMeta = (a) =>
    t('roles.' + a.role) + ' · ' + (a.expires_at ? t('admin.until', { d: fmtDate(a.expires_at) }) : t('admin.noExpiry'));
  const userDetails = (a) => [
    [a.full_name, a.organization].filter(Boolean).join(' · '),
    [a.tg_username ? '@' + a.tg_username : a.tg_name,
     a.last_seen_at ? t('admin.lastSeen', { t: fmtWhen(a.last_seen_at) }) : t('admin.notSignedIn')].filter(Boolean).join(' · '),
  ].filter(Boolean);
  const requester = (r) => [r.organization,
    r.tg_username ? '@' + r.tg_username : (r.tg_name !== r.full_name ? r.tg_name : '')].filter(Boolean).join(' · ');

  function draw() {
    if (!data && !error) {
      root.innerHTML = `<main class="screen"><div class="boot"><span class="spinner"></span></div></main>`;
      return;
    }
    const c = (data && data.count) || {};
    const reqs = (data && data.requests) || [];
    const accounts = (data && data.accounts) || [];
    const fx = data && !shown ? ' fade' : '';   // animate the first view only, not every re-render
    if (data) shown = true;
    root.innerHTML = `
    <main class="screen${fx}">
      <header class="topbar">
        <button class="icon-btn" id="back" aria-label="${esc(t('back'))}">${icon('back', 18, 2)}</button>
        <h1>${esc(t('admin.title'))}</h1>
        <span class="badge">${icon('shield', 13, 2)}${esc(t('admin.badge'))}</span>
      </header>
      ${error ? `<p class="form-error" role="alert">${esc(error)}</p>` : ''}
      ${data ? `
      <div class="stats">${STATES.map((s) => `<div class="stat"><span>${esc(t('admin.stats.' + s))}</span><b>${c[s] || 0}</b></div>`).join('')}</div>

      ${reqs.length ? `
      <section class="card stack" aria-label="${esc(t('admin.requests'))}">
        <div class="card-head"><h2>${esc(t('admin.requests'))}</h2>
          <span class="pill pending" style="margin-left:auto">${esc(t('admin.newN', { n: reqs.length }))}</span></div>
        <div>${reqs.map((r) => `
          <div class="req">
            <div class="top"><span class="who">${esc(r.full_name)}</span><span class="pill">${esc(fmtWhen(r.created_at))}</span></div>
            <span class="meta">${esc(requester(r))}</span>
            <span class="tags"><span class="pill">${esc(t('contact.reasons.' + r.reason))}</span>
              ${r.account ? `<span class="pill ${r.account.state}"><span class="mono">${esc(r.account.login)}</span> · ${esc(t('admin.stats.' + r.account.state))}</span>` : ''}</span>
            ${r.message ? `<span class="msg">${esc(r.message)}</span>` : ''}
            <div class="actions">
              <button class="btn secondary small" data-close-req="${r.id}">${esc(t('close'))}</button>
              ${r.reason === 'reset' && r.account
                ? `<button class="btn primary small" data-reset-req="${r.id}">${esc(t('admin.reset'))}</button>`
                : `<button class="btn primary small" data-approve="${r.id}">${esc(t('admin.approve'))}</button>`}
            </div>
          </div>`).join('')}</div>
      </section>` : ''}

      <section class="card stack" id="create" aria-label="${esc(t('admin.create'))}">
        <div class="card-head"><span class="tile">${icon('key', 18)}</span>
          <div><h2>${esc(t('admin.create'))}</h2><p class="sub">${esc(t('admin.createSub'))}</p></div></div>
        ${form.request ? `<div class="context"><span>${esc(t('admin.forRequest', { name: form.request.full_name }))}</span>
          <button class="icon-btn ghost" id="unlink" aria-label="${esc(t('cancel'))}">${icon('close', 16, 2)}</button></div>` : ''}
        <div class="field"><span class="label" id="roleLabel">${esc(t('admin.role'))}</span>
          <div class="seg" role="group" aria-labelledby="roleLabel">${segHTML(ROLES.map((r) => [r, t('roles.' + r)]), form.role, 'role')}</div></div>
        <div class="field"><span class="label" id="termLabel">${esc(t('admin.term'))}</span>
          <div class="seg" role="group" aria-labelledby="termLabel">${segHTML(TERMS.map((x) => [x, t('admin.terms.' + x)]), form.term, 'term')}</div></div>
        <button class="btn primary" id="generate" ${busy ? 'disabled' : ''}>
          ${busy ? '<span class="spinner sm"></span>' : `${icon('plus', 18, 2)}${esc(t('admin.generate'))}`}</button>
        ${creds ? credsHTML(creds) : ''}
      </section>

      <section class="card users" aria-label="${esc(t('admin.list'))}">
        ${accounts.length ? accounts.map((a) => `
          <div class="user">
            <span class="avatar">${esc(initials(a.login))}</span>
            <span class="who">
              <span class="line1"><span class="mono">${esc(a.login)}</span>
                <span class="pill ${a.state}"><span class="dot"></span>${esc(t('admin.stats.' + a.state))}</span></span>
              ${a.full_name || a.tg_username ? `<span class="line2">${esc(a.full_name || '@' + a.tg_username)}</span>` : ''}
              <span class="line2">${esc(userMeta(a))}</span>
            </span>
            <button class="icon-btn ghost" data-menu="${a.id}" aria-label="${esc(t('admin.actions', { login: a.login }))}">${icon('more', 18)}</button>
          </div>`).join('') : `<p class="empty">${esc(t('admin.empty'))}</p>`}
      </section>` : `<button class="btn primary" id="reload">${esc(t('retry'))}</button>`}
    </main>
    ${sheet ? sheetHTML() : ''}`;
    bind();
  }

  function sheetHTML() {
    const a = sheet.account;
    const title = a ? a.login : sheet.request.full_name;
    let body = '';
    if (sheet.mode === 'close') {
      body = `<div class="menu">
        <button data-finish="close"><span class="ic">${icon('check', 18)}</span>
          <span>${esc(t('admin.markDone'))}<small>${esc(t('admin.markDoneNote'))}</small></span></button>
        <button data-finish="reject" class="danger"><span class="ic">${icon('ban', 18)}</span>
          <span>${esc(t('admin.reject'))}<small>${esc(t('admin.rejectNote'))}</small></span></button>
      </div>`;
    } else if (sheet.mode === 'menu') {
      const details = userDetails(a);
      body = `${details.length ? `<p class="note">${details.map(esc).join('<br>')}</p>` : ''}
      <div class="menu">
        <button data-do="reset"><span class="ic">${icon('key', 18)}</span>${esc(t('admin.reset'))}</button>
        <button data-do="extend"><span class="ic">${icon('calendar', 18)}</span>${esc(t('admin.extend'))}</button>
        ${a.status === 'blocked'
          ? `<button data-do="unblock"><span class="ic">${icon('unlock', 18)}</span>${esc(t('admin.unblock'))}</button>`
          : `<button data-do="block" class="danger"><span class="ic">${icon('ban', 18)}</span>${esc(t('admin.block'))}</button>`}
      </div>`;
    } else if (sheet.mode === 'extend') {
      body = `<p class="note">${esc(t('admin.extendTitle'))}</p>
        <div class="seg" role="group">${segHTML(TERMS.map((x) => [x, t('admin.terms.' + x)]), '', 'extend')}</div>`;
    } else if (sheet.mode === 'creds') {
      body = credsHTML(sheet.creds);
    }
    return `
    <div class="sheet-wrap" role="dialog" aria-modal="true" aria-label="${esc(title)}">
      <button class="backdrop" data-close aria-label="${esc(t('close'))}"></button>
      <div class="sheet">
        <span class="grip"></span>
        <div class="head"><h2${a ? ' class="mono"' : ''}>${esc(title)}</h2>
          <button class="icon-btn" data-close aria-label="${esc(t('close'))}">${icon('close', 16, 2.2)}</button></div>
        ${body}
      </div>
    </div>`;
  }

  function bind() {
    const $ = (s) => root.querySelector(s);
    const on = (sel, fn) => root.querySelectorAll(sel).forEach((el) => el.addEventListener('click', (e) => fn(el, e)));
    if ($('#back')) $('#back').addEventListener('click', () => { haptic(); nav.go('dashboard'); });
    if ($('#reload')) $('#reload').addEventListener('click', () => { haptic(); load(); });
    on('[data-copy]', (el) => copy(el.dataset.copy));
    on('[data-role]', (el) => { haptic(); form.role = el.dataset.role; draw(); });
    on('[data-term]', (el) => { haptic(); form.term = el.dataset.term; draw(); });
    if ($('#unlink')) $('#unlink').addEventListener('click', () => { haptic(); form.request = null; draw(); });
    on('[data-approve]', (el) => {
      haptic();
      form.request = data.requests.find((r) => String(r.id) === el.dataset.approve) || null;
      creds = null; draw();
      const card = root.querySelector('#create');
      if (card) card.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    const findReq = (id) => data.requests.find((r) => String(r.id) === id);
    on('[data-close-req]', (el) => {             // done quietly, or rejected (the requester is told)
      haptic();
      sheet = { request: findReq(el.dataset.closeReq), mode: 'close' };
      draw();
    });
    on('[data-finish]', async (el) => {
      const rq = sheet.request;
      if (await act(el.dataset.finish, { request_id: rq.id })) {
        if (form.request && form.request.id === rq.id) form.request = null;
        sheet = null; draw(); toast(t('admin.done')); load();
      }
    });
    on('[data-reset-req]', async (el) => {       // new password for the requester's own login
      const rq = findReq(el.dataset.resetReq);
      const r = await act('reset', { request_id: rq.id });
      if (!r) return;
      haptic('success');
      sheet = { request: rq, mode: 'creds', creds: { title: t('admin.newPassword'), login: r.account.login,
                                                     password: r.password, delivered: r.delivered, note: t('admin.resetNote') } };
      draw();
      load();
    });
    if ($('#generate')) $('#generate').addEventListener('click', async () => {
      busy = true; draw();
      const r = await act('create', { role: form.role, term: form.term, request_id: form.request ? form.request.id : null });
      busy = false;
      if (r) {
        haptic('success');
        creds = { title: t('admin.ready'), login: r.account.login, password: r.password, delivered: form.request ? r.delivered : undefined };
        form.request = null;
        await load();
      } else draw();
    });
    on('[data-menu]', (el) => {
      haptic();
      sheet = { account: data.accounts.find((a) => String(a.id) === el.dataset.menu), mode: 'menu' };
      draw();
    });
    on('[data-close]', () => { haptic(); sheet = null; draw(); });
    on('[data-do]', async (el) => {
      const a = sheet.account, what = el.dataset.do;
      if (what === 'extend') { haptic(); sheet.mode = 'extend'; return draw(); }
      const r = await act(what, { id: a.id });
      if (!r) return;
      if (what === 'reset') {
        sheet = { account: a, mode: 'creds',
                  creds: { title: t('admin.newPassword'), login: r.account.login, password: r.password, note: t('admin.resetNote') } };
      } else { sheet = null; toast(t('admin.done')); }
      draw();                                    // close or switch the sheet now, then refresh the list
      load();
    });
    on('[data-extend]', async (el) => {
      if (await act('extend', { id: sheet.account.id, term: el.dataset.extend })) {
        sheet = null; draw(); toast(t('admin.done')); load();
      }
    });
  }

  draw();
  load();
}
