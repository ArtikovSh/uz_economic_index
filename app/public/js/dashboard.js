// Dashboard shell: four tabs over the daily index data, plus the language and account sheets.
import { api, esc, fmtDate, haptic, icon, lang, LANGS, openSheet, setBack, setLang, t } from './lib.js';
import { buildModel, locate, TYPES } from './stats.js';
import { renderOverview } from './views/overview.js';
import { renderMethod, renderTopics } from './views/topics.js';
import { newsState, renderPosts } from './views/posts.js';

const TABS = [['home', 'home'], ['topics', 'layers'], ['posts', 'news'], ['method', 'book']];
const VIEWS = { home: renderOverview, topics: renderTopics, posts: renderPosts, method: renderMethod };

export function renderDashboard(root, nav, state) {
  setBack(null);
  const model = buildModel((state.data && state.data.stats) || {});
  const me = (state.data && state.data.me) || {};
  const ui = state.ui || (state.ui = { tab: 'home', type: 'kun', keys: {}, posts: null });
  const check = `<span class="check">${icon('check', 20, 2.2)}</span>`;

  const ctx = {
    root, nav, model, me, ui, draw, go,
    sheet: (title, html, mount) => openSheet(root, title, html, mount),
    period: () => locate(model, ui.type, ui.keys[ui.type]),
    setType(type) { haptic(); ui.type = type; draw(false); },
    setKey(key) { haptic(); ui.keys[ui.type] = key; draw(false); },
    pickType() {
      haptic();
      ctx.sheet(t('period.pick'), `<div class="menu">${TYPES.map((p) =>
        `<button data-pt="${p}"><span>${esc(t('period.' + p))}</span>${p === ui.type ? check : ''}</button>`).join('')}</div>`,
      (body, close) => body.querySelectorAll('[data-pt]').forEach((b) => b.addEventListener('click', () => {
        close(); ctx.setType(b.dataset.pt);
      })));
    },
  };

  /** Switch tab; the news tab starts from the selected period (and topic, when given). */
  function go(tab, opts = {}) {
    haptic();
    if (tab === 'posts' && model.last && (opts.topics || !ui.posts)) {
      ui.posts = newsState(model, ctx.period().cur, opts.topics || []);
    }
    ui.tab = tab;
    window.scrollTo(0, 0);
    draw();
  }

  function openLanguage() {
    haptic();
    ctx.sheet(t('langTitle'), `<div class="menu">${LANGS.map(([id, label]) =>
      `<button data-lang="${id}"><span>${esc(label)}</span>${id === lang() ? check : ''}</button>`).join('')}</div>`,
    (body, close) => body.querySelectorAll('[data-lang]').forEach((b) => b.addEventListener('click', () => {
      haptic(); setLang(b.dataset.lang); close(); draw(false);
    })));
  }

  function openAccount() {
    haptic();
    const until = me.expires_at ? t('admin.until', { d: fmtDate(me.expires_at) }) : t('admin.noExpiry');
    ctx.sheet(me.login || t('dash.account'), `
      <p class="note">${esc(t('roles.' + me.role))} · ${esc(until)}</p>
      <div class="menu">
        ${me.is_admin ? `<button data-users><span class="ic">${icon('users', 18)}</span><span>${esc(t('dash.users'))}</span></button>` : ''}
        ${me.owner ? '' : `<button class="danger" data-logout><span class="ic">${icon('logout', 18)}</span><span>${esc(t('dash.logout'))}</span></button>`}
      </div>`, (body, close) => {
      const users = body.querySelector('[data-users]');
      if (users) users.addEventListener('click', () => { haptic(); close(); nav.go('admin'); });
      const out = body.querySelector('[data-logout]');
      if (out) out.addEventListener('click', async () => {
        haptic();
        try { await api('logout'); } catch (e) { /* the reload shows the state */ }
        nav.reload();
      });
    });
  }

  function draw(animate = true) {
    if (ui.tab === 'posts' && !ui.posts && model.last) ui.posts = newsState(model, ctx.period().cur);
    const view = VIEWS[ui.tab](ctx);
    root.innerHTML = `
    <main class="screen app${animate ? ' fade' : ''}">${view.html}</main>
    <nav class="tabbar" aria-label="${esc(t('dash.title'))}">${TABS.map(([id, ic]) =>
      `<button type="button" data-nav="${id}" ${ui.tab === id ? 'aria-current="page"' : ''}>${icon(ic, 22, ui.tab === id ? 1.9 : 1.8)}${esc(t('tabs.' + id))}</button>`).join('')}</nav>`;
    if (view.bind) view.bind(root);
    root.querySelectorAll('[data-nav]').forEach((b) => b.addEventListener('click', () => {
      if (b.dataset.nav !== ui.tab) go(b.dataset.nav);
    }));
    const langBtn = root.querySelector('#lang');
    if (langBtn) langBtn.addEventListener('click', openLanguage);
    const account = root.querySelector('#account');
    if (account) account.addEventListener('click', openAccount);
  }

  draw();
}
