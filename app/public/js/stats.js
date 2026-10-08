// Period arithmetic on the daily counts, the same sums and rounding as indicator.py.
export const TYPES = ['kun', 'hafta', 'oy', 'chorak', 'yil'];
const WINDOW = { kun: 30, hafta: 12 };                  // chart length for days and weeks
const SUB = { oy: 'kun', chorak: 'hafta', yil: 'oy' };   // longer periods are charted by their parts

const pad = (n) => String(n).padStart(2, '0');
const iso = (d) => `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
const date = (s) => new Date(Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10)));
export const addDays = (s, n) => { const d = date(s); d.setUTCDate(d.getUTCDate() + n); return iso(d); };
export const dayCount = (a, b) => Math.round((date(b) - date(a)) / 864e5) + 1;

/** Python's round(x, 1): ties go to the even digit. */
function round1(x) {
  const y = x * 10, r = Math.round(y);
  return (Math.abs(y % 1) === 0.5 && r % 2 !== 0 ? r - 1 : r) / 10;
}

function isoWeek(monday) {
  const th = date(addDays(monday, 3));                 // the Thursday decides the ISO year
  const jan1 = Date.UTC(th.getUTCFullYear(), 0, 1);
  return Math.ceil(((th - jan1) / 864e5 + 1) / 7);
}

/** The period of the given type that contains day ("YYYY-MM-DD"), like indicator.period_of. */
export function periodOf(day, type) {
  const d = date(day), y = d.getUTCFullYear(), m = d.getUTCMonth();
  if (type === 'kun') return { type, key: day, start: day, end: day };
  if (type === 'hafta') {
    const start = addDays(day, -((d.getUTCDay() + 6) % 7));
    return { type, key: start, start, end: addDays(start, 6), week: isoWeek(start) };
  }
  if (type === 'oy') return { type, key: day.slice(0, 7), start: iso(new Date(Date.UTC(y, m, 1))), end: iso(new Date(Date.UTC(y, m + 1, 0))) };
  if (type === 'chorak') {
    const q = Math.floor(m / 3);
    return { type, key: `${y}-Q${q + 1}`, start: iso(new Date(Date.UTC(y, 3 * q, 1))), end: iso(new Date(Date.UTC(y, 3 * q + 3, 0))) };
  }
  return { type, key: String(y), start: `${y}-01-01`, end: `${y}-12-31` };
}

export function buildModel(stats) {
  const days = (stats.days || []).map(([d, posts, nonad, econ, pos, neg, ch]) => ({ d, posts, nonad, econ, pos, neg, ch }));
  return {
    days, has: new Set(days.map((x) => x.d)), topics: stats.topics || [],
    first: days.length ? days[0].d : null, last: days.length ? days[days.length - 1].d : null,
    channels: stats.channels || [], channelsTotal: stats.channels_total || 0,
    chanDays: stats.chan_days || [],
  };
}

/** Posts of each channel within [from, to]: Map(channel id -> count). */
export function channelCounts(model, from, to) {
  const out = new Map(model.channels.map((c) => [c.id, 0]));
  model.chanDays.forEach(([i, c, n]) => {
    const d = model.days[i].d;
    if (d >= from && d <= to) out.set(model.channels[c].id, (out.get(model.channels[c].id) || 0) + n);
  });
  return out;
}

/** Periods of a type that have data, oldest first. */
export function periods(model, type) {
  const seen = new Map();
  model.days.forEach((x) => { const p = periodOf(x.d, type); if (!seen.has(p.key)) seen.set(p.key, p); });
  return [...seen.values()];
}

/** Totals and indices of one period; null when it has no data. */
export function aggregate(model, p) {
  const t = { posts: 0, nonad: 0, econ: 0, pos: 0, neg: 0, days: 0, ch: 0, lastDay: null };
  model.days.forEach((x) => {
    if (x.d < p.start || x.d > p.end) return;
    t.posts += x.posts; t.nonad += x.nonad; t.econ += x.econ; t.pos += x.pos; t.neg += x.neg;
    t.days += 1; t.ch = x.ch; t.lastDay = x.d;
  });
  if (!t.days) return null;
  return {
    ...p, ...t, neu: t.econ - t.pos - t.neg, ads: t.posts - t.nonad,
    expected: dayCount(p.start, p.end), open: p.end > model.last,
    eai: t.nonad ? round1(100 * t.econ / t.nonad) : null,
    esi: t.econ ? round1(100 * (t.pos - t.neg) / t.econ) : null,
  };
}

/** The selected period (by key, else the latest), the one before it with data, and neighbours. */
export function locate(model, type, key) {
  const list = periods(model, type);
  let i = list.findIndex((p) => p.key === key);
  if (i < 0) i = list.length - 1;
  return {
    cur: aggregate(model, list[i]), prev: i > 0 ? aggregate(model, list[i - 1]) : null,
    prevKey: i > 0 ? list[i - 1].key : null, nextKey: i < list.length - 1 ? list[i + 1].key : null,
  };
}

const empty = (p) => ({ ...p, eai: null, esi: null, empty: true });

/** Chart slots (empty where there is no data). A day or a week is shown against the days or weeks
 *  before it; a month, quarter or year by its own days, weeks or months. */
export function series(model, p) {
  const out = [];
  if (SUB[p.type]) {
    const end = p.end < model.last ? p.end : model.last;
    const first = periodOf(model.first, SUB[p.type]).start;           // nothing before the series began
    for (let day = first > p.start ? first : p.start; day <= end;) {
      const q = periodOf(day, SUB[p.type]);
      const part = { ...q, start: q.start < p.start ? p.start : q.start, end: q.end > p.end ? p.end : q.end };
      out.push(aggregate(model, part) || empty(part));
      day = addDays(q.end, 1);
    }
    return out;
  }
  let cur = p;
  for (let k = 0; k < WINDOW[p.type] && cur.end >= model.first; k += 1) {
    out.unshift(aggregate(model, cur) || empty(cur));
    cur = periodOf(addDays(cur.start, -1), p.type);
  }
  return out;
}

/** Counted posts by topic within the period: [{key, n, pos, neg, neu, esi, wpos, wneg}] by size.
 *  A post counts in each of its topics; wpos/wneg split its ESI share between them, so the
 *  topics' shares add up to ESI. */
export function topicsOf(model, p) {
  const acc = new Map();
  model.topics.forEach(([i, key, n, pos, neg, wpos = pos, wneg = neg]) => {
    const d = model.days[i].d;
    if (d < p.start || d > p.end) return;
    const t = acc.get(key) || { key, n: 0, pos: 0, neg: 0, wpos: 0, wneg: 0 };
    t.n += n; t.pos += pos; t.neg += neg; t.wpos += wpos; t.wneg += wneg;
    acc.set(key, t);
  });
  return [...acc.values()].map((t) => ({ ...t, neu: t.n - t.pos - t.neg, esi: Math.round(100 * (t.pos - t.neg) / t.n) }))
    .sort((a, b) => b.n - a.n || a.key.localeCompare(b.key));
}
