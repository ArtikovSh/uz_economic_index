// Overview: period switch, EAI/ESI cards, trend, tone split, coverage and main topics.
import { esc, icon, lang, logo, t } from '../lib.js';
import { num, periodLabel, signed, versus } from '../fmt.js';
import { TYPES, series, topicsOf } from '../stats.js';
import { dynamics, sparkBars, sparkLine } from '../charts.js';

export const topicName = (k) => { const s = t('topics.' + k); return s.startsWith('topics.') ? k : s; };
export const netClass = (v) => (v > 0 ? 'pos' : v < 0 ? 'neg' : 'zero');

export function brandHeader() {
  return `
  <header class="hdr">
    <div class="brand-sm">${logo(34)}<div><b>${esc(t('dash.title'))}</b><span>${esc(t('dash.sub'))}</span></div></div>
    <div class="top-actions">
      <button class="icon-btn wide" id="lang" aria-label="${esc(t('langTitle'))}">${icon('globe', 16)}${esc(lang().toUpperCase())}</button>
      <button class="icon-btn" id="account" aria-label="${esc(t('dash.account'))}">${icon('user', 18)}</button>
    </div>
  </header>`;
}

/** Delta chip: arrow up or down, value; ESI chips carry the tone colour. */
function delta(d, digits, unit, toned) {
  const cls = !toned || d === 0 ? 'flat' : d > 0 ? 'pos' : 'neg';
  const arrow = d === 0 ? icon('minus', 12, 2.4) : `<span class="${d < 0 ? 'turn' : ''}">${icon('up', 12, 2.4)}</span>`;
  return `<span class="delta ${cls}">${arrow}${esc(signed(d, digits))}${unit ? ' ' + esc(unit) : ''}</span>`;
}

