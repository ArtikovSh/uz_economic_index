// Dashboard (interim: the current daily views, restyled; replaced by the new design next).
import { api, esc, fmtDate, haptic, icon, logo, setBack, t } from './lib.js';

const moodColor = (s) => (s > 0.15 ? 'var(--pos)' : s < -0.15 ? 'var(--negFill)' : 'var(--neu)');
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function arc(cx, cy, r, a0, a1) {
  const p = (a) => [cx + r * Math.cos(Math.PI * a / 180), cy - r * Math.sin(Math.PI * a / 180)];
  const [x0, y0] = p(a0), [x1, y1] = p(a1);
  return `M ${x0} ${y0} A ${r} ${r} 0 ${Math.abs(a1 - a0) > 180 ? 1 : 0} 1 ${x1} ${y1}`;
}
function gauge(value, min, max, color) {
  const v = Math.max(min, Math.min(max, value)), ang = 180 - 180 * (v - min) / (max - min);
  return `<svg viewBox="0 0 150 88" width="100%" aria-hidden="true">
    <path d="${arc(75, 80, 62, 180, 0)}" fill="none" style="stroke:var(--surface2)" stroke-width="11" stroke-linecap="round"/>
    <path d="${arc(75, 80, 62, 180, ang)}" fill="none" style="stroke:${color}" stroke-width="11" stroke-linecap="round"/></svg>`;
}

