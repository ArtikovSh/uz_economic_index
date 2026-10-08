// News: economic posts of a day or a date range, filtered by topic, tone and channel.
import { api, errorText, esc, haptic, icon, segHTML, t, tg } from '../lib.js';
import { dayFull, monthName, num, postTime, range, views, weekdayShort } from '../fmt.js';
import { addDays, channelCounts, dayCount } from '../stats.js';
import { topicName } from './overview.js';

const TONES = ['all', 'pos', 'neu', 'neg'];
const TONE_LOOK = { 1: ['pos', 'trendUp', 'ov.pos'], 0: ['neu', 'minus', 'ov.neu'], '-1': ['neg', 'trendDown', 'ov.neg'] };
const clamp = (d, model) => (d < model.first ? model.first : d > model.last ? model.last : d);
const SHOWN = 6;                                   // channels listed before "N more"

/** Fresh news state for a period (optionally one topic): the period's days that have data. */
export function newsState(model, period, topics = []) {
  const from = clamp(period.start, model), to = clamp(period.end, model);
  return { mode: from === to ? 'day' : 'range', from, to, topics, channels: [], tone: 'all', sort: 'new',
           items: [], total: null, more: false, loading: false, error: '' };
}

let seq = 0;

export function renderPosts(ctx) {
  const { model, ui } = ctx;
  if (!model.last) {
    return { html: `<header class="page-hdr"><div><h1>${esc(t('tabs.posts'))}</h1></div></header>
      <div class="empty-state">${icon('news', 28)}<p>${esc(t('ov.empty'))}</p></div>` };
  }
  const P = ui.posts;
  const desktop = window.matchMedia('(min-width: 1024px)').matches;
  const pickerState = P.pickerState || (P.pickerState = { query: '', expanded: false });
  const channelName = (id) => (model.channels.find((c) => c.id === id) || { name: id.replace(/^@/, '') }).name;
  const active = P.topics.length + P.channels.length + (P.tone !== 'all' ? 1 : 0);
  const tags = [
    ...P.topics.map((k) => ['topics', k, topicName(k)]),
    ...P.channels.map((c) => ['channels', c, channelName(c)]),
    ...(P.tone !== 'all' ? [['tone', P.tone, t('ov.' + P.tone)]] : []),
  ];
  const dateLabel = P.mode === 'day' ? dayFull(P.from) : range(P.from, P.to);

  const card = (p) => {
    const [cls, ic, label] = TONE_LOOK[p.s];
    return `
    <article class="pcard">
      <div class="ptop"><span class="tone-chip ${cls}">${icon(ic, 13, 2.2)}${esc(t(label))}</span>
        <span class="ptopic">${esc((p.ts || [p.t]).map(topicName).join(' · '))}</span><span class="ptime">${esc(postTime(p.at))}</span></div>
      ${p.head ? `<h3 class="phead">${esc(p.head)}</h3>` : ''}
      ${p.text ? `<p class="ptext">${esc(p.text)}</p>` : ''}
      <div class="pfoot"><b>${esc(channelName(p.ch))}</b>
        <span class="pviews" aria-label="${esc(t('ps.views'))}">${icon('eye', 14, 1.9)}${esc(views(p.v))}</span>
        <a class="psrc" href="${esc(p.link)}" data-link="${esc(p.link)}">${esc(t('ps.source'))}${icon('external', 14, 2)}</a></div>
    </article>`;
  };
  const list = P.error ? `<p class="form-error" role="alert">${esc(P.error)}</p>`
    : P.total === 0 ? `<div class="empty-state small"><p>${esc(t('ps.empty'))}</p></div>`
      : P.items.map(card).join('') + (P.loading ? '<div class="pcard skl"></div><div class="pcard skl"></div>' : '')
        + (P.more && !P.loading ? `<button class="btn secondary" id="more">${esc(t('ps.more'))}</button>` : '');

  const html = `
  <header class="page-hdr">
    <div><h1>${esc(t('tabs.posts'))}</h1><p>${P.total == null ? '&nbsp;' : esc(t('ps.count', { n: num(P.total) }))}</p></div>
    <div class="top-actions">
      <button class="icon-btn lg ${P.sort !== 'new' ? 'on' : ''}" id="sort" aria-label="${esc(t('ps.sort'))}">${icon('sort', 19, 1.9)}</button>
      <button class="icon-btn lg ${active ? 'on' : ''}" id="filters" aria-label="${esc(t('ps.filters'))}">${icon('sliders', 19, 1.9)}
        ${active ? `<span class="count">${active}</span>` : ''}</button>
    </div>
  </header>
  <button class="date-btn" id="date">${icon('calendar', 18)}<b>${esc(dateLabel)}</b>
    ${P.mode === 'range' ? `<span>${esc(t('ps.nDays', { n: dayCount(P.from, P.to) }))}</span>` : ''}${icon('chevronDown', 16, 2)}</button>
  ${tags.length ? `<div class="tags">${tags.map(([kind, val, label]) => `
    <span class="tag">${esc(label)}<button data-untag="${kind}" data-val="${esc(val)}" aria-label="${esc(t('ps.remove', { x: label }))}">${icon('close', 14, 2.2)}</button></span>`).join('')}</div>` : ''}
  <div class="plist" aria-busy="${P.loading}">${list}</div>
  ${desktop ? `<aside class="filters-panel card" aria-label="${esc(t('ps.filters'))}"></aside>` : ''}`;

  // ------------------------------------------------------------ loading --
  async function load(reset) {
    if (P.filterTimer) reset = true;                 // pagination during a pending filter must start over
    clearTimeout(P.filterTimer); P.filterTimer = null;
    const my = ++seq;
    if (reset) { P.items = []; P.total = null; }
    P.loading = true; P.error = '';
    if (reset) ctx.draw(false);
    let r = null;
    try {
      r = await api('posts', { from: P.from, to: P.to, topics: P.topics, channels: P.channels,
                               tone: P.tone === 'all' ? null : P.tone, sort: P.sort, offset: reset ? 0 : P.items.length });
    } catch (e) { r = null; }
    if (my !== seq || ui.posts !== P) return;                  // a newer request or another view
    P.loading = false;
    if (r && r.ok) {
      P.items = reset ? r.items : P.items.concat(r.items);
      P.total = r.total; P.more = r.more;
    } else P.error = errorText(r);
    if (ui.tab === 'posts' && ctx.isActive()) ctx.draw(false);
  }

  // ------------------------------------------------------------- sheets --
  function openSort() {
    const opts = [['new', 'calendar', 'ps.sortNew', 'ps.sortNewSub'], ['old', 'calendar', 'ps.sortOld', 'ps.sortOldSub'],
      ['views', 'eye', 'ps.sortViews', 'ps.sortViewsSub']];
    ctx.sheet(t('ps.sort'), `<div class="menu">${opts.map(([id, ic, a, b]) => `
      <button data-sort="${id}"><span class="ic">${icon(ic, 18)}</span>
        <span>${esc(t(a))}<small>${esc(t(b))}</small></span>${id === P.sort ? `<span class="check">${icon('check', 20, 2.2)}</span>` : ''}</button>`).join('')}</div>`,
    (body, close) => body.querySelectorAll('[data-sort]').forEach((b) => b.addEventListener('click', () => {
      haptic(); close(); if (P.sort !== b.dataset.sort) { P.sort = b.dataset.sort; load(true); }
    })));
  }

  function openFilters(inlineBody = null) {
    const inline = !!inlineBody;
    const draft = inline ? P : { topics: [...P.topics], channels: [...P.channels], tone: P.tone };
    const keys = topicKeys(model);
    let count = P.total, timer = null, mine = 0;
    // channel picker inside the same sheet: its own selection until "Choose"
    let picking = inline ? draft.channels : null;
    let query = inline ? pickerState.query : '', expanded = inline && pickerState.expanded;
    const counts = channelCounts(model, P.from, P.to);
    const chans = [...model.channels].sort((a, b) => (counts.get(b.id) || 0) - (counts.get(a.id) || 0) || a.name.localeCompare(b.name));
    const chip = (attr, val, label, on) => `<button type="button" data-${attr}="${esc(val)}" aria-pressed="${on}">${esc(label)}</button>`;
    const picked = () => draft.channels.map(channelName);
    const filtersHTML = () => `
      <div class="field"><span class="label">${esc(t('ps.topic'))}</span>
        <div class="chips">${keys.map((k) => chip('topic', k, topicName(k), draft.topics.includes(k))).join('')}</div></div>
      <div class="field"><span class="label">${esc(t('ps.tone'))}</span>
        <div class="seg">${segHTML(TONES.map((x) => [x, t(x === 'all' ? 'ps.all' : 'ov.' + x)]), draft.tone, 'tone')}</div></div>
      ${inline ? pickerHTML() : `<div class="field"><span class="label">${esc(t('ps.channel'))}</span>
        <button type="button" class="pick-row" data-pick>
          <span class="t"><b>${esc(draft.channels.length ? t('ps.nChannels', { n: draft.channels.length }) : t('ps.allChannels'))}</b>
            ${draft.channels.length ? `<small>${esc(picked().join(', '))}</small>` : ''}</span>
          <span class="cnt">${esc(t('ps.ofN', { n: model.channels.length }))}</span>${icon('chevronRight', 18)}</button></div>`}
      ${inline ? `<button class="btn secondary" data-clear>${esc(t('ps.clear'))}</button>` : `
        <div class="two"><button class="btn secondary" data-clear>${esc(t('ps.clear'))}</button>
        <button class="btn primary" data-apply>${esc(t('ps.show', { n: count == null ? '…' : num(count) }))}</button></div>`}`;
    const pickerHTML = () => {
      // the chosen ones first, then by posts in the period
      const list = [...chans.filter((c) => picking.includes(c.id)), ...chans.filter((c) => !picking.includes(c.id))];
      return `
      <div class="cp-head">${inline ? '' : `<button type="button" class="icon-btn" data-cp-back aria-label="${esc(t('back'))}">${icon('back', 16, 2)}</button>`}
        <b>${esc(t('ps.channels'))}</b><span class="cnt">${picking.length} / ${model.channels.length}</span></div>
      <div class="input-wrap">${icon('search', 18)}<input id="cpq" type="search" autocomplete="off" aria-label="${esc(t('ps.searchChannel'))}" placeholder="${esc(t('ps.searchChannel'))}" value="${esc(query)}">
        ${inline ? `<button type="button" class="icon-btn sm" data-cp-search-clear aria-label="${esc(t('ps.clear'))}" ${query ? '' : 'hidden'}>${icon('close', 14, 2)}</button>` : ''}</div>
      <div class="cp-actions"><span>${esc(t('ps.byPosts'))}</span>
        <span><button type="button" class="link" data-cp-all>${esc(t('ps.all'))}</button> · <button type="button" class="link" data-cp-none>${esc(t('ps.clear'))}</button></span></div>
      <div class="cp-list">${list.map((c, i) => `
        <button type="button" class="cp-row" data-cp="${esc(c.id)}" aria-pressed="${picking.includes(c.id)}"
                data-q="${esc((c.name + ' ' + c.id).toLowerCase())}" ${!expanded && i >= SHOWN ? 'hidden' : ''}>
          <span class="avatar">${esc(c.name.charAt(0).toUpperCase())}</span>
          <span class="nm"><b>${esc(c.name)}</b><small>${esc(c.id)}</small></span>
          <span class="n">${esc(num(counts.get(c.id) || 0))}</span><span class="ck">${icon('check', 14, 2.6)}</span>
        </button>`).join('')}</div>
      ${!expanded && list.length > SHOWN ? `<button type="button" class="link cp-more" data-cp-more>${esc(t('ps.moreChannels', { n: list.length - SHOWN }))}</button>` : ''}
      ${inline ? '' : `<div class="two"><button class="btn secondary" data-cp-back>${esc(t('cancel'))}</button>
        <button class="btn primary" data-cp-ok>${esc(t('ps.choose', { n: picking.length }))}</button></div>`}`;
    };
    const html = () => inline ? `<h2>${esc(t('ps.filters'))}</h2>${filtersHTML()}` : (picking ? pickerHTML() : filtersHTML());
    const flip = (arr, v) => (arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);
    let refill = null;
    const recount = () => {
      if (inline) {
        clearTimeout(P.filterTimer);
        ++seq;                                      // invalidate responses before the debounce expires
        P.loading = false; P.total = null; P.error = '';
        P.filterTimer = setTimeout(() => {
          P.filterTimer = null;
          if (ui.tab === 'posts' && ui.posts === P && ctx.isActive()) load(true);
        }, 300);
        return;
      }
      clearTimeout(timer);
      const my = ++mine;
      timer = setTimeout(async () => {
        let r = null;
        try {
          r = await api('posts', { from: P.from, to: P.to, topics: draft.topics, channels: draft.channels,
                                   tone: draft.tone === 'all' ? null : draft.tone, count_only: true });
        } catch (e) { r = null; }
        if (my === mine && r && r.ok) { count = r.total; if (!picking) refill(); }
      }, 250);
    };
    const mount = (body, close, fill) => {
      refill = () => fill(html());
      if (inline) bindPicker(body);
      else if (picking) return bindPicker(body);
      const change = (fn) => () => { haptic(); fn(); if (inline) picking = draft.channels; count = null; refill(); recount(); };
      body.querySelector('[data-pick]')?.addEventListener('click', () => {
        haptic(); picking = [...draft.channels]; query = ''; expanded = false; refill();
      });
      body.querySelectorAll('[data-topic]').forEach((b) => b.addEventListener('click', change(() => { draft.topics = flip(draft.topics, b.dataset.topic); })));
      body.querySelectorAll('[data-tone]').forEach((b) => b.addEventListener('click', change(() => { draft.tone = b.dataset.tone; })));
      body.querySelector('[data-clear]').addEventListener('click', change(() => {
        draft.topics = []; draft.channels = []; draft.tone = 'all';
        if (inline) { query = ''; expanded = false; pickerState.query = ''; pickerState.expanded = false; }
      }));
      body.querySelector('[data-apply]')?.addEventListener('click', () => {
        haptic(); clearTimeout(timer); ++mine; close();
        Object.assign(P, draft);
        load(true);
      });
    };
    if (inline) {
      const fill = (markup) => {
        const focused = document.activeElement;
        const attr = focused && [...focused.attributes].find((a) => a.name.startsWith('data-'));
        const scroll = inlineBody.scrollTop;
        inlineBody.innerHTML = markup;
        mount(inlineBody, null, fill);
        if (attr) [...inlineBody.querySelectorAll(`[${attr.name}]`)]
          .find((b) => b.getAttribute(attr.name) === attr.value)?.focus({ preventScroll: true });
        inlineBody.scrollTop = scroll;
      };
      fill(html());
    } else ctx.sheet(t('ps.filters'), html(), mount);

    function bindPicker(body) {
      const rows = [...body.querySelectorAll('[data-cp]')];
      const search = body.querySelector('#cpq');
      const more = body.querySelector('[data-cp-more]');
      const clearSearch = body.querySelector('[data-cp-search-clear]');
      const show = () => {                          // filter in place: re-rendering would drop the keyboard
        const q = query.trim().toLowerCase();
        rows.forEach((r, i) => { r.hidden = q ? !r.dataset.q.includes(q) : !expanded && i >= SHOWN; });
        if (more) more.hidden = !!q || expanded;
        if (clearSearch) clearSearch.hidden = !query;
        if (inline) { pickerState.query = query; pickerState.expanded = expanded; }
      };
      search.addEventListener('input', () => { query = search.value; show(); });
      clearSearch?.addEventListener('click', () => { query = ''; search.value = ''; show(); search.focus(); });
      show();
      if (more) more.addEventListener('click', () => { haptic(); expanded = true; show(); });
      rows.forEach((r) => r.addEventListener('click', () => {
        haptic();
        picking = flip(picking, r.dataset.cp);
        if (inline) { draft.channels = picking; refill(); recount(); return; }
        r.setAttribute('aria-pressed', String(picking.includes(r.dataset.cp)));
        body.querySelector('.cp-head .cnt').textContent = `${picking.length} / ${model.channels.length}`;
        body.querySelector('[data-cp-ok]').textContent = t('ps.choose', { n: picking.length });
      }));
      const all = (ids) => () => {
        haptic(); picking = ids;
        if (inline) draft.channels = picking;
        refill(); if (inline) recount();
      };
      body.querySelector('[data-cp-all]').addEventListener('click', all(model.channels.map((c) => c.id)));
      body.querySelector('[data-cp-none]').addEventListener('click', all([]));
      body.querySelectorAll('[data-cp-back]').forEach((b) => b.addEventListener('click', () => { haptic(); picking = null; refill(); }));
      body.querySelector('[data-cp-ok]')?.addEventListener('click', () => {
        haptic();
        // every channel chosen is the same as no channel filter
        draft.channels = picking.length === model.channels.length ? [] : picking;
        picking = null; count = null; refill(); recount();
      });
    }
  }

  function openDate() {
    const d = { mode: P.mode, from: P.from, to: P.to, picking: false, month: P.to.slice(0, 7) };
    const lastMonth = model.last.slice(0, 7), firstMonth = model.first.slice(0, 7);
    const presets = () => {
      const m0 = `${lastMonth}-01`;
      return [[t('ps.last7'), clamp(addDays(model.last, -6), model), model.last],
        [t('ps.last30'), clamp(addDays(model.last, -29), model), model.last],
        [monthName(+lastMonth.slice(5) - 1), clamp(m0, model), model.last]];
    };
    const html = () => {
      const [y, m] = d.month.split('-').map(Number);
      const offset = (new Date(Date.UTC(y, m - 1, 1)).getUTCDay() + 6) % 7, n = new Date(Date.UTC(y, m, 0)).getUTCDate();
      const cells = [];
      for (let i = 0; i < offset; i += 1) cells.push('<span></span>');
      for (let k = 1; k <= n; k += 1) {
        const s = `${d.month}-${String(k).padStart(2, '0')}`, ok = model.has.has(s);
        const edge = s === d.from || (d.mode === 'range' && !d.picking && s === d.to);
        const inside = d.mode === 'range' && !d.picking && s > d.from && s < d.to;
        cells.push(`<button type="button" data-day="${s}" ${ok ? '' : 'disabled'} class="${edge ? 'edge' : inside ? 'in' : ''}"
          aria-pressed="${edge}" aria-label="${esc(dayFull(s))}">${k}</button>`);
      }
      const to = d.picking ? d.from : d.to;
      const summary = d.mode === 'day' ? dayFull(d.from) : `${range(d.from, to)} · ${t('ps.nDays', { n: dayCount(d.from, to) })}`;
      return `
      <div class="seg">${segHTML([['range', t('ps.range')], ['day', t('ps.day')]], d.mode, 'mode')}</div>
      ${d.mode === 'range' ? `<div class="chips">${presets().map(([label, a, b], i, all) => `<button type="button" data-preset="${i}"
        aria-pressed="${!d.picking && i === all.findIndex(([, x, y]) => x === d.from && y === d.to)}">${esc(label)}</button>`).join('')}</div>` : ''}
      <div class="cal-nav">
        <button class="icon-btn" data-month="-1" ${d.month <= firstMonth ? 'disabled' : ''} aria-label="${esc(t('ps.prevMonth'))}">${icon('back', 16, 2)}</button>
        <b>${esc(monthName(m - 1))} ${y}</b>
        <button class="icon-btn" data-month="1" ${d.month >= lastMonth ? 'disabled' : ''} aria-label="${esc(t('ps.nextMonth'))}">${icon('chevronRight', 16, 2)}</button>
      </div>
      <div class="cal">${weekdayShort().map((w) => `<span class="wd">${esc(w)}</span>`).join('')}${cells.join('')}</div>
      <p class="note muted"><b class="grey">${esc(t('ps.grey'))}</b>${esc(t('ps.greyTail'))}</p>
      <div class="cal-foot"><span>${esc(summary)}</span><button class="btn primary" data-apply>${esc(t('ps.apply'))}</button></div>`;
    };
    ctx.sheet(t('ps.date'), html(), (body, close, fill) => {
      const redraw = () => fill(html());
      body.querySelectorAll('[data-mode]').forEach((b) => b.addEventListener('click', () => {
        haptic(); d.mode = b.dataset.mode; d.picking = false; if (d.mode === 'day') d.to = d.from; redraw();
      }));
      body.querySelectorAll('[data-preset]').forEach((b) => b.addEventListener('click', () => {
        haptic(); const [, a, z] = presets()[+b.dataset.preset];
        Object.assign(d, { from: a, to: z, picking: false, month: z.slice(0, 7) }); redraw();
      }));
      body.querySelectorAll('[data-month]').forEach((b) => b.addEventListener('click', () => {
        haptic(); const [y, m] = d.month.split('-').map(Number), x = new Date(Date.UTC(y, m - 1 + Number(b.dataset.month), 1));
        d.month = `${x.getUTCFullYear()}-${String(x.getUTCMonth() + 1).padStart(2, '0')}`; redraw();
      }));
      body.querySelectorAll('[data-day]').forEach((b) => b.addEventListener('click', () => {
        haptic(); const s = b.dataset.day;
        if (d.mode === 'day') { d.from = s; d.to = s; } else if (!d.picking) { d.from = s; d.to = s; d.picking = true; } else {
          if (s < d.from) { d.to = d.from; d.from = s; } else d.to = s;
          d.picking = false;
        }
        redraw();
      }));
      body.querySelector('[data-apply]').addEventListener('click', () => {
        haptic(); close();
        P.mode = d.mode; P.from = d.from; P.to = d.picking ? d.from : d.to;
        if (P.mode === 'range' && P.from === P.to) P.mode = 'day';
        load(true);
      });
    });
  }

  return {
    html,
    bind(el) {
      // Defer the initial request until the shell has finished binding this render.
      if (P.total == null && !P.loading && !P.error && !P.filterTimer) queueMicrotask(() => {
        if (ui.tab === 'posts' && ui.posts === P && ctx.isActive()) load(true);
      });
      const panel = el.querySelector('.filters-panel');
      if (panel) openFilters(panel);
      el.querySelector('#sort').addEventListener('click', () => { haptic(); openSort(); });
      el.querySelector('#filters').addEventListener('click', () => { haptic(); openFilters(); });
      el.querySelector('#date').addEventListener('click', () => { haptic(); openDate(); });
      el.querySelectorAll('[data-untag]').forEach((b) => b.addEventListener('click', () => {
        haptic(); const kind = b.dataset.untag;
        if (kind === 'tone') P.tone = 'all'; else P[kind] = P[kind].filter((x) => x !== b.dataset.val);
        load(true);
      }));
      const more = el.querySelector('#more');
      if (more) more.addEventListener('click', () => { haptic(); load(false); ctx.draw(false); });
      el.querySelectorAll('[data-link]').forEach((a) => a.addEventListener('click', (e) => {
        e.preventDefault(); haptic();
        try { tg.openTelegramLink(a.dataset.link); } catch (err) { window.open(a.dataset.link, '_blank'); }
      }));
    },
  };
}

/** Topic keys ordered by how often they occur, so the common ones come first. */
function topicKeys(model) {
  const n = new Map();
  model.topics.forEach(([, k, c]) => n.set(k, (n.get(k) || 0) + c));
  return [...n.keys()].sort((a, b) => n.get(b) - n.get(a));
}