export function renderOverview(ctx) {
  const { model, ui } = ctx;
  if (!model.last) {
    return { html: `${brandHeader()}<div class="empty-state">${icon('pulse', 28)}<p>${esc(t('ov.empty'))}</p></div>` };
  }
  const { cur, prev, prevKey, nextKey } = ctx.period();
  const slots = series(model, cur);
  const recent = slots.filter((s) => !s.empty).slice(-15);          // KPI sparklines
  const topics = topicsOf(model, cur).slice(0, 5);
  const maxN = Math.max(1, ...topics.map((x) => x.n));
  const dE = prev ? Math.round((cur.eai - prev.eai) * 10) / 10 : null;
  const dS = prev ? Math.round((cur.esi - prev.esi) * 10) / 10 : null;
  const esiTone = cur.esi >= 5 ? 'pos' : cur.esi <= -5 ? 'neg' : '';
  const width = Math.min(ctx.root.clientWidth || 360, 560) - 62;     // card's inner width
  const share = (x) => `${(100 * x / (cur.econ || 1)).toFixed(2)}%`;
  const cover = cur.type === 'kun' ? t('ov.channels', { a: cur.ch, b: model.channelsTotal || cur.ch })
    : cur.open ? t('ov.daysOpen', { a: cur.days }) : t('ov.days', { a: cur.days, b: cur.expected });

  const html = `
  ${brandHeader()}
  <div class="seg periods" role="group" aria-label="${esc(t('period.pick'))}">${TYPES.map((p) =>
    `<button type="button" data-type="${p}" aria-pressed="${p === ui.type}">${esc(t('period.' + p))}</button>`).join('')}</div>
  <div class="prow">
    <span class="plabel">${icon('calendar', 16)}<span>${esc(periodLabel(cur))}</span></span>
    ${cur.open ? `<span class="pill pending">${esc(t('period.open'))}</span>` : ''}
    <span class="pnav">
      <button class="icon-btn sm" data-key="${esc(prevKey || '')}" ${prevKey ? '' : 'disabled'} aria-label="${esc(t('period.prev'))}">${icon('back', 16, 2)}</button>
      <button class="icon-btn sm" data-key="${esc(nextKey || '')}" ${nextKey ? '' : 'disabled'} aria-label="${esc(t('period.next'))}">${icon('chevronRight', 16, 2)}</button>
    </span>
  </div>

  <section class="kpis" aria-label="EAI, ESI">
    <div class="kpi">
      <div class="k-label">${esc(t('ov.eai'))}</div>
      <div class="k-val">${esc(num(cur.eai, 1))}<span class="k-unit">%</span></div>
      <div class="k-cmp">${prev ? delta(dE, 1, t('ov.pp'), false) : ''}<span>${esc(prev ? versus(prev) : t('ov.noPrev'))}</span></div>
      ${sparkLine(recent.map((x) => x.eai))}
      <div class="k-hint">${esc(t('ov.eaiHint'))}</div>
    </div>
    <div class="kpi">
      <div class="k-label">${esc(t('ov.esi'))}</div>
      <div class="k-val ${esiTone}">${esc(signed(cur.esi, 1))}</div>
      <div class="k-cmp">${prev ? delta(dS, 1, '', true) : ''}<span>${esc(prev ? versus(prev) : t('ov.noPrev'))}</span></div>
      ${sparkBars(recent.map((x) => x.esi))}
      <div class="k-hint">${esc(t('ov.esiHint'))}</div>
    </div>
  </section>

  <section class="card" aria-label="${esc(t('ov.dynamics'))}">
    <div class="card-title"><h2>${esc(t('ov.dynamics'))}</h2><span>${esc(['kun', 'hafta'].includes(cur.type) ? t('ov.lastN.' + cur.type, { n: slots.length }) : t('ov.by.' + cur.type))}</span></div>
    <div class="legend">
      <span><i class="l-line"></i>${esc(t('ov.legEai'))}</span><span><i class="l-pos"></i>${esc(t('ov.legEsi'))}</span>
      ${slots.some((s) => s.empty) ? `<span><i class="l-gap"></i>${esc(t('ov.legGap'))}</span>` : ''}
    </div>
    <div class="charts">${dynamics(slots, width, { eai: t('ov.chartEai'), esi: t('ov.chartEsi') })}</div>
  </section>

  <section class="card" aria-label="${esc(t('ov.tone'))}">
    <div class="card-title"><h2>${esc(t('ov.tone'))}</h2><span>${esc(t('ov.econN', { n: num(cur.econ) }))}</span></div>
    <div class="tbar"><span style="width:${share(cur.pos)}" class="b-pos"></span><span style="width:${share(cur.neu)}" class="b-neu"></span><span style="width:${share(cur.neg)}" class="b-neg"></span></div>
    <div class="tgrid">
      <div><span class="t-pos">${icon('trendUp', 14, 2)}${esc(t('ov.pos'))}</span><b>${esc(num(cur.pos))}</b></div>
      <div><span>${icon('minus', 14, 2)}${esc(t('ov.neu'))}</span><b>${esc(num(cur.neu))}</b></div>
      <div><span class="t-neg">${icon('trendDown', 14, 2)}${esc(t('ov.neg'))}</span><b>${esc(num(cur.neg))}</b></div>
    </div>
  </section>

  <section class="card cov" aria-label="${esc(t('ov.coverage'))}">
    <div><span>${esc(t('ov.coverage'))}</span><b>${esc(cover)}</b></div>
    <div><span>${esc(t('ov.posts'))}</span><b>${esc(num(cur.posts))}</b></div>
    <div><span>${esc(t('ov.ads'))}</span><b>${esc(num(cur.ads))}</b></div>
  </section>

  ${topics.length ? `
  <section class="card toptopics" aria-label="${esc(t('ov.top'))}">
    <div class="card-title"><h2>${esc(t('ov.top'))}</h2><button class="link more" data-tab="topics">${esc(t('ov.all'))}${icon('chevronRight', 16, 2)}</button></div>
    ${topics.map((x) => `
      <button class="ttrow" data-tab="topics">
        <span class="nm">${esc(topicName(x.key))}</span>
        <span class="track"><span style="width:${Math.round(100 * x.n / maxN)}%"></span></span>
        <span class="n">${esc(num(x.n))}</span>
        <span class="net ${netClass(x.esi)}">${esc(signed(x.esi))}</span>
      </button>`).join('')}
  </section>` : ''}`;

  return {
    html,
    bind(el) {
      el.querySelectorAll('[data-type]').forEach((b) => b.addEventListener('click', () => ctx.setType(b.dataset.type)));
      el.querySelectorAll('[data-key]').forEach((b) => b.addEventListener('click', () => b.dataset.key && ctx.setKey(b.dataset.key)));
      el.querySelectorAll('[data-tab]').forEach((b) => b.addEventListener('click', () => ctx.go(b.dataset.tab)));
    },
  };
}
