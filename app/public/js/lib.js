// Shared helpers: Telegram bridge, escaping, icons, translations, API calls.
export const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;

export const esc = (s) => String(s ?? '').replace(/[&<>"']/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// ---------------------------------------------------------------- icons ----
const PATHS = {
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c1-3.5 3.5-5.5 6.5-5.5s5.5 2 6.5 5.5"/><path d="M16 4.8a3.5 3.5 0 0 1 0 6.4M18 14.8c1.8.7 3 2.4 3.5 5.2"/>',
  lock: '<rect x="4.5" y="10.5" width="15" height="10" rx="2"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/>',
  eye: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="3"/>',
  eyeOff: '<path d="M3 3l18 18"/><path d="M10.6 5.6A9.7 9.7 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a17 17 0 0 1-3.2 3.9M6.3 6.9A17 17 0 0 0 2.5 12S6 18.5 12 18.5c1.6 0 3-.4 4.3-1"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
  arrowRight: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  back: '<path d="m15 5-7 7 7 7"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  send: '<path d="M21 3 10.5 13.5"/><path d="M21 3 14.5 21l-4-7.5L3 9.5 21 3Z"/>',
  key: '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M16 7l3 3M14 9l2 2"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  copy: '<rect x="8.5" y="8.5" width="11.5" height="11.5" rx="2"/><path d="M15.5 8.5V5.5a1.5 1.5 0 0 0-1.5-1.5H5.5A1.5 1.5 0 0 0 4 5.5V14a1.5 1.5 0 0 0 1.5 1.5h3"/>',
  shield: '<path d="M12 3 5 6v6c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6l-7-3Z"/>',
  more: '<circle cx="5" cy="12" r="1.4" fill="currentColor"/><circle cx="12" cy="12" r="1.4" fill="currentColor"/><circle cx="19" cy="12" r="1.4" fill="currentColor"/>',
  calendar: '<rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
  refresh: '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/>',
  ban: '<circle cx="12" cy="12" r="8.5"/><path d="m6 6 12 12"/>',
  unlock: '<rect x="4.5" y="10.5" width="15" height="10" rx="2"/><path d="M8 10.5V7.5a4 4 0 0 1 7.7-1.5"/>',
  logout: '<path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3"/><path d="M10 8l-4 4 4 4M6 12h10"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.6v.4"/>',
  alert: '<path d="M12 4 2.5 20h19L12 4Z"/><path d="M12 10v4.5M12 17.4v.3"/>',
  home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V20h5v-6h4v6h5V9.5"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 13 9 5 9-5"/>',
  news: '<path d="M4 5h12v14H6a2 2 0 0 1-2-2V5Z"/><path d="M16 9h4v8a2 2 0 0 1-2 2h-2"/><path d="M7 9h6M7 13h6M7 16h4"/>',
  up: '<path d="M7 17 17 7M9 7h8v8"/>',
  down: '<path d="M7 7l10 10M17 9v8H9"/>',
};
export const icon = (name, size = 20, width = 1.8) =>
  `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${width}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${PATHS[name] || ''}</svg>`;
export const logo = (size = 36) =>
  `<svg class="logo" width="${size}" height="${size}" viewBox="0 0 36 36" aria-hidden="true"><rect width="36" height="36" rx="10"/><path d="M8 23l6-6 5 4 9-10"/><circle cx="28" cy="11" r="2.6"/></svg>`;

// --------------------------------------------------------- translations ----
const D = {
  uz: {
    auth: {
      tag: 'O‘zbekiston iqtisodiy yangiliklar indeksi', login: 'Login', loginPh: 'Masalan, analyst.07',
      password: 'Parol', passwordPh: 'Parolni kiriting', showPw: 'Parolni ko‘rsatish', hidePw: 'Parolni yashirish',
      signIn: 'Kirish', noCreds: 'Kirish ma’lumoti yo‘qmi? ', contactLink: 'Administratorga', contactTail: ' murojaat qiling.',
    },
    err: {
      invalid: 'Login yoki parol noto‘g‘ri.', locked: 'Urinishlar ko‘p bo‘ldi. 15 daqiqadan so‘ng qayta urinib ko‘ring.',
      blocked: 'Hisob bloklangan.', expired: 'Kirish muddati tugagan.',
      other_account: 'Bu login boshqa Telegram hisobiga bog‘langan.', fill: 'Login va parolni kiriting.',
      network: 'Tarmoq xatosi. Qayta urinib ko‘ring.', server: 'Server xatosi. Birozdan so‘ng urinib ko‘ring.',
      name: 'Ism va familiyani kiriting.', too_many: 'So‘rovingiz allaqachon yuborilgan. Administrator javobini kuting.',
      forbidden: 'Bu amal uchun ruxsat yo‘q.', no_account: 'Bu foydalanuvchining logini topilmadi.',
    },
    contact: {
      title: 'Administratorga murojaat', fullName: 'Ism va familiya', fullNamePh: 'Ism Familiya',
      org: 'Tashkilot va lavozim', orgPh: 'Bo‘lim, lavozim', reason: 'Murojaat sababi',
      reasons: { access: 'Kirish olish', reset: 'Parolni tiklash', other: 'Boshqa' },
      message: 'Xabar', messagePh: 'Ixtiyoriy', telegram: 'Telegram hisobi', auto: 'avtomatik', send: 'Yuborish',
      pending: 'Avvalgi so‘rovingiz ko‘rib chiqilmoqda.',
    },
    sent: { title: 'So‘rov yuborildi', text: 'Administrator javobini shu bot orqali olasiz.', back: 'Kirish sahifasiga qaytish' },
    denied: { blocked: 'Hisob bloklangan', expired: 'Kirish muddati tugagan', other: 'Boshqa login bilan kirish' },
    outside: { text: 'Ilovani Telegram ichida oching.' },
    retry: 'Qayta urinish', back: 'Orqaga', close: 'Yopish', cancel: 'Bekor qilish',
    admin: {
      title: 'Foydalanuvchilar', badge: 'Admin',
      stats: { active: 'Faol', pending: 'Kutilmoqda', expired: 'Muddati tugagan', blocked: 'Bloklangan' },
      requests: 'Kirish so‘rovlari', newN: '{n} ta yangi', reject: 'Rad etish', approve: 'Login yaratish',
      create: 'Yangi kirish ma’lumoti', createSub: 'Login va parol bir marta ko‘rsatiladi', role: 'Rol',
      term: 'Amal qilish muddati', terms: { 30: '30 kun', 90: '90 kun', 0: 'Muddatsiz' },
      generate: 'Login va parol yaratish', forRequest: 'So‘rov: {name}', ready: 'Kirish ma’lumoti tayyor',
      newPassword: 'Yangi parol', copyLogin: 'Loginni nusxalash', copyPassword: 'Parolni nusxalash', copied: 'Nusxalandi',
      once: 'Parol faqat hozir ko‘rsatiladi. Birinchi kirishda login Telegram hisobiga bog‘lanadi.',
      delivered: 'Foydalanuvchiga bot orqali yuborildi.', notDelivered: 'Bot orqali yuborib bo‘lmadi — o‘zingiz yetkazing.',
      resetNote: 'Eski parol endi ishlamaydi; foydalanuvchi qaytadan kiradi.',
      list: 'Ro‘yxat', empty: 'Hali foydalanuvchi yo‘q.', lastSeen: 'Oxirgi faollik: {t}', notSignedIn: 'Hali kirilmagan',
      until: '{d} gacha', noExpiry: 'muddatsiz', actions: '{login} uchun amallar',
      reset: 'Parolni tiklash', extend: 'Muddatni uzaytirish', block: 'Bloklash', unblock: 'Blokdan chiqarish',
      extendTitle: 'Yangi muddat', done: 'Saqlandi', rejectNote: 'Foydalanuvchiga rad javobi bot orqali yuboriladi.',
      markDone: 'Bajarildi deb yopish', markDoneNote: 'Foydalanuvchiga xabar yuborilmaydi.',
    },
    roles: { analyst: 'Analitik', economist: 'Iqtisodchi', admin: 'Admin' },
    time: { today: 'bugun, {hm}', yesterday: 'kecha, {hm}' },
    dash: { title: 'Iqtisodiy indeks', sub: 'Ma’lumot 2 kun kechikish bilan', users: 'Foydalanuvchilar', account: 'Hisob', logout: 'Hisobdan chiqish' },
  },
  ru: {
    auth: {
      tag: 'Индекс экономических новостей Узбекистана', login: 'Логин', loginPh: 'Например, analyst.07',
      password: 'Пароль', passwordPh: 'Введите пароль', showPw: 'Показать пароль', hidePw: 'Скрыть пароль',
      signIn: 'Войти', noCreds: 'Нет данных для входа? Обратитесь к ', contactLink: 'администратору', contactTail: '.',
    },
    err: {
      invalid: 'Неверный логин или пароль.', locked: 'Слишком много попыток. Повторите через 15 минут.',
      blocked: 'Аккаунт заблокирован.', expired: 'Срок доступа истёк.',
      other_account: 'Этот логин привязан к другому аккаунту Telegram.', fill: 'Введите логин и пароль.',
      network: 'Ошибка сети. Повторите попытку.', server: 'Ошибка сервера. Повторите позже.',
      name: 'Укажите имя и фамилию.', too_many: 'Запрос уже отправлен. Дождитесь ответа администратора.',
      forbidden: 'Нет прав на это действие.', no_account: 'Логин этого пользователя не найден.',
    },
    contact: {
      title: 'Обращение к администратору', fullName: 'Имя и фамилия', fullNamePh: 'Имя Фамилия',
      org: 'Организация и должность', orgPh: 'Отдел, должность', reason: 'Причина обращения',
      reasons: { access: 'Получить доступ', reset: 'Сбросить пароль', other: 'Другое' },
      message: 'Сообщение', messagePh: 'Необязательно', telegram: 'Аккаунт Telegram', auto: 'автоматически', send: 'Отправить',
      pending: 'Ваш предыдущий запрос рассматривается.',
    },
    sent: { title: 'Запрос отправлен', text: 'Ответ администратора придёт в этом боте.', back: 'Вернуться ко входу' },
    denied: { blocked: 'Аккаунт заблокирован', expired: 'Срок доступа истёк', other: 'Войти с другим логином' },
    outside: { text: 'Откройте приложение в Telegram.' },
    retry: 'Повторить', back: 'Назад', close: 'Закрыть', cancel: 'Отмена',
    admin: {
      title: 'Пользователи', badge: 'Админ',
      stats: { active: 'Активные', pending: 'Ожидают', expired: 'Срок истёк', blocked: 'Заблокированы' },
      requests: 'Запросы на доступ', newN: 'новых: {n}', reject: 'Отклонить', approve: 'Создать логин',
      create: 'Новые данные для входа', createSub: 'Логин и пароль показываются один раз', role: 'Роль',
      term: 'Срок действия', terms: { 30: '30 дней', 90: '90 дней', 0: 'Бессрочно' },
      generate: 'Создать логин и пароль', forRequest: 'Запрос: {name}', ready: 'Данные для входа готовы',
      newPassword: 'Новый пароль', copyLogin: 'Копировать логин', copyPassword: 'Копировать пароль', copied: 'Скопировано',
      once: 'Пароль показывается только сейчас. При первом входе логин привяжется к аккаунту Telegram.',
      delivered: 'Отправлено пользователю через бот.', notDelivered: 'Не удалось отправить через бот — передайте сами.',
      resetNote: 'Старый пароль больше не работает; пользователь войдёт заново.',
      list: 'Список', empty: 'Пользователей пока нет.', lastSeen: 'Активность: {t}', notSignedIn: 'Ещё не входил',
      until: 'до {d}', noExpiry: 'бессрочно', actions: 'Действия для {login}',
      reset: 'Сбросить пароль', extend: 'Продлить срок', block: 'Заблокировать', unblock: 'Разблокировать',
      extendTitle: 'Новый срок', done: 'Сохранено', rejectNote: 'Пользователь получит отказ через бот.',
      markDone: 'Закрыть как выполненный', markDoneNote: 'Пользователь не получит сообщения.',
    },
    roles: { analyst: 'Аналитик', economist: 'Экономист', admin: 'Админ' },
    time: { today: 'сегодня, {hm}', yesterday: 'вчера, {hm}' },
    dash: { title: 'Экономический индекс', sub: 'Данные с задержкой 2 дня', users: 'Пользователи', account: 'Аккаунт', logout: 'Выйти из аккаунта' },
  },
  en: {
    auth: {
      tag: 'Uzbekistan economic news index', login: 'Login', loginPh: 'e.g. analyst.07',
      password: 'Password', passwordPh: 'Enter your password', showPw: 'Show password', hidePw: 'Hide password',
      signIn: 'Sign in', noCreds: 'No credentials? Contact your ', contactLink: 'administrator', contactTail: '.',
    },
    err: {
      invalid: 'Wrong login or password.', locked: 'Too many attempts. Try again in 15 minutes.',
      blocked: 'This account is blocked.', expired: 'Access has expired.',
      other_account: 'This login is linked to another Telegram account.', fill: 'Enter your login and password.',
      network: 'Network error. Please try again.', server: 'Server error. Please try again later.',
      name: 'Enter your full name.', too_many: 'Your request has already been sent. Please wait for the administrator.',
      forbidden: 'You are not allowed to do this.', no_account: 'No login found for this user.',
    },
    contact: {
      title: 'Contact the administrator', fullName: 'Full name', fullNamePh: 'First Last',
      org: 'Organization and position', orgPh: 'Department, position', reason: 'Reason',
      reasons: { access: 'Get access', reset: 'Reset password', other: 'Other' },
      message: 'Message', messagePh: 'Optional', telegram: 'Telegram account', auto: 'automatic', send: 'Send',
      pending: 'Your previous request is being reviewed.',
    },
    sent: { title: 'Request sent', text: 'You will get the administrator’s reply in this bot.', back: 'Back to sign-in' },
    denied: { blocked: 'Account blocked', expired: 'Access expired', other: 'Sign in with another login' },
    outside: { text: 'Open the app in Telegram.' },
    retry: 'Try again', back: 'Back', close: 'Close', cancel: 'Cancel',
    admin: {
      title: 'Users', badge: 'Admin',
      stats: { active: 'Active', pending: 'Pending', expired: 'Expired', blocked: 'Blocked' },
      requests: 'Access requests', newN: '{n} new', reject: 'Reject', approve: 'Create login',
      create: 'New credentials', createSub: 'Login and password are shown once', role: 'Role',
      term: 'Valid for', terms: { 30: '30 days', 90: '90 days', 0: 'No expiry' },
      generate: 'Create login and password', forRequest: 'Request: {name}', ready: 'Credentials ready',
      newPassword: 'New password', copyLogin: 'Copy login', copyPassword: 'Copy password', copied: 'Copied',
      once: 'The password is shown only now. On first sign-in the login is linked to the Telegram account.',
      delivered: 'Sent to the user via the bot.', notDelivered: 'Could not send via the bot — deliver it yourself.',
      resetNote: 'The old password no longer works; the user signs in again.',
      list: 'List', empty: 'No users yet.', lastSeen: 'Last active: {t}', notSignedIn: 'Not signed in yet',
      until: 'until {d}', noExpiry: 'no expiry', actions: 'Actions for {login}',
      reset: 'Reset password', extend: 'Extend access', block: 'Block', unblock: 'Unblock',
      extendTitle: 'New validity', done: 'Saved', rejectNote: 'The user will be told via the bot.',
      markDone: 'Mark as done', markDoneNote: 'The user is not notified.',
    },
    roles: { analyst: 'Analyst', economist: 'Economist', admin: 'Admin' },
    time: { today: 'today, {hm}', yesterday: 'yesterday, {hm}' },
    dash: { title: 'Economic index', sub: 'Data with a 2-day lag', users: 'Users', account: 'Account', logout: 'Sign out' },
  },
};
export const LANGS = [['uz', 'O‘zbekcha'], ['ru', 'Русский'], ['en', 'English']];

function pickLang() {
  try {
    const saved = localStorage.getItem('uzei.lang');
    if (D[saved]) return saved;
  } catch (e) { /* storage blocked */ }
  const lc = ((tg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.language_code) || '').slice(0, 2);
  return lc === 'ru' ? 'ru' : lc === 'en' ? 'en' : 'uz';
}
let LANG = pickLang();
document.documentElement.lang = LANG;
export const lang = () => LANG;
export function setLang(l) {
  if (!D[l]) return;
  LANG = l;
  document.documentElement.lang = l;
  try { localStorage.setItem('uzei.lang', l); } catch (e) { /* storage blocked */ }
}
const lookup = (dict, key) => key.split('.').reduce((o, k) => (o == null ? o : o[k]), dict);
export function t(key, vars) {
  let s = lookup(D[LANG], key);
  if (s == null) s = lookup(D.uz, key);
  if (s == null) return key;
  return vars ? String(s).replace(/\{(\w+)\}/g, (_, k) => (vars[k] ?? '')) : s;
}

// ------------------------------------------------------------ telegram ----
export function haptic(kind = 'light') {
  try {
    if (['success', 'error', 'warning'].includes(kind)) tg.HapticFeedback.notificationOccurred(kind);
    else tg.HapticFeedback.impactOccurred(kind);
  } catch (e) { /* not in Telegram */ }
}
export function applyTheme() {
  document.documentElement.dataset.theme = tg && tg.colorScheme === 'dark' ? 'dark' : 'light';
  const bg = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim();
  try { tg.setHeaderColor(bg); tg.setBackgroundColor(bg); } catch (e) { /* older clients */ }
}
let backFn = null;
export function setBack(fn) {
  if (!tg || !tg.BackButton) return;
  if (backFn) tg.BackButton.offClick(backFn);
  backFn = fn || null;
  if (fn) { tg.BackButton.onClick(fn); tg.BackButton.show(); } else tg.BackButton.hide();
}

// ----------------------------------------------------------------- API ----
export async function api(action, body) {
  const headers = { 'X-Telegram-Init-Data': (tg && tg.initData) || '' };
  if (action) headers['Content-Type'] = 'application/json';
  const res = await fetch(action ? `/api/index?action=${encodeURIComponent(action)}` : '/api/index', {
    method: action ? 'POST' : 'GET', headers, body: action ? JSON.stringify(body || {}) : undefined,
  });
  let data = {};
  try { data = await res.json(); } catch (e) { /* empty body */ }
  return { ...data, status: res.status };
}
export function errorText(r) {
  if (!r) return t('err.network');
  if (r.error && t('err.' + r.error) !== 'err.' + r.error) return t('err.' + r.error);
  return r.status >= 500 ? t('err.server') : t('err.network');
}

// ------------------------------------------------------------ ui bits -----
const pad = (n) => String(n).padStart(2, '0');
export const fmtDate = (iso) => { const d = new Date(iso); return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`; };
export function fmtWhen(iso) {
  if (!iso) return '';
  const d = new Date(iso), now = new Date();
  const hm = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  const day = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((day(now) - day(d)) / 864e5);
  if (diff === 0) return t('time.today', { hm });
  if (diff === 1) return t('time.yesterday', { hm });
  return fmtDate(iso);
}
export function toast(text) {
  document.querySelectorAll('.toast').forEach((n) => n.remove());
  const el = document.createElement('div');
  el.className = 'toast';
  el.setAttribute('role', 'status');
  el.textContent = text;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 1800);
}
export async function copy(text) {
  try { await navigator.clipboard.writeText(text); }
  catch (e) {
    const ta = document.createElement('textarea');
    ta.value = text; ta.setAttribute('readonly', ''); ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); } catch (err) { /* nothing more to try */ }
    ta.remove();
  }
  haptic('success');
  toast(t('admin.copied'));
}
export function segHTML(items, current, attr) {
  return items.map(([id, label]) =>
    `<button type="button" data-${attr}="${esc(id)}" aria-pressed="${String(id) === String(current)}">${esc(label)}</button>`).join('');
}
