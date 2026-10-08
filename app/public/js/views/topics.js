// Topics: tone split and ESI per topic, and how the topics add up to the period's ESI.
import { esc, icon, t } from '../lib.js';
import { num, periodLabel, signed } from '../fmt.js';
import { topicsOf } from '../stats.js';
import { netClass, topicName } from './overview.js';

export function renderTopics(ctx) {
  const { model, ui } = ctx;
  const head = (sub) => `
  <header class="page-hdr">
    <div><h1>${esc(t('tabs.topics'))}</h1>${sub ? `<p>${esc(sub)}</p>` : ''}</div>
    <button class="pick-btn" id="ptype" aria-label="${esc(t('period.pick'))}">${esc(t('period.' + ui.type))}${icon('chevronDown', 16, 2)}</button>
  </header>`;
  if (!model.last) {
    return { html: `${head('')}<div class="empty-state">${icon('layers', 28)}<p>${esc(t('ov.empty'))}</p></div>`, bind: bindHead };
  }
  const { cur } = ctx.period();
  const rows = topicsOf(model, cur);
  const maxN = Math.max(1, ...rows.map((x) => x.n));
  const parts = rows.map((x) => ({ key: x.key, v: 100 * (x.wpos - x.wneg) / cur.econ }))
    .filter((x) => Math.abs(x.v) > 0.005).sort((a, b) => b.v - a.v);
  const maxV = Math.max(0.1, ...parts.map((x) => Math.abs(x.v)));

  const html = `
  ${head(t('tp.sub', { period: periodLabel(cur), n: num(cur.econ) }))}
  <section class="card" aria-label="${esc(t('tp.byTone'))}">
    <h2>${esc(t('tp.byTone'))}</h2>
    <div class="legend"><span><i class="l-pos"></i>${esc(t('ov.pos'))}</span><span><i class="l-neu"></i>${esc(t('ov.neu'))}</span><span><i class="l-neg"></i>${esc(t('ov.neg'))}</span></div>
    <div class="tl-head"><span>${esc(t('tp.head'))}</span><span>ESI</span></div>
    ${rows.map((x) => `
      <button class="tlrow" data-topic="${esc(x.key)}">
        <span class="tl-main">
          <span class="tl-name"><span class="tl-label">${esc(topicName(x.key))}</span>
            <span class="tl-tones" aria-label="${esc(`${t('ov.pos')} ${x.pos}, ${t('ov.neu')} ${x.neu}, ${t('ov.neg')} ${x.neg}`)}">
              <span class="t-pos">${esc(num(x.pos))}</span><i>|</i><span class="t-neu">${esc(num(x.neu))}</span><i>|</i><span class="t-neg">${esc(num(x.neg))}</span></span>
            <b>${esc(num(x.n))}</b></span>
          <span class="tl-track"><span style="width:${Math.round(100 * x.n / maxN)}%">
            <i class="b-pos" style="flex:${x.pos}"></i><i class="b-neu" style="flex:${x.neu}"></i><i class="b-neg" style="flex:${x.neg}"></i></span></span>
        </span>
        <span class="net ${netClass(x.esi)}">${esc(signed(x.esi))}</span>
      </button>`).join('')}
  </section>

  <section class="card" aria-label="${esc(t('tp.how'))}">
    <h2>${esc(t('tp.how'))}</h2>
    <p class="note how">${esc(t('tp.howText', { n: num(cur.econ) }))}</p>
    ${parts.map((x) => `
      <div class="ctrow">
        <span>${esc(topicName(x.key))}</span>
        <span class="ct-track"><i class="${x.v > 0 ? 'b-pos right' : 'b-neg left'}" style="width:${(50 * Math.abs(x.v) / maxV).toFixed(1)}%"></i></span>
        <b class="${x.v > 0 ? 't-pos' : 't-neg'}">${esc(signed(x.v, 1))}</b>
      </div>`).join('')}
    <div class="ct-total"><span>${esc(t('tp.total'))}</span><b class="${netClass(cur.esi) === 'neg' ? 't-neg' : 't-pos'}">${esc(signed(cur.esi, 1))}</b></div>
  </section>`;

  function bindHead(el) {
    el.querySelector('#ptype').addEventListener('click', () => ctx.pickType());
  }
  return {
    html,
    bind(el) {
      bindHead(el);
      el.querySelectorAll('[data-topic]').forEach((b) => b.addEventListener('click', () =>
        ctx.go('posts', { topics: [b.dataset.topic] })));
    },
  };
}

export function renderMethod() {
  const card = (ic, tone, title, formula, text) => `
  <section class="card mcard">
    <div class="card-head"><span class="tile ${tone}">${icon(ic, 18, 1.9)}</span><h2>${esc(title)}</h2></div>
    <div class="formula">${esc(formula)}</div>
    <p class="note">${esc(text)}</p>
  </section>`;
  return {
    html: `
    <header class="page-hdr"><div><h1>${esc(t('tabs.method'))}</h1><p>${esc(t('md.sub'))}</p></div></header>
    ${card('target', '', t('md.eai'), t('md.eaiF'), t('md.eaiText'))}
    ${card('pulse', 'pos', t('md.esi'), t('md.esiF'), t('md.esiText'))}`,
  };
}
