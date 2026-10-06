// Screens before sign-in: login, contact the administrator, request sent, access denied.
import { api, errorText, esc, haptic, icon, lang, LANGS, logo, segHTML, setBack, setLang, t, tg } from './lib.js';

export function renderLogin(root, nav) {
  setBack(null);
  let values = { login: '' }, error = '', busy = false, showPw = false, shown = false;

  const draw = () => {
    root.innerHTML = `
    <main class="screen login${shown ? '' : ' fade'}">
      <div class="lang-row"><div class="seg compact" role="group" aria-label="Til">${segHTML(LANGS, lang(), 'lang')}</div></div>
      <div class="login-center">
        <div class="brand">${logo(60)}<div><h1>UZ Economic Index</h1><p>${esc(t('auth.tag'))}</p></div></div>
        <form class="card form" id="form" novalidate>
          <div class="field">
            <label for="login">${esc(t('auth.login'))}</label>
            <div class="input-wrap">${icon('user', 18)}
              <input id="login" class="mono" autocomplete="username" autocapitalize="none" autocorrect="off" spellcheck="false"
                     placeholder="${esc(t('auth.loginPh'))}" value="${esc(values.login)}"></div>
          </div>
          <div class="field">
            <label for="password">${esc(t('auth.password'))}</label>
            <div class="input-wrap">${icon('lock', 18)}
              <input id="password" class="mono" type="${showPw ? 'text' : 'password'}" autocomplete="current-password"
                     placeholder="${esc(t('auth.passwordPh'))}">
              <button type="button" class="icon-btn ghost" id="eye" aria-label="${esc(t(showPw ? 'auth.hidePw' : 'auth.showPw'))}">${icon(showPw ? 'eyeOff' : 'eye', 18)}</button>
            </div>
          </div>
          ${error ? `<p class="form-error" role="alert">${esc(error)}</p>` : ''}
          <button class="btn primary" type="submit" ${busy ? 'disabled' : ''}>
            ${busy ? '<span class="spinner sm"></span>' : `${esc(t('auth.signIn'))}${icon('arrowRight', 18, 2)}`}
          </button>
        </form>
      </div>
      <p class="foot">${esc(t('auth.noCreds'))}<a href="#contact" id="contact" class="link">${esc(t('auth.contactLink'))}</a>${esc(t('auth.contactTail'))}</p>
    </main>`;
    shown = true;

    root.querySelectorAll('[data-lang]').forEach((b) => b.addEventListener('click', () => {
      haptic();
      const pw = root.querySelector('#password').value;     // kept in the DOM only, never in the markup
      values.login = root.querySelector('#login').value; setLang(b.dataset.lang); draw();
      root.querySelector('#password').value = pw;
    }));
    root.querySelector('#eye').addEventListener('click', (e) => {
      showPw = !showPw;                                       // in place: a re-render would clear the password
      const pw = root.querySelector('#password'), eye = e.currentTarget;
      pw.type = showPw ? 'text' : 'password';
      eye.innerHTML = icon(showPw ? 'eyeOff' : 'eye', 18);
      eye.setAttribute('aria-label', t(showPw ? 'auth.hidePw' : 'auth.showPw'));
      pw.focus();
    });
    root.querySelector('#contact').addEventListener('click', (e) => { e.preventDefault(); haptic(); nav.go('contact', { from: 'login' }); });
    root.querySelector('#form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const login = root.querySelector('#login').value.trim();
      const password = root.querySelector('#password').value;
      values.login = login;
      if (!login || !password) { error = t('err.fill'); haptic('error'); return draw(); }
      busy = true; error = ''; draw();
      let r = null;
      try { r = await api('login', { login, password }); } catch (err) { r = null; }
      busy = false;
      if (r && r.ok) { haptic('success'); return nav.reload(); }
      error = errorText(r); haptic('error'); draw();
    });
  };
  draw();
}

