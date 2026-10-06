// Numbers, dates and period names in the three interface languages.
import { lang } from './lib.js';

const L = {
  uz: {
    months: ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun', 'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr'],
    short: ['yan', 'fev', 'mar', 'apr', 'may', 'iyn', 'iyl', 'avg', 'sen', 'okt', 'noy', 'dek'],
    weekdays: ['dushanba', 'seshanba', 'chorshanba', 'payshanba', 'juma', 'shanba', 'yakshanba'],
    wd2: ['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'],
    thousand: 'ming', million: 'mln',
  },
  ru: {
    months: ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь'],
    gen: ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'],
    dat: ['январю', 'февралю', 'марту', 'апрелю', 'маю', 'июню', 'июлю', 'августу', 'сентябрю', 'октябрю', 'ноябрю', 'декабрю'],
    short: ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'],
    weekdays: ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье'],
    wd2: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
    thousand: 'тыс.', million: 'млн',
  },
  en: {
    months: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
    short: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
    weekdays: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
    wd2: ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'],
    thousand: 'K', million: 'M',
  },
};
const ROMAN = ['I', 'II', 'III', 'IV'];
const loc = () => L[lang()] || L.uz;
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const MINUS = '−';

// ------------------------------------------------------------- numbers ----
const nf = (digits) => new Intl.NumberFormat(lang() === 'en' ? 'en-US' : 'ru-RU',
  { minimumFractionDigits: digits, maximumFractionDigits: digits });
export const num = (v, digits = 0) => (v == null ? '—' : (v < 0 ? MINUS : '') + nf(digits).format(Math.abs(v)));
export const signed = (v, digits = 0) => (v == null ? '—' : (v > 0 ? '+' : v < 0 ? MINUS : '') + nf(digits).format(Math.abs(v)));
export function views(n) {
  const l = loc(), en = lang() === 'en';
  if (n >= 1e6) return nf(1).format(n / 1e6) + (en ? '' : ' ') + l.million;
  if (n >= 1e3) return nf(1).format(n / 1e3) + (en ? '' : ' ') + l.thousand;
  return String(n);
}

// --------------------------------------------------------------- dates ----
const parts = (s) => [+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10)];
const weekday = (s) => (new Date(Date.UTC(...parts(s))).getUTCDay() + 6) % 7;
export const weekdayShort = () => loc().wd2;
export const monthName = (m) => cap(loc().months[m]);

/** "4-oktabr" / "4 октября" / "4 Oct". */
export function dayMonth(s, full = true) {
  const [, m, d] = parts(s), l = loc(), code = lang();
  if (code === 'uz') return `${d}-${full ? l.months[m] : l.short[m]}`;
  if (code === 'ru') return `${d} ${full ? l.gen[m] : l.short[m]}`;
  return `${d} ${full ? l.months[m] : l.short[m]}`;
}
/** "4-oktabr 2026" / "4 октября 2026" / "4 October 2026". */
export const dayFull = (s) => `${dayMonth(s)} ${s.slice(0, 4)}`;
/** "5-sen" / "5 сен" / "5 Sep" (axis ticks, post times). */
export const dayShort = (s) => dayMonth(s, false);

/** "21–27 sentabr" or "28 sentabr – 4 oktabr" (and the same in ru/en). */
export function range(a, b) {
  if (a === b) return dayMonth(a);
  const [, ma, da] = parts(a), [, mb] = parts(b);
  return ma === mb ? `${da}–${dayMonth(b)}` : `${dayMonth(a)} – ${dayMonth(b)}`;
}

/** Heading of a period, e.g. "4-oktabr 2026, yakshanba", "39-hafta · 21–27 sentabr". */
export function periodLabel(p) {
  const code = lang(), l = loc(), [y, m] = parts(p.start);
  if (p.type === 'kun') {
    const wd = l.weekdays[weekday(p.start)];
    return code === 'en' ? `${wd}, ${dayFull(p.start)}` : `${dayFull(p.start)}, ${wd}`;
  }
  if (p.type === 'hafta') {
    const r = range(p.start, p.end);
    if (code === 'uz') return `${p.week}-hafta · ${r}`;
    if (code === 'ru') return `${p.week}-я неделя · ${r}`;
    return `Week ${p.week} · ${r}`;
  }
  if (p.type === 'oy') return `${monthName(m)} ${y}`;
  if (p.type === 'chorak') {
    const q = Math.floor(m / 3);
    if (code === 'uz') return `${ROMAN[q]} chorak ${y}`;
    if (code === 'ru') return `${ROMAN[q]} квартал ${y}`;
    return `Q${q + 1} ${y}`;
  }
  return code === 'uz' ? `${y}-yil` : code === 'ru' ? `${y} год` : String(y);
}

/** "27-sentabrga nisbatan" / "к 27 сентября" / "vs 27 Sep": the period a change is measured against. */
export function versus(p) {
  const code = lang(), l = loc(), [y, m] = parts(p.start), q = Math.floor(m / 3);
  if (p.type === 'kun') {
    return code === 'uz' ? `${dayMonth(p.start)}ga nisbatan` : code === 'ru' ? `к ${dayMonth(p.start)}` : `vs ${dayShort(p.start)}`;
  }
  if (p.type === 'hafta') return code === 'uz' ? `${p.week}-haftaga nisbatan` : code === 'ru' ? `к ${p.week}-й неделе` : `vs week ${p.week}`;
  if (p.type === 'oy') return code === 'uz' ? `${l.months[m]}ga nisbatan` : code === 'ru' ? `к ${l.dat[m]}` : `vs ${l.months[m]}`;
  if (p.type === 'chorak') {
    if (code === 'uz') return `${ROMAN[q]} chorakka nisbatan`;
    if (code === 'ru') return `${q === 1 ? 'ко' : 'к'} ${ROMAN[q]} кварталу`;
    return `vs Q${q + 1}`;
  }
  return code === 'uz' ? `${y}-yilga nisbatan` : code === 'ru' ? `к ${y} году` : `vs ${y}`;
}

/** Axis tick of a period slot: "5-sen", "39-h", "sen", "III 2026", "2026". */
export function tick(p) {
  const code = lang(), l = loc(), [y, m] = parts(p.start);
  if (p.type === 'kun') return dayShort(p.start);
  if (p.type === 'hafta') return code === 'uz' ? `${p.week}-h` : code === 'ru' ? `${p.week} нед.` : `W${p.week}`;
  if (p.type === 'oy') return m === 0 ? `${l.short[m]} ${String(y).slice(2)}` : l.short[m];
  if (p.type === 'chorak') return code === 'en' ? `Q${Math.floor(m / 3) + 1} ${String(y).slice(2)}` : `${ROMAN[Math.floor(m / 3)]} ${y}`;
  return String(y);
}

/** Post time: "23-sen, 17:06". */
export const postTime = (at) => `${dayShort(at.slice(0, 10))}, ${at.slice(11, 16)}`;
