// Mini App entry: asks the server who the Telegram user is and opens the right screen.
import { api, applyTheme, errorText, tg } from './lib.js';
import { renderContact, renderDenied, renderError, renderLogin, renderOutside, renderSent } from './screens.js';
import { renderAdmin } from './admin.js';
import { renderDashboard } from './dashboard.js';

const root = document.getElementById('root');
const state = { auth: null, data: null, requestOpen: false };
let deepLink = new URLSearchParams(location.search).get('screen');   // bot buttons open ?screen=admin
const SCREENS = {
  login: renderLogin, contact: renderContact, sent: renderSent, denied: renderDenied,
  outside: renderOutside, error: renderError, admin: renderAdmin, dashboard: renderDashboard,
};

const nav = {
  go(screen, opts) {
    window.scrollTo(0, 0);
    SCREENS[screen](root, nav, state, opts || {});
  },
  reload() { return boot(); },
};

async function boot() {
  applyTheme();
  if (!tg || !tg.initData) return nav.go('outside');
  root.innerHTML = '<div class="boot"><span class="spinner"></span></div>';
  let r = null;
  try { r = await api(); } catch (e) { r = null; }
  if (r && r.status === 401) return nav.go('outside');
  if (!r || !r.auth) return nav.go('error', { text: errorText(r) });
  state.auth = r.auth;
  state.requestOpen = !!r.request_open;
  state.data = r.auth === 'ok' ? r : null;
  if (r.auth === 'login') return nav.go('login');
  if (r.auth !== 'ok') return nav.go('denied');
  const want = deepLink;
  deepLink = null;                                   // only the first screen after sign-in
  return nav.go(want === 'admin' && r.me && r.me.is_admin ? 'admin' : 'dashboard');
}

if (tg) {
  try { tg.ready(); tg.expand(); } catch (e) { /* older clients */ }
  try { tg.onEvent('themeChanged', applyTheme); } catch (e) { /* older clients */ }
}
boot();
