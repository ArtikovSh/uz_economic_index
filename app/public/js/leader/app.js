import { api, errorText, haptic, icon, logo, setBack, t, toast } from '../lib.js';
import { num } from '../fmt.js';
import { home, mountHome } from './home.js';
import { topics, mountTopics } from './topics.js';
import { posts, mountPosts } from './posts.js';
import { settings, mountSettings } from './settings.js';
import { onboarding } from './onboarding.js';
import { countUp, periodPanel, text } from './components.js';
import { periods, selectedChannels } from './model.js';
import { appear, reduced } from './motion.js';

const TABS = [['home', 'home'], ['topics', 'layers'], ['settings', 'settings']];
const VIEWS = { home, topics, posts, settings }, MOUNTS = { home: mountHome, topics: mountTopics, posts: mountPosts, settings: mountSettings };
export function renderLeader(root, nav, state) {
  const shell = document.createElement('div'); shell.className = 'leader-shell'; root.replaceChildren(shell);
  let cleanups = [], numberStop = () => {}, pending = {}, saveTimer, queue = Promise.resolve(), revision = 0;
  let confirmed = structuredClone(state.data.prefs);
  const ctx = {
    root, nav, shell, main: null, data: state.data.leader, prefs: state.data.prefs, me: state.data.me,
    ui: { tab: 'home', type: 'kun', keys: {}, origin: 'home', scroll: 0, posts: null },
    track: (fn) => cleanups.push(fn), back: null, draw, launch, updatePrefs, flushPrefs, dispose,
    period() {
      const list = periods(ctx.data, ctx.ui.type);
      let index = list.findIndex((p) => p.key === ctx.ui.keys[ctx.ui.type]);
      if (index < 0) index = list.length - 1;
      return { p: list[index] || null, list, index };
    },
    openNews(opts) {
      ctx.ui.origin = ctx.ui.tab; ctx.ui.scroll = ctx.main.scrollTop;
      ctx.ui.posts = { tone: opts.tone || 'all', topics: opts.topics || null, sort: 'new', items: [], total: null, more: false };
      ctx.ui.tab = 'posts'; draw('static');
    },
    animateNumbers(mode, old) { numberStop(); numberStop = countUp(ctx.main, mode, old); },
  };
  function dispose() { cleanups.forEach((fn) => fn()); cleanups = []; numberStop(); clearTimeout(saveTimer); setBack(null); }
  function back() {
    if (ctx.ui.tab !== 'posts') return;
    ctx.ui.tab = ctx.ui.origin; draw('static'); ctx.main.scrollTop = ctx.ui.scroll;
  }
  function updatePrefs(patch) {
    Object.assign(ctx.prefs, patch); Object.assign(pending, patch); revision++;
    clearTimeout(saveTimer); saveTimer = setTimeout(flushPrefs, 400);
  }
  function flushPrefs() {
    clearTimeout(saveTimer);
    const patch = pending, mine = revision; pending = {};
    if (!Object.keys(patch).length) return queue;
    queue = queue.then(async () => {
      try {
        const r = await api('prefs_set', patch); if (!r.ok) throw r;
        confirmed = r.prefs;
        if (patch.channels) {
          const data = await api('leader_stats', { channels: patch.channels }); if (!data.ok) throw data;
          if (JSON.stringify(ctx.prefs.channels) === JSON.stringify(patch.channels)) ctx.data = data;
        }
        if (shell.isConnected && ctx.ui.tab !== 'settings') draw('update', true);
      } catch (r) {
        if (mine === revision) {
          for (const key of Object.keys(patch)) ctx.prefs[key] = confirmed[key];
          if (shell.isConnected) draw('update', true);
        }
        toast(errorText(r));
      }
    });
    return queue;
  }
  function launch() {
    shell.innerHTML = '<div class="leader-content"><header class="leader-header"></header><main class="leader-scroll"></main></div><nav class="leader-nav"></nav>';
    ctx.main = shell.querySelector('main'); draw('entry');
  }
  function draw(mode = 'entry', preserve = false) {
    const scroll = preserve ? ctx.main.scrollTop : 0;
    const newsHeight = preserve && ctx.ui.tab === 'posts' ? ctx.main.scrollHeight : 0;
    const old = Object.fromEntries([...ctx.main.querySelectorAll('[data-number]')].map((el) => [el.dataset.number, +el.dataset.display || 0]));
    const oldGauge = +(ctx.main.querySelector('.leader-gauge')?.dataset.value || 0);
    const oldBars = Object.fromEntries([...ctx.main.querySelectorAll('[data-bar]')].map((el) => [el.dataset.bar, el.style.width || el.style.flexGrow]));
    cleanups.forEach((fn) => fn()); cleanups = []; numberStop();
    const tab = ctx.ui.tab;
    shell.dataset.tab = tab;
    shell.querySelector('.leader-header').innerHTML = tab === 'home' ? `${logo(34)}<div><h1>${text('leader.title')}</h1><p>${text('leader.subtitle', { n: num(selectedChannels(ctx).length) })}</p></div>`
      : `${tab === 'posts' ? `<button class="icon-btn" data-back aria-label="${text('back')}">${icon('back')}</button>` : ''}<h1>${text(tab === 'settings' ? 'leader.settings' : 'tabs.' + tab)}</h1>`;
    shell.querySelector('[data-back]')?.addEventListener('click', back);
    ctx.back = tab === 'posts' ? back : null;
    if (!ctx.closeSheet) setBack(ctx.back);
    ctx.main.innerHTML = (tab === 'home' || tab === 'topics' ? periodPanel(ctx) : '') + VIEWS[tab](ctx);
    if (newsHeight) ctx.main.querySelector('.leader-news').style.minHeight = newsHeight + 'px';
    ctx.main.scrollTop = scroll;
    const active = tab === 'posts' ? ctx.ui.origin : tab;
    shell.querySelector('.leader-nav').setAttribute('aria-label', t('leader.navigation'));
    shell.querySelector('.leader-nav').innerHTML = TABS.map(([key, ic]) => `<button data-tab="${key}" ${active === key ? 'aria-current="page"' : ''}>${icon(ic, 22)}${text(key === 'settings' ? 'leader.settings' : 'tabs.' + key)}</button>`).join('');
    shell.querySelectorAll('[data-tab]').forEach((b) => { b.onclick = () => {
      if (ctx.ui.tab === b.dataset.tab) return;
      haptic(); ctx.ui.tab = b.dataset.tab; draw('entry');
    }; });
    ctx.main.querySelectorAll('[data-period]').forEach((b) => { b.onclick = () => { ctx.ui.type = b.dataset.period; draw('update', true); }; });
    ctx.main.querySelectorAll('[data-step]').forEach((b) => { b.onclick = () => {
      const { list, index } = ctx.period(), p = list[index + +b.dataset.step];
      if (p) { ctx.ui.keys[ctx.ui.type] = p.key; draw('update', true); }
    }; });
    MOUNTS[tab](ctx, mode, oldGauge);
    ctx.animateNumbers(tab === 'home' && mode === 'entry' && !reduced() && ctx.main.querySelector('.leader-gauge').dataset.target !== '' ? 'waiting' : mode, old);
    if (!reduced() && mode !== 'static') ctx.main.querySelectorAll('[data-bar]').forEach((el) => {
      const prop = el.style.width ? 'width' : 'flexGrow', target = el.style[prop];
      el.style[prop] = mode === 'entry' ? '0' : oldBars[el.dataset.bar] || '0';
      el.getBoundingClientRect();
      const frame = requestAnimationFrame(() => { el.style[prop] = target; });
      ctx.track(() => cancelAnimationFrame(frame));
    });
    if (mode === 'entry') {
      const content = ctx.main.querySelector('.leader-home,.leader-topics,.leader-settings');
      if (content) ctx.track(appear(content));
    }
  }
  setBack(null);
  if (ctx.prefs.onboarded) launch(); else onboarding(ctx);
}
