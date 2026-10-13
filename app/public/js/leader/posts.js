import { api, errorText, esc, icon, t, tg } from '../lib.js';
import { num, postTime, views } from '../fmt.js';
import { periodPanel, sheet, text } from './components.js';
import { aggregate, selectedChannels, selectedTopics, TONES } from './model.js';
import { animate, appear, outCubic } from './motion.js';

const SORTS = ['new', 'old', 'views'];
const sortKey = (sort) => 'ps.sort' + sort[0].toUpperCase() + sort.slice(1);
const options = (P) => SORTS.map((s) => `<button data-sort="${s}" aria-pressed="${P.sort === s}"><span><b>${text(sortKey(s))}</b><small>${text(sortKey(s) + 'Sub')}</small></span>${P.sort === s ? icon('check') : ''}</button>`).join('');
const tones = (ctx) => {
  const P = ctx.ui.posts, total = aggregate(ctx.data, ctx.period().p, P.topics || selectedTopics(ctx.prefs));
  return `<div class="leader-tones" role="group" aria-label="${text('ps.tone')}">${['all', ...TONES].map((key, i) => `<button data-tone="${key}" aria-pressed="${P.tone === key}"><span>${text(i ? 'ov.' + key : 'ps.all')}</span><small class="${i ? key : ''}">${num(i ? total.tones[i - 1] : total.total)}</small></button>`).join('')}</div>`;
};
export function posts(ctx) {
  const P = ctx.ui.posts;
  return `<div class="leader-news"><div class="leader-news-top">${periodPanel(ctx)}</div>
    <div class="leader-news-filters">${tones(ctx)}<div class="leader-news-count"><span data-post-count></span><button data-sort-open>${icon('sort', 16)}${text(sortKey(P.sort))}${icon('chevronDown', 14)}</button></div></div>
    <div class="leader-post-list" aria-live="polite" aria-busy="true"></div>
    <aside class="leader-news-aside">${periodPanel(ctx)}${tones(ctx)}<div class="leader-sort-options">${options(P)}</div><span data-post-count></span></aside></div>`;
}
function card(ctx, p) {
  const key = p.s > 0 ? 'pos' : p.s < 0 ? 'neg' : 'neu';
  const name = ctx.data.channels.find((c) => c.id === p.ch)?.name || p.ch;
  return `<article class="pcard"><div class="ptop"><span class="tone-chip ${key}">${icon(key === 'pos' ? 'trendUp' : key === 'neg' ? 'trendDown' : 'minus', 13, 2.2)}${text('ov.' + key)}</span>
    <span class="ptopic">${esc((p.ts || [p.t]).map((topic) => t('topics.' + topic)).join(' · '))}</span><span class="ptime">${esc(ctx.ui.type === 'kun' ? p.at.slice(11, 16) : postTime(p.at))}</span></div>
    ${p.head ? `<h3 class="phead">${esc(p.head)}</h3>` : ''}${p.text ? `<p class="ptext">${esc(p.text)}</p>` : ''}
    <div class="pfoot"><b>${esc(name)}</b><span class="pviews" aria-label="${text('ps.views')}">${icon('eye', 14)}${esc(views(p.v))}</span>
    <a class="psrc" href="${esc(p.link)}" data-link="${esc(p.link)}">${text('ps.source')}${icon('external', 14)}</a></div></article>`;
}
export function mountPosts(ctx) {
  const P = ctx.ui.posts, list = ctx.main.querySelector('.leader-post-list');
  let seq = 0, stopScroll = () => {};
  ctx.track(() => { seq++; stopScroll(); });
  const smoothTop = () => {
    stopScroll(); const start = ctx.main.scrollTop;
    const release = () => { list.style.minHeight = ''; ctx.main.querySelector('.leader-news')?.style.removeProperty('min-height'); };
    if (start) stopScroll = animate(700, (t) => { ctx.main.scrollTop = start * (1 - outCubic(t)); }, release);
    else release();
  };
  const renderList = (oldLength = 0) => {
    list.setAttribute('aria-busy', P.loading);
    ctx.main.querySelectorAll('[data-post-count]').forEach((el) => { el.textContent = P.total == null ? '' : t('leader.posts', { n: num(P.total) }); });
    list.querySelector('[data-more]')?.remove(); list.querySelector('[data-loading]')?.remove();
    list.querySelector('[data-post-error]')?.remove();
    if (!oldLength) list.innerHTML = '';
    const fresh = document.createElement('div');
    fresh.innerHTML = P.items.slice(oldLength).map((p) => card(ctx, p)).join('');
    [...fresh.children].forEach((el, i) => { list.append(el); ctx.track(appear(el, 380, 12, 45 * Math.min(i, 8))); });
    if (P.error) list.insertAdjacentHTML('beforeend', `<div data-post-error role="alert"><p class="form-error">${esc(P.error)}</p><button class="btn secondary" data-retry>${text('retry')}</button></div>`);
    else if (!P.loading && !P.total) list.innerHTML = `<p class="leader-empty">${text('leader.empty')}</p>`;
    if (P.loading) list.insertAdjacentHTML('beforeend', '<div data-loading class="boot"><span class="spinner"></span></div>');
    else if (P.more) list.insertAdjacentHTML('beforeend', `<button class="btn secondary" data-more>${text('leader.more', { n: num(Math.min(30, P.total - P.items.length)) })}</button>`);
    list.querySelector('[data-more]')?.addEventListener('click', () => load(false));
    list.querySelector('[data-retry]')?.addEventListener('click', () => load(true));
    list.querySelectorAll('[data-link]').forEach((el) => { el.onclick = (e) => { if (tg?.openTelegramLink) { e.preventDefault(); tg.openTelegramLink(el.dataset.link); } }; });
  };
  async function load(reset) {
    if (!reset && P.loading) return;
    const mine = ++seq, oldLength = reset ? 0 : P.items.length;
    if (reset) { list.style.minHeight = list.offsetHeight + 'px'; P.items = []; P.total = null; smoothTop(); }
    P.loading = true; P.error = ''; renderList(oldLength);
    try {
      const p = ctx.period().p;
      const r = p ? await api('posts', { from: p.start, to: p.end, channels: selectedChannels(ctx),
        topics: P.topics || selectedTopics(ctx.prefs), tone: P.tone === 'all' ? null : P.tone, sort: P.sort, offset: oldLength })
        : { ok: true, items: [], total: 0, more: false };
      if (mine !== seq || !list.isConnected) return;
      if (!r.ok) throw r;
      P.items.push(...r.items); P.total = r.total; P.more = r.more;
    } catch (r) { if (mine !== seq || !list.isConnected) return; P.error = errorText(r); }
    P.loading = false; renderList(oldLength);
  }
  ctx.main.querySelectorAll('[data-tone]').forEach((b) => { b.onclick = () => {
    P.tone = b.dataset.tone;
    ctx.main.querySelectorAll('[data-tone]').forEach((el) => el.setAttribute('aria-pressed', el.dataset.tone === P.tone)); load(true);
  }; });
  const changeSort = (sort) => {
    P.sort = sort;
    ctx.main.querySelector('.leader-sort-options').innerHTML = options(P); bindSort(ctx.main);
    ctx.main.querySelector('[data-sort-open]').innerHTML = icon('sort', 16) + text(sortKey(sort)) + icon('chevronDown', 14);
    load(true);
  };
  const bindSort = (el, close) => el.querySelectorAll('[data-sort]').forEach((b) => { b.onclick = () => { close?.(); changeSort(b.dataset.sort); }; });
  bindSort(ctx.main);
  ctx.main.querySelector('[data-sort-open]').onclick = () => sheet(ctx, t('ps.sort'), `<div class="leader-sort-options">${options(P)}</div>`, (panel, close) => bindSort(panel, close));
  load(true);
}