export function renderDashboard(root, nav, state) {
  setBack(null);
  const D = state.data || {};
  const me = D.me || {};
  let tab = 'over', period = 30, postFilter = null, chart = null;
  let fx = ' fade';                    // entry animation: on tab changes, not on every filter tap

  const header = () => `
    <header class="topbar">
      <div class="brand-sm">${logo(34)}<div><b>${esc(t('dash.title'))}</b><span>${esc(t('dash.sub'))}</span></div></div>
      <div class="top-actions">
        ${me.is_admin ? `<button class="icon-btn" id="toAdmin" aria-label="${esc(t('dash.users'))}">${icon('users', 18)}</button>` : ''}
        ${me.owner ? '' : `<button class="icon-btn" id="account" aria-label="${esc(t('dash.account'))}">${icon('user', 18)}</button>`}
      </div>
    </header>`;

  function openAccount() {
    const until = me.expires_at ? t('admin.until', { d: fmtDate(me.expires_at) }) : t('admin.noExpiry');
    const wrap = document.createElement('div');
    wrap.className = 'sheet-wrap';
    wrap.setAttribute('role', 'dialog');
    wrap.setAttribute('aria-modal', 'true');
    wrap.setAttribute('aria-label', t('dash.account'));
    wrap.innerHTML = `
      <button class="backdrop" data-close aria-label="${esc(t('close'))}"></button>
      <div class="sheet">
        <span class="grip"></span>
        <div class="head"><h2 class="mono">${esc(me.login)}</h2>
          <button class="icon-btn" data-close aria-label="${esc(t('close'))}">${icon('close', 16, 2.2)}</button></div>
        <p class="note">${esc(t('roles.' + me.role))} · ${esc(until)}</p>
        <div class="menu"><button class="danger" data-logout><span class="ic">${icon('logout', 18)}</span>${esc(t('dash.logout'))}</button></div>
      </div>`;
    root.appendChild(wrap);
    wrap.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', () => { haptic(); wrap.remove(); }));
    wrap.querySelector('[data-logout]').addEventListener('click', async () => {
      haptic();
      try { await api('logout'); } catch (e) { /* the reload shows the state */ }
      nav.reload();
    });
  }

  function overview() {
    const L = D.latest || {}, P = D.prev || {}, W = D.week;
    const eai = L.eai == null ? null : L.eai, esi = L.esi == null ? null : L.esi;
    const dE = (eai == null || P.eai == null) ? 0 : Math.round((eai - P.eai) * 10) / 10;
    const dS = (esi == null || P.esi == null) ? 0 : Math.round(esi - P.esi);
    const delta = (v) => `<span style="color:${v > 0 ? 'var(--pos)' : v < 0 ? 'var(--neg)' : 'var(--muted)'}">${v > 0 ? '▲' : v < 0 ? '▼' : '–'} ${Math.abs(v)}</span>`;
    const esiCol = esi == null ? 'var(--muted)' : esi >= 5 ? 'var(--pos)' : esi <= -5 ? 'var(--neg)' : 'var(--ink)';
    const fmtE = (v) => (v == null ? '—' : v.toFixed(1)), fmtS = (v) => (v == null ? '—' : (v > 0 ? '+' : '') + Math.round(v));
    const s = D.sentiment || { pos: 0, neu: 0, neg: 0 }, tot = (s.pos + s.neu + s.neg) || 1;
    const topT = (D.topics || []).slice(0, 5), maxN = Math.max(1, ...topT.map((x) => x.n));
    return `
    <div class="gauges${fx}">
      <div class="g">${gauge(eai || 0, 0, 100, 'var(--primary)')}
        <div class="val">${fmtE(eai)}<span style="font-size:15px">%</span></div><div class="lab">E’tibor · EAI</div>
        <div class="delta">${delta(dE)}</div><div class="hint">iqtisodiy xabarlar ulushi</div></div>
      <div class="g">${gauge(esi || 0, -100, 100, esiCol)}
        <div class="val" style="color:${esiCol}">${fmtS(esi)}</div><div class="lab">Kayfiyat · ESI</div>
        <div class="delta">${delta(dS)}</div><div class="hint">ijobiy − salbiy · 0 = neytral</div></div>
    </div>
    ${W ? `<div class="card${fx}"><p class="st">Hafta ${esc(W.s.slice(5))} – ${esc(W.e.slice(5))}</p>
      <div class="sleg"><span>EAI <b>${fmtE(W.eai)}%</b></span><span>ESI <b>${fmtS(W.esi)}</b></span></div></div>` : ''}
    <div class="card${fx}"><p class="st">Dinamika</p>
      <div class="seg">${[7, 30, 90].map((p) => `<button type="button" data-p="${p}" aria-pressed="${p === period}">${p} kun</button>`).join('')}</div>
      <canvas id="trend" height="150" aria-label="EAI va ESI dinamikasi" role="img"></canvas></div>
    <div class="card${fx}"><p class="st">Ohang taqsimoti — ${esc(D.date || '')}</p>
      <div class="sdist"><span style="width:${100 * s.pos / tot}%;background:var(--pos)"></span>
        <span style="width:${100 * s.neu / tot}%;background:var(--neu)"></span>
        <span style="width:${100 * s.neg / tot}%;background:var(--negFill)"></span></div>
      <div class="sleg"><span><i style="background:var(--pos)"></i>Ijobiy <b>${s.pos}</b></span>
        <span><i style="background:var(--neu)"></i>Neytral <b>${s.neu}</b></span>
        <span><i style="background:var(--negFill)"></i>Salbiy <b>${s.neg}</b></span></div></div>
    ${topT.length ? `<div class="card${fx}"><p class="st">Asosiy mavzular</p>${topT.map((x) => `
      <div class="trow" data-topic="${esc(x.primary_topic)}"><div class="nm">${esc(x.name)}</div>
        <div class="track"><div class="fill" style="width:${Math.round(100 * x.n / maxN)}%;background:${moodColor(x.s)}"></div></div>
        <div class="cnt">${x.n}</div></div>`).join('')}</div>` : ''}`;
  }

  function topicsView() {
    const tp = D.topics || [];
    if (!tp.length) return '<div class="center">Bu kun uchun mavzu topilmadi.</div>';
    const maxN = Math.max(1, ...tp.map((x) => x.n));
    return `<p class="st${fx}">Mavzular — ${esc(D.date || '')}</p>` + tp.map((x) => `
      <div class="card${fx} trow" data-topic="${esc(x.primary_topic)}" style="margin-top:8px">
        <div class="nm" style="min-width:120px">${esc(x.name)}</div>
        <div class="track"><div class="fill" style="width:${Math.round(100 * x.n / maxN)}%;background:${moodColor(x.s)}"></div></div>
        <div style="text-align:right"><div class="cnt">${x.n}</div>
          <div style="font-size:10.5px;color:var(--muted)">${x.s > 0 ? '+' : ''}${x.s}</div></div></div>`).join('');
  }

  function postsView() {
    const all = D.top || [];
    const posts = postFilter ? all.filter((p) => p.primary_topic === postFilter) : all;
    const topics = [...new Set(all.map((p) => p.primary_topic))];
    const chips = `<div class="filters${fx}"><button type="button" data-f="" aria-pressed="${!postFilter}">Hammasi</button>` +
      topics.map((x) => `<button type="button" data-f="${esc(x)}" aria-pressed="${postFilter === x}">${esc(all.find((p) => p.primary_topic === x).topic)}</button>`).join('') + '</div>';
    if (!posts.length) return chips + '<div class="center">Post topilmadi.</div>';
    return chips + posts.map((p) => `
      <a class="post${fx}" href="${esc(p.link)}" data-link="${esc(p.link)}">
        <div class="top"><span class="tone" style="background:${moodColor(p.sentiment)}"></span>
          <span class="tag">${esc(p.topic)}</span>
          <span class="ch">${esc(p.channel)} · ${icon('eye', 13)} ${esc(p.views)}</span></div>
        <div class="tx">${esc(p.raw_text)}</div></a>`).join('');
  }

  function drawChart() {
    const el = root.querySelector('#trend');
    if (!el || !window.Chart) return;
    const dd = (D.daily || []).slice(-period), muted = css('--muted'), primary = css('--primary'), pos = css('--pos');
    if (chart) chart.destroy();
    chart = new window.Chart(el, {
      type: 'line',
      data: { labels: dd.map((x) => x.d.slice(5)), datasets: [
        { label: 'E’tibor (EAI, %)', data: dd.map((x) => x.eai), yAxisID: 'y', borderColor: primary, tension: 0.35, pointRadius: 0, borderWidth: 2 },
        { label: 'Kayfiyat (ESI)', data: dd.map((x) => x.esi), yAxisID: 'y1', borderColor: pos, tension: 0.35, pointRadius: 0, borderWidth: 2 },
      ] },
      options: { responsive: true, interaction: { intersect: false, mode: 'index' },
        plugins: { legend: { labels: { boxWidth: 10, color: muted, font: { size: 11 } } } },
        scales: { x: { ticks: { color: muted, maxTicksLimit: 6, font: { size: 9 } }, grid: { display: false } },
          y: { min: 0, max: 100, ticks: { color: muted, font: { size: 9 } }, grid: { color: css('--line') } },
          y1: { min: -100, max: 100, position: 'right', ticks: { color: muted, font: { size: 9 } }, grid: { display: false } } } },
    });
  }

  function draw(animate = true) {
    fx = animate ? ' fade' : '';
    const tabs = [['over', 'home', 'Umumiy'], ['topics', 'layers', 'Mavzular'], ['posts', 'news', 'Postlar']];
    root.innerHTML = `
    <main class="screen dash">
      ${header()}
      ${tab === 'over' ? overview() : tab === 'topics' ? topicsView() : postsView()}
    </main>
    <nav class="tabbar" aria-label="Bo‘limlar">${tabs.map(([id, ic, label]) =>
      `<button type="button" data-tab="${id}" ${tab === id ? 'aria-current="page"' : ''}>${icon(ic, 21)}${label}</button>`).join('')}</nav>`;
    if (tab === 'over') drawChart();
    bind();
  }

  function bind() {
    const on = (sel, fn) => root.querySelectorAll(sel).forEach((el) => el.addEventListener('click', (e) => fn(el, e)));
    on('[data-tab]', (el) => { haptic(); tab = el.dataset.tab; postFilter = null; draw(); });
    on('[data-p]', (el) => { haptic(); period = Number(el.dataset.p); draw(false); });
    on('[data-topic]', (el) => { haptic(); postFilter = el.dataset.topic; tab = 'posts'; draw(); });
    on('[data-f]', (el) => { haptic(); postFilter = el.dataset.f || null; draw(false); });
    on('[data-link]', (el, e) => {
      e.preventDefault(); haptic();
      try { window.Telegram.WebApp.openTelegramLink(el.dataset.link); } catch (err) { window.open(el.dataset.link); }
    });
    const admin = root.querySelector('#toAdmin');
    if (admin) admin.addEventListener('click', () => { haptic(); nav.go('admin'); });
    const account = root.querySelector('#account');
    if (account) account.addEventListener('click', () => { haptic(); openAccount(); });
  }

  draw();
}