export function renderContact(root, nav, state, opts = {}) {
  setBack(() => nav.go(opts.from || 'login'));
  const u = (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) || {};
  const form = { full_name: [u.first_name, u.last_name].filter(Boolean).join(' '), organization: '', reason: 'access', message: '' };
  let error = '', busy = false, shown = false;
  const tgName = u.username ? '@' + u.username : [u.first_name, u.last_name].filter(Boolean).join(' ');

  const read = () => {
    form.full_name = root.querySelector('#fullname').value;
    form.organization = root.querySelector('#org').value;
    form.message = root.querySelector('#note').value;
  };
  const draw = () => {
    const reasons = ['access', 'reset', 'other'].map((k) => [k, t('contact.reasons.' + k)]);
    root.innerHTML = `
    <main class="screen${shown ? '' : ' fade'}">
      <header class="topbar">
        <button class="icon-btn" id="back" aria-label="${esc(t('back'))}">${icon('back', 18, 2)}</button>
        <h1>${esc(t('contact.title'))}</h1>
      </header>
      ${state.requestOpen ? `<p class="context" role="status">${icon('info', 16)}<span>${esc(t('contact.pending'))}</span></p>` : ''}
      <form class="card form" id="form" novalidate style="margin-top:8px">
        <div class="field"><label for="fullname">${esc(t('contact.fullName'))}</label>
          <input id="fullname" class="input" autocomplete="name" maxlength="80" placeholder="${esc(t('contact.fullNamePh'))}" value="${esc(form.full_name)}"></div>
        <div class="field"><label for="org">${esc(t('contact.org'))}</label>
          <input id="org" class="input" autocomplete="organization" maxlength="120" placeholder="${esc(t('contact.orgPh'))}" value="${esc(form.organization)}"></div>
        <div class="field"><span class="label" id="reasonLabel">${esc(t('contact.reason'))}</span>
          <div class="chips" role="group" aria-labelledby="reasonLabel">${segHTML(reasons, form.reason, 'reason')}</div></div>
        <div class="field"><label for="note">${esc(t('contact.message'))}</label>
          <textarea id="note" class="input" rows="3" maxlength="500" placeholder="${esc(t('contact.messagePh'))}">${esc(form.message)}</textarea></div>
        <div class="field"><span class="label">${esc(t('contact.telegram'))}</span>
          <div class="readonly">${icon('send', 18)}<span>${esc(tgName || '—')}</span><span class="hint">${esc(t('contact.auto'))}</span></div></div>
        ${error ? `<p class="form-error" role="alert">${esc(error)}</p>` : ''}
        <button class="btn primary" type="submit" ${busy ? 'disabled' : ''}>
          ${busy ? '<span class="spinner sm"></span>' : `${esc(t('contact.send'))}${icon('arrowRight', 18, 2)}`}
        </button>
      </form>
    </main>`;
    shown = true;
    root.querySelector('#back').addEventListener('click', () => { haptic(); nav.go(opts.from || 'login'); });
    root.querySelectorAll('[data-reason]').forEach((b) => b.addEventListener('click', () => {
      haptic(); read(); form.reason = b.dataset.reason; draw();
    }));
    root.querySelector('#form').addEventListener('submit', async (e) => {
      e.preventDefault(); read();
      if (form.full_name.trim().length < 3) { error = t('err.name'); haptic('error'); return draw(); }
      busy = true; error = ''; draw();
      let r = null;
      try { r = await api('request', form); } catch (err) { r = null; }
      busy = false;
      if (r && r.ok) { haptic('success'); state.requestOpen = true; return nav.go('sent'); }
      error = errorText(r); haptic('error'); draw();
    });
  };
  draw();
}

export function renderSent(root, nav) {
  setBack(() => nav.go('login'));
  root.innerHTML = `
  <main class="screen fade">
    <div class="center-msg">
      <span class="ring ok">${icon('check', 32, 2.2)}</span>
      <h2>${esc(t('sent.title'))}</h2>
      <p>${esc(t('sent.text'))}</p>
      <button class="btn secondary" id="back">${esc(t('sent.back'))}</button>
    </div>
  </main>`;
  root.querySelector('#back').addEventListener('click', () => { haptic(); nav.go('login'); });
}

export function renderDenied(root, nav, state) {
  setBack(null);
  root.innerHTML = `
  <main class="screen fade">
    <div class="center-msg">
      <span class="ring warn">${icon(state.auth === 'blocked' ? 'ban' : 'calendar', 30, 2)}</span>
      <h2>${esc(t('denied.' + (state.auth === 'blocked' ? 'blocked' : 'expired')))}</h2>
      <p>${esc(t('auth.noCreds'))}<a href="#contact" id="contact" class="link">${esc(t('auth.contactLink'))}</a>${esc(t('auth.contactTail'))}</p>
      <button class="btn secondary" id="other">${esc(t('denied.other'))}</button>
    </div>
  </main>`;
  root.querySelector('#contact').addEventListener('click', (e) => { e.preventDefault(); haptic(); nav.go('contact', { from: 'denied' }); });
  root.querySelector('#other').addEventListener('click', async () => {
    haptic();
    try { await api('logout'); } catch (e) { /* the reload shows the state anyway */ }
    nav.reload();
  });
}

export function renderOutside(root) {
  setBack(null);
  root.innerHTML = `
  <main class="screen fade">
    <div class="center-msg">${logo(60)}<h2>UZ Economic Index</h2><p>${esc(t('outside.text'))}</p></div>
  </main>`;
}

export function renderError(root, nav, state, opts = {}) {
  setBack(null);
  root.innerHTML = `
  <main class="screen fade">
    <div class="center-msg">
      <span class="ring warn">${icon('alert', 30, 2)}</span>
      <p>${esc(opts.text || t('err.network'))}</p>
      <button class="btn primary" id="retry">${icon('refresh', 18, 2)}${esc(t('retry'))}</button>
    </div>
  </main>`;
  root.querySelector('#retry').addEventListener('click', () => { haptic(); nav.reload(); });
}
