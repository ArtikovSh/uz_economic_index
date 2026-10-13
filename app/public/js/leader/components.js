import { esc, icon, setBack, t } from '../lib.js';
import { num, signed } from '../fmt.js';
import { animate, outCubic } from './motion.js';
import { label, TOPICS } from './model.js';

export const text = (key, vars) => esc(t(key, vars));
export const number = (key, value, format = '', cls = '') => `<span class="${cls}" data-number="${key}" data-value="${value ?? ''}" data-format="${format}">${formatNumber(value, format)}</span>`;
export function formatNumber(value, format) {
  if (value == null) return '—';
  if (format === 'signed') return signed(value);
  if (format === 'percent') return num(value) + '%';
  if (format.startsWith('leader.')) return t(format, { n: format === 'leader.points' ? signed(value) : num(value) });
  return num(value);
}
export function countUp(root, mode, old = {}) {
  const nodes = [...root.querySelectorAll('[data-number]')];
  if (mode === 'waiting') {
    nodes.forEach((el) => { el.textContent = formatNumber(el.dataset.value === '' ? null : 0, el.dataset.format); });
    return () => {};
  }
  return animate(mode === 'entry' ? 1500 : mode === 'static' ? 0 : 700, (t) => nodes.forEach((el) => {
    const end = el.dataset.value === '' ? null : +el.dataset.value;
    const start = mode === 'entry' ? 0 : old[el.dataset.number] ?? end;
    const v = end == null ? null : Math.round(start + (end - start) * outCubic(t));
    el.textContent = formatNumber(v, el.dataset.format); el.dataset.display = v ?? '';
  }));
}
export function periodPanel(ctx) {
  const { p, list, index } = ctx.period();
  return `<div class="leader-period"><div class="leader-seg" role="group" aria-label="${text('period.pick')}">
    ${['kun', 'hafta', 'oy'].map((key) => `<button data-period="${key}" aria-pressed="${ctx.ui.type === key}">${text('period.' + key)}</button>`).join('')}
    </div><div class="leader-date">${icon('calendar', 18)}<b>${esc(label(p))}</b>
    <button class="icon-btn" data-step="-1" aria-label="${text('period.prev')}" ${index <= 0 ? 'disabled' : ''}>${icon('back', 16)}</button>
    <button class="icon-btn" data-step="1" aria-label="${text('period.next')}" ${index >= list.length - 1 ? 'disabled' : ''}>${icon('chevronRight', 16)}</button></div></div>`;
}
export function topicTiles(selected) {
  return `<div class="leader-tiles">${TOPICS.map((key) => `<button data-topic="${key}" aria-pressed="${selected.includes(key)}">
    <span class="leader-check">${icon('check', 12, 3)}</span><span>${text('topics.' + key)}</span></button>`).join('')}</div>`;
}
export function channelPicker(channels, selected, allowEmpty) {
  const all = selected.length === channels.length;
  return `<label class="input-wrap">${icon('search', 18)}<input data-search aria-label="${text('leader.search')}" placeholder="${text('leader.search')}"></label>
    <div class="leader-picker-meta"><span data-selected>${text('leader.selected', { a: num(selected.length), b: num(channels.length) })}</span>
      <button class="link" data-select-all>${text(all && allowEmpty ? 'leader.clearAll' : 'leader.selectAll')}</button></div>
    <div class="leader-channels">${channels.map((c) => `<button class="leader-channel" data-channel="${esc(c.id)}" aria-pressed="${selected.includes(c.id)}">
      <span class="leader-avatar">${esc(c.name.slice(0, 2).toUpperCase())}</span><span class="leader-channel-name"><b>${esc(c.name)}</b><small>${esc(c.id)}</small></span>
      <span class="leader-check">${icon('check', 12, 3)}</span></button>`).join('')}</div>`;
}
export function bindPicker(root, channels, selected, allowEmpty, change) {
  const draw = () => {
    root.querySelector('[data-selected]').textContent = t('leader.selected', { a: num(selected.length), b: num(channels.length) });
    root.querySelector('[data-select-all]').textContent = t(selected.length === channels.length && allowEmpty ? 'leader.clearAll' : 'leader.selectAll');
    root.querySelectorAll('[data-channel]').forEach((b) => b.setAttribute('aria-pressed', selected.includes(b.dataset.channel)));
    change([...selected]);
  };
  root.querySelector('[data-search]').oninput = (e) => {
    const query = e.target.value.toLocaleLowerCase().trim();
    root.querySelectorAll('[data-channel]').forEach((b) => { b.hidden = !b.textContent.toLocaleLowerCase().includes(query); });
  };
  root.querySelector('[data-select-all]').onclick = () => { selected = selected.length === channels.length && allowEmpty ? [] : channels.map((c) => c.id); draw(); };
  root.querySelectorAll('[data-channel]').forEach((b) => { b.onclick = () => {
    const id = b.dataset.channel;
    if (selected.includes(id)) { if (!allowEmpty && selected.length === 1) return; selected = selected.filter((v) => v !== id); }
    else selected = [...selected, id];
    draw();
  }; });
}

export function sheet(ctx, title, html, mount, kind = 'sort') {
  const wrap = document.createElement('div'), opener = document.activeElement;
  wrap.className = `leader-overlay leader-${kind}-overlay`;
  wrap.innerHTML = `<button class="leader-backdrop" aria-label="${text('close')}"></button><section class="leader-dialog" role="dialog" aria-modal="true" aria-label="${esc(title)}" tabindex="-1">
    <div class="leader-dialog-head"><h2>${esc(title)}</h2><button class="link" data-done>${text('admin.doneBtn')}</button></div><div class="leader-dialog-body">${html}</div></section>`;
  ctx.root.append(wrap);
  const panel = wrap.querySelector('.leader-dialog'), bg = wrap.querySelector('.leader-backdrop');
  ctx.shell.inert = true;
  let closing = false, stop = () => {};
  const wide = () => matchMedia('(min-width: 600px)').matches;
  const draw = (progress) => {
    bg.style.opacity = progress; panel.style.opacity = wide() ? progress : 1;
    panel.style.transform = wide() ? `scale(${.96 + .04 * progress})` : `translateY(${100 * (1 - progress)}%)`;
  };
  const cleanup = () => {
    document.removeEventListener('keydown', key); wrap.remove(); ctx.shell.inert = false; setBack(ctx.back);
    const focus = opener?.isConnected && opener.matches('button,input,a[href]') ? opener : ctx.main.querySelector('[data-pick-channels],[data-sort-open]');
    focus?.focus({ preventScroll: true }); ctx.closeSheet = null;
  };
  const close = () => {
    if (closing) return; closing = true; stop();
    stop = animate(wide() ? 200 : 250, (t) => draw(1 - t * t), cleanup);
  };
  const key = (e) => {
    if (e.key === 'Escape') { e.preventDefault(); close(); }
    if (e.key !== 'Tab') return;
    const nodes = [...panel.querySelectorAll('button,input,a[href]')].filter((n) => !n.disabled && n.getClientRects().length);
    const first = nodes[0], last = nodes.at(-1);
    if (e.shiftKey && (document.activeElement === first || document.activeElement === panel)) { e.preventDefault(); last?.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
  };
  document.addEventListener('keydown', key); setBack(close); ctx.closeSheet = close;
  bg.onclick = close; wrap.querySelector('[data-done]').onclick = close;
  mount(panel, close); panel.querySelector('input,button')?.focus({ preventScroll: true });
  stop = animate(wide() ? 200 : 300, (t) => draw(outCubic(t)));
  return close;
}
