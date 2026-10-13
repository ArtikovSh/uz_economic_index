import { addDays, dayCount, periodOf } from '../stats.js';
import { dayMonth, monthName, periodLabel, range } from '../fmt.js';

export const TOPICS = ['central_bank', 'currency_fx', 'prices_inflation', 'banking_finance', 'fiscal', 'macro',
  'trade', 'business', 'labour_income', 'energy_utility', 'transport', 'construction_realty'];
export const TONES = ['pos', 'neu', 'neg'];
export const selectedTopics = (prefs) => prefs.topics.length ? prefs.topics : TOPICS;
export const selectedChannels = (ctx) => ctx.prefs.channels.length ? ctx.prefs.channels : ctx.data.channels.map((c) => c.id);
export const periods = (data, type) => [...new Map(data.days.map(([day]) => {
  const p = periodOf(day, type); return [p.key, p];
})).values()];
export const previous = (p) => periodOf(addDays(p.start, -1), p.type);
export function label(p, short = false) {
  if (!p) return '—';
  if (p.type === 'kun') return short ? dayMonth(p.start) : periodLabel(p).replace(' ' + p.start.slice(0, 4), '');
  if (p.type === 'hafta') return range(p.start, p.end);
  return monthName(+p.start.slice(5, 7) - 1) + (short ? '' : ', ' + p.start.slice(0, 4));
}

export function shares(counts) {
  const total = counts.reduce((a, b) => a + b, 0);
  if (!total) return [0, 0, 0];
  const raw = counts.map((v) => 100 * v / total), out = raw.map(Math.floor);
  const order = raw.map((v, i) => [v - out[i], i]).sort((a, b) => b[0] - a[0] || a[1] - b[1]);
  for (let n = 100 - out.reduce((a, b) => a + b, 0), i = 0; i < n; i++) out[order[i][1]]++;
  return out;
}

export function aggregate(data, p, topics) {
  const indices = new Set(), result = { posts: 0, tones: [0, 0, 0], days: p ? dayCount(p.start, p.end) : 0, channels: 0 };
  data.days.forEach(([day, posts], i) => {
    if (p && day >= p.start && day <= p.end) { indices.add(i); result.posts += posts; }
  });
  result.channels = new Set((data.channel_days || []).filter(([i]) => indices.has(i)).map(([, ch]) => ch)).size;
  result.topics = topics.map((key) => ({ key, tones: [0, 0, 0] }));
  const byTopic = new Map(result.topics.map((r) => [r.key, r]));
  data.topics.forEach(([i, topic, ...counts]) => {
    if (indices.has(i) && byTopic.has(topic)) counts.forEach((v, j) => { byTopic.get(topic).tones[j] += v; });
  });
  const chosen = new Set(topics);
  (data.groups || []).forEach(([i, group, ...counts]) => {
    if (indices.has(i) && group.some((topic) => chosen.has(topic))) counts.forEach((v, j) => { result.tones[j] += v; });
  });
  result.total = result.tones.reduce((a, b) => a + b, 0);
  result.mood = result.total ? Math.round(100 * (result.tones[0] - result.tones[2]) / result.total) : null;
  result.shares = shares(result.tones);
  result.topics.forEach((r) => { r.total = r.tones.reduce((a, b) => a + b, 0); });
  result.topics.sort((a, b) => b.total - a.total);
  return result;
}
