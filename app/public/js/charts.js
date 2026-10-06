// Small SVG charts drawn to the card's width; colours come from the CSS tokens.
import { esc } from './lib.js';
import { num, signed, tick } from './fmt.js';

const f1 = (v) => v.toFixed(1);

/** Nice axis step for a span (1, 2, 5 × 10^k). */
function step(span, parts) {
  const raw = span / parts, mag = 10 ** Math.floor(Math.log10(raw || 1));
  return [1, 2, 5, 10].map((k) => k * mag).find((s) => s >= raw) || raw;
}

/** EAI sparkline (line) for the KPI card. */
export function sparkLine(vals) {
  const v = vals.filter((x) => x != null);
  if (v.length < 2) return '';
  const lo = Math.min(...v), hi = Math.max(...v), span = hi - lo || 1;
  const d = v.map((x, i) => `${i ? 'L' : 'M'}${f1(140 * i / (v.length - 1))} ${f1(30 - 26 * (x - lo) / span)}`).join(' ');
  return `<svg width="100%" height="34" viewBox="0 0 140 34" preserveAspectRatio="none" aria-hidden="true">
    <path d="${d}" fill="none" class="c-eai" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/></svg>`;
}

function bars(vals, x, w, zero, scale) {
  let pos = '', neg = '';
  vals.forEach((v, i) => {
    if (v == null) return;
    const h = Math.max(1.5, Math.abs(v) * scale), x0 = f1(x(i) - w / 2);
    if (v >= 0) pos += `M${x0} ${f1(zero - h)}h${w}v${f1(h)}h-${w}Z`;
    else neg += `M${x0} ${zero}h${w}v${f1(h)}h-${w}Z`;
  });
  return `<path d="${pos}" class="c-pos"/><path d="${neg}" class="c-neg"/>`;
}

/** ESI sparkline (bars around zero) for the KPI card. */
export function sparkBars(vals) {
  const v = vals.filter((x) => x != null);
  if (v.length < 2) return '';
  const hasPos = v.some((x) => x > 0), hasNeg = v.some((x) => x < 0);
  const zero = hasPos && hasNeg ? 17 : hasNeg ? 3 : 31;
  const room = hasPos && hasNeg ? 15 : 28, m = Math.max(...v.map(Math.abs)) || 1;
  const n = v.length, w = 6, x = (i) => 3 + w / 2 + i * ((134 - w) / (n - 1));
  return `<svg width="100%" height="34" viewBox="0 0 140 34" preserveAspectRatio="none" aria-hidden="true">
    <line x1="0" x2="140" y1="${zero}" y2="${zero}" class="c-line"/>${bars(v, x, w, zero, room / m)}</svg>`;
}

/** Gap bands where slots have no data. */
function gaps(slots, x, slotW, h) {
  let out = '', i = 0;
  while (i < slots.length) {
    if (!slots[i].empty) { i += 1; continue; }
    let j = i;
    while (j + 1 < slots.length && slots[j + 1].empty) j += 1;
    out += `<rect x="${f1(x(i) - slotW / 2)}" y="0" width="${f1((j - i + 1) * slotW)}" height="${h}" rx="4" class="c-gap"/>`;
    i = j + 1;
  }
  return out;
}

/** Dinamika: EAI line over the slots, then ESI bars with the period ticks. */
export function dynamics(slots, width, labels) {
  const W = Math.max(240, Math.round(width)), plot = W - 34, n = slots.length;
  const slotW = plot / n, x = (i) => slotW * (i + 0.5);
  const eai = slots.map((s) => s.eai), esi = slots.map((s) => s.esi);
  const ev = eai.filter((v) => v != null);

  // EAI: range padded to nice steps, three gridlines
  let lo = Math.min(...ev), hi = Math.max(...ev);
  const st = step(Math.max(hi - lo, 4), 4);
  lo = Math.floor(lo / st) * st; hi = Math.ceil(hi / st) * st;
  if (hi - lo < 2 * st) hi = lo + 2 * st;
  const H1 = 112, yE = (v) => 10 + (hi - v) / (hi - lo) * 92;
  let path = '', pen = false;
  eai.forEach((v, i) => {
    if (v == null) { pen = false; return; }
    path += `${pen ? 'L' : 'M'}${f1(x(i))} ${f1(yE(v))} `;
    pen = true;
  });
  const lastI = eai.map((v, i) => (v == null ? -1 : i)).filter((i) => i >= 0).pop();
  const grid1 = [hi, (hi + lo) / 2, lo].map((v, k) => `
    <line x1="0" x2="${f1(plot)}" y1="${f1(yE(v))}" y2="${f1(yE(v))}" class="c-line" ${k < 2 ? 'stroke-dasharray="2 4"' : ''}/>
    <text x="${W}" y="${f1(yE(v) + 4)}" text-anchor="end" class="c-txt">${esc(num(v, Number.isInteger(v) ? 0 : 1))}%</text>`).join('');

  // ESI: symmetric scale when both signs occur
  const sv = esi.filter((v) => v != null), m = Math.max(10, ...sv.map(Math.abs));
  const top = step(m, 1);
  const both = sv.some((v) => v < 0) && sv.some((v) => v > 0), down = !both && sv.every((v) => v <= 0);
  const zero = both ? 37 : down ? 6 : 68, room = both ? 30 : 60;
  const yS = (v) => zero - v / top * room;
  const marks = both ? [top, 0, -top] : down ? [0, -top] : [top, 0];
  const grid2 = marks.map((v) => `
    <line x1="0" x2="${f1(plot)}" y1="${f1(yS(v))}" y2="${f1(yS(v))}" class="${v === 0 ? 'c-axis' : 'c-line'}" ${v === 0 ? '' : 'stroke-dasharray="2 4"'}/>
    <text x="${W}" y="${f1(yS(v) + 4)}" text-anchor="end" class="c-txt">${esc(signed(v))}</text>`).join('');
  const bw = Math.max(2, Math.min(8, slotW * 0.6));
  const ticks = [...new Set([0, 1, 2, 3, 4].map((k) => Math.round(k * (n - 1) / 4)))].map((i) => {
    const anchor = n === 1 ? 'middle' : i === 0 ? 'start' : i === n - 1 ? 'end' : 'middle';
    const tx = anchor === 'start' ? x(i) - slotW / 2 : anchor === 'end' ? x(i) + slotW / 2 : x(i);
    return `<text x="${f1(Math.max(0, tx))}" y="88" text-anchor="${anchor}" class="c-txt">${esc(tick(slots[i]))}</text>`;
  }).join('');

  return `
  <svg width="${W}" height="${H1}" viewBox="0 0 ${W} ${H1}" role="img" aria-label="${esc(labels.eai)}" class="chart">
    ${gaps(slots, x, slotW, H1)}${grid1}
    <path d="${path}" fill="none" class="c-eai" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
    ${lastI != null ? `<circle cx="${f1(x(lastI))}" cy="${f1(yE(eai[lastI]))}" r="4" class="c-dot"/>` : ''}
  </svg>
  <svg width="${W}" height="92" viewBox="0 0 ${W} 92" role="img" aria-label="${esc(labels.esi)}" class="chart">
    ${gaps(slots, x, slotW, 74)}${grid2}${bars(esi, x, bw, zero, room / top)}${ticks}
  </svg>`;
}
