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
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3Z"/>',
  sort: '<path d="M7 4v16M3.5 16.5 7 20l3.5-3.5"/><path d="M17 20V4M13.5 7.5 17 4l3.5 3.5"/>',
  sliders: '<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>',
  external: '<path d="M14 4h6v6"/><path d="M20 4 11 13"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  chevronDown: '<path d="m6 9 6 6 6-6"/>',
  chevronRight: '<path d="m9 5 7 7-7 7"/>',
  target: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="0.8"/>',
  pulse: '<path d="M3 12h4l2.5-6 5 12 2.5-6H21"/>',
  trendUp: '<path d="M3 17 9.5 10.5l4 4L21 7"/><path d="M15 7h6v6"/>',
  trendDown: '<path d="M3 7l6.5 6.5 4-4L21 17"/><path d="M15 17h6v-6"/>',
  minus: '<path d="M5 12h14"/>',
  pause: '<path d="M9 5v14M15 5v14"/>',
  trash: '<path d="M4 7h16M9 7V4.5h6V7M6.5 7l1 13h9l1-13M10 11v6M14 11v6"/>',
  play: '<path d="M7 5l12 7-12 7V5Z"/>',
  book: '<path d="M5 4h13v14H7a2 2 0 0 0-2 2V4Z"/><path d="M5 20a2 2 0 0 1 2-2h11v3H7a2 2 0 0 1-2-1Z"/>',
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
      forbidden: 'Bu amal uchun ruxsat yo‘q.',
      bad_handle: 'Kanal manzili noto‘g‘ri.', exists: 'Bu kanal ro‘yxatda bor.',
      not_channel: 'Bunday ochiq Telegram kanal topilmadi.',
      tg_unavailable: 'Telegram bilan bog‘lanib bo‘lmadi. Keyinroq urinib ko‘ring.',
      last_channel: 'Kamida bitta kanal faol qolishi kerak.', no_account: 'Bu foydalanuvchining logini topilmadi.',
      login_taken: 'Bu login band.', bad_login: 'Login talablarga mos emas.', weak_password: 'Parol talablarga mos emas.',
      no_request: 'Murojaat allaqachon ko‘rib chiqilgan.', self: 'O‘zingiz kirgan loginni o‘chira olmaysiz.', not_found: 'Topilmadi. Ro‘yxat yangilandi.',
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
      title: 'Admin paneli',
      tabUsers: 'Foydalanuvchilar', tabChannels: 'Kanallar', chanAdd: 'Kanal qo‘shish',
      chanSub: 'Keyingi kunlik yig‘imdan boshlab indeksga kiradi', chanPh: '@kanal yoki t.me/kanal',
      chanAddBtn: 'Qo‘shish', chanAdded: 'Kanal qo‘shildi', chanActive: 'Faol', chanPaused: 'To‘xtatilgan',
      chanSince: '{d} dan', pause: 'To‘xtatish', resume: 'Qayta yoqish',
      pauseNote: 'Keyingi kunlik yig‘imdan boshlab kanal indeksga kirmaydi. Yakunlangan kunlar o‘zgarmaydi.',
      stats: { active: 'Faol', pending: 'Kutilmoqda', expired: 'Muddati tugagan', blocked: 'Bloklangan' },
      reject: 'Rad etish', approve: 'Login yaratish',
      role: 'Rol',
      term: 'Amal qilish muddati', terms: { 30: '30 kun', 90: '90 kun', 0: 'Muddatsiz' },
      forRequest: 'So‘rov: {name}', ready: 'Kirish ma’lumoti tayyor',
      newPassword: 'Yangi parol', copyLogin: 'Loginni nusxalash', copyPassword: 'Parolni nusxalash', copied: 'Nusxalandi',
      once: 'Parol faqat hozir ko‘rsatiladi. Birinchi kirishda login Telegram hisobiga bog‘lanadi.',
      delivered: 'Foydalanuvchiga bot orqali yuborildi.', notDelivered: 'Bot orqali yuborib bo‘lmadi — o‘zingiz yetkazing.',
      resetNote: 'Eski parol endi ishlamaydi; foydalanuvchi qaytadan kiradi.',
      list: 'Ro‘yxat', empty: 'Hali foydalanuvchi yo‘q.', notSignedIn: 'Hali kirilmagan',
      until: '{d} gacha', noExpiry: 'muddatsiz',
      reset: 'Parolni tiklash', extend: 'Muddatni uzaytirish', block: 'Bloklash', unblock: 'Blokdan chiqarish',
      done: 'Saqlandi', rejectNote: 'Foydalanuvchiga rad javobi bot orqali yuboriladi.',
      markDone: 'Bajarildi deb yopish', markDoneNote: 'Foydalanuvchiga xabar yuborilmaydi.',
      tabRequests: 'Murojaatlar', newUser: 'Yangi foydalanuvchi', createBtn: 'Yaratish', auto: 'Avtomatik', manual: 'Qo‘lda',
      pwAuto: '12 belgili tasodifiy parol', loginPh: 'masalan, a.karimov', pwPh: 'Parolni kiriting',
      loginFree: 'Login bo‘sh', loginTaken: 'Bu login band', checking: 'Tekshirilmoqda…',
      loginBad: '3–32 belgi: kichik lotin harflari, raqamlar va . _ -; harf bilan boshlanadi',
      rules: { length: '8–64 belgi', mix: 'Harf va raqam bor', space: 'Bo‘sh joy yo‘q', login: 'Loginni o‘z ichiga olmaydi' },
      pwValid: 'Parol yaroqli', pwInvalid: 'Parol yaroqsiz', confirm: 'Tasdiqlash', doneBtn: 'Tayyor',
      changePw: 'Parolni o‘zgartirish', newUntil: 'Yangi muddat: {d} gacha', newForever: 'Yangi muddat: muddatsiz',
      nowUntil: 'Hozir: {d} gacha', nowForever: 'Hozir: muddatsiz',
      blockNote: 'Foydalanuvchi bot va dashboardga kira olmaydi. Keyin blokdan chiqarish mumkin.',
      unblockNote: 'Foydalanuvchi yana kira oladi.',
      f: { name: 'Ism', org: 'Tashkilot', valid: 'Amal qiladi', seen: 'Oxirgi faollik', created: 'Yaratilgan' },
      requestsEmpty: 'Yangi murojaat yo‘q', handled: 'Ko‘rib chiqilganlar', statusDone: 'Bajarildi', statusRejected: 'Rad etildi',
      write: 'Telegram’da yozish', openAccount: 'Hisobni ochish',
      remove: 'O‘chirish', removeUser: 'Foydalanuvchini o‘chirish',
      removeUserNote: 'Login va paroli butunlay o‘chiriladi, foydalanuvchi kira olmaydi. Bu amalni qaytarib bo‘lmaydi.',
      removeChannel: 'Kanalni o‘chirish', removeChannelNote: 'Kanal ro‘yxatdan o‘chiriladi va boshqa yig‘ilmaydi. Yig‘ilgan xabarlari arxivda qoladi.',
      removed: 'O‘chirildi',
    },
    roles: { analyst: 'Analitik', economist: 'Iqtisodchi', admin: 'Admin' },
    time: { today: 'bugun, {hm}', yesterday: 'kecha, {hm}' },
    dash: { title: 'Iqtisodiy indeks', sub: 'Ma’lumot 2 kun kechikish bilan', users: 'Admin paneli', account: 'Hisob', logout: 'Hisobdan chiqish' },
    tabs: { home: 'Asosiy', topics: 'Mavzular', posts: 'Xabarlar', method: 'Metodika' },
    period: { kun: 'Kun', hafta: 'Hafta', oy: 'Oy', chorak: 'Chorak', yil: 'Yil', open: 'Yakunlanmagan',
      prev: 'Oldingi davr', next: 'Keyingi davr', pick: 'Davrni tanlash' },
    ov: {
      eai: 'E’tibor · EAI', eaiHint: 'iqtisodiy xabarlar ulushi', esi: 'Kayfiyat · ESI', esiHint: 'ijobiy − salbiy, 0 = neytral',
      pp: 'f.b.', noPrev: 'Oldingi davr kuzatilmagan', dynamics: 'Dinamika',
      by: { oy: 'Kunlar bo‘yicha', chorak: 'Haftalar bo‘yicha', yil: 'Oylar bo‘yicha' },
      lastN: { kun: 'So‘nggi {n} kun', hafta: 'So‘nggi {n} hafta', oy: 'So‘nggi {n} oy', chorak: 'So‘nggi {n} chorak', yil: 'So‘nggi {n} yil' },
      legEai: 'E’tibor, %', legEsi: 'Kayfiyat', legGap: 'Ma’lumot yo‘q', chartEai: 'E’tibor indeksi', chartEsi: 'Kayfiyat indeksi',
      tone: 'Ohang taqsimoti', econN: '{n} iqtisodiy xabar', pos: 'Ijobiy', neu: 'Neytral', neg: 'Salbiy',
      coverage: 'Qamrov', posts: 'Xabarlar', ads: 'Reklama chiqarildi', channels: '{a}/{b} kanal', days: '{a}/{b} kun', daysOpen: '{a} kun',
      top: 'Asosiy mavzular', all: 'Barchasi', empty: 'Hozircha ma’lumot yo‘q',
    },
    tp: {
      sub: '{period} · {n} iqtisodiy xabar', byTone: 'Mavzular bo‘yicha kayfiyat', head: 'Mavzu · xabarlar soni',
      how: 'ESI qanday shakllandi', total: 'Jami = ESI',
      howText: 'Mavzu ulushi = (ijobiy − salbiy) ÷ {n} iqtisodiy xabar × 100. Barcha ulushlar yig‘indisi ESI ga teng.',
    },
    ps: {
      count: '{n} ta iqtisodiy xabar', sort: 'Saralash', filters: 'Filtrlar', topic: 'Mavzu', tone: 'Ohang', channel: 'Kanal',
      all: 'Hammasi', clear: 'Tozalash', show: 'Ko‘rsatish ({n})', source: 'Manba', more: 'Yana yuklash', views: 'Ko‘rishlar',
      empty: 'Tanlangan davr va filtr bo‘yicha xabar yo‘q.', remove: '{x} filtrini olib tashlash',
      sortNew: 'Avval yangilari', sortNewSub: 'Sana bo‘yicha: yangi → eski', sortOld: 'Avval eskilari',
      sortOldSub: 'Sana bo‘yicha: eski → yangi', sortViews: 'Ko‘p ko‘rilganlar', sortViewsSub: 'Ko‘rishlar soni bo‘yicha',
      date: 'Sana', range: 'Oraliq', day: 'Bir kun', last7: 'So‘nggi 7 kun', last30: 'So‘nggi 30 kun',
      grey: 'Kulrang', greyTail: ' kunlarda ma’lumot yo‘q', apply: 'Qo‘llash', nDays: '{n} kun',
      prevMonth: 'Oldingi oy', nextMonth: 'Keyingi oy',
    },
    md: {
      sub: 'Indekslar qanday hisoblanadi', eai: 'E’tibor indeksi · EAI', eaiF: 'EAI = 100 × iqtisodiy ÷ reklama emas',
      eaiText: 'Reklama bo‘lmagan xabarlarning necha foizi O‘zbekiston iqtisodiyotiga oid. Shkala 0–100%.',
      esi: 'Kayfiyat indeksi · ESI', esiF: 'ESI = 100 × (ijobiy − salbiy) ÷ iqtisodiy',
      esiText: 'Iqtisodiy xabarlardagi yaxshi va yomon yangiliklar balansi. Shkala −100 dan +100 gacha, 0 — neytral.',
    },
    topics: {
      prices_inflation: 'Narx va inflatsiya', currency_fx: 'Valyuta kursi', fiscal: 'Byudjet va soliq', trade: 'Tashqi savdo',
      macro: 'Makroiqtisodiyot', central_bank: 'Markaziy bank', banking_finance: 'Bank va moliya',
      labour_income: 'Mehnat va daromad', energy_utility: 'Energetika', business: 'Biznes', construction_realty: 'Qurilish',
    },
    langTitle: 'Til',
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
      forbidden: 'Нет прав на это действие.',
      bad_handle: 'Неверный адрес канала.', exists: 'Этот канал уже в списке.',
      not_channel: 'Такой открытый канал Telegram не найден.',
      tg_unavailable: 'Не удалось связаться с Telegram. Попробуйте позже.',
      last_channel: 'Хотя бы один канал должен остаться активным.', no_account: 'Логин этого пользователя не найден.',
      login_taken: 'Этот логин занят.', bad_login: 'Логин не соответствует требованиям.', weak_password: 'Пароль не соответствует требованиям.',
      no_request: 'Обращение уже рассмотрено.', self: 'Нельзя удалить логин, под которым вы вошли.', not_found: 'Не найдено. Список обновлён.',
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
      title: 'Админ-панель',
      tabUsers: 'Пользователи', tabChannels: 'Каналы', chanAdd: 'Добавить канал',
      chanSub: 'Войдёт в индекс со следующего ежедневного сбора', chanPh: '@канал или t.me/канал',
      chanAddBtn: 'Добавить', chanAdded: 'Канал добавлен', chanActive: 'Активен', chanPaused: 'Приостановлен',
      chanSince: 'с {d}', pause: 'Приостановить', resume: 'Возобновить',
      pauseNote: 'Со следующего ежедневного сбора канал не входит в индекс. Завершённые дни не меняются.',
      stats: { active: 'Активные', pending: 'Ожидают', expired: 'Срок истёк', blocked: 'Заблокированы' },
      reject: 'Отклонить', approve: 'Создать логин',
      role: 'Роль',
      term: 'Срок действия', terms: { 30: '30 дней', 90: '90 дней', 0: 'Бессрочно' },
      forRequest: 'Запрос: {name}', ready: 'Данные для входа готовы',
      newPassword: 'Новый пароль', copyLogin: 'Копировать логин', copyPassword: 'Копировать пароль', copied: 'Скопировано',
      once: 'Пароль показывается только сейчас. При первом входе логин привяжется к аккаунту Telegram.',
      delivered: 'Отправлено пользователю через бот.', notDelivered: 'Не удалось отправить через бот — передайте сами.',
      resetNote: 'Старый пароль больше не работает; пользователь войдёт заново.',
      list: 'Список', empty: 'Пользователей пока нет.', notSignedIn: 'Ещё не входил',
      until: 'до {d}', noExpiry: 'бессрочно',
      reset: 'Сбросить пароль', extend: 'Продлить срок', block: 'Заблокировать', unblock: 'Разблокировать',
      done: 'Сохранено', rejectNote: 'Пользователь получит отказ через бот.',
      markDone: 'Закрыть как выполненный', markDoneNote: 'Пользователь не получит сообщения.',
      tabRequests: 'Обращения', newUser: 'Новый пользователь', createBtn: 'Создать', auto: 'Автоматически', manual: 'Вручную',
      pwAuto: 'Случайный пароль из 12 символов', loginPh: 'например, a.karimov', pwPh: 'Введите пароль',
      loginFree: 'Логин свободен', loginTaken: 'Этот логин занят', checking: 'Проверяем…',
      loginBad: '3–32 символа: строчная латиница, цифры и . _ -; начинается с буквы',
      rules: { length: '8–64 символа', mix: 'Есть буквы и цифры', space: 'Без пробелов', login: 'Не содержит логин' },
      pwValid: 'Пароль подходит', pwInvalid: 'Пароль не подходит', confirm: 'Подтвердить', doneBtn: 'Готово',
      changePw: 'Сменить пароль', newUntil: 'Новый срок: до {d}', newForever: 'Новый срок: бессрочно',
      nowUntil: 'Сейчас: до {d}', nowForever: 'Сейчас: бессрочно',
      blockNote: 'Пользователь не сможет войти в бот и дашборд. Блокировку можно снять позже.',
      unblockNote: 'Пользователь снова сможет войти.',
      f: { name: 'Имя', org: 'Организация', valid: 'Действует', seen: 'Активность', created: 'Создан' },
      requestsEmpty: 'Новых обращений нет', handled: 'Рассмотренные', statusDone: 'Выполнено', statusRejected: 'Отклонено',
      write: 'Написать в Telegram', openAccount: 'Открыть аккаунт',
      remove: 'Удалить', removeUser: 'Удалить пользователя',
      removeUserNote: 'Логин и пароль будут удалены навсегда, пользователь не сможет войти. Действие необратимо.',
      removeChannel: 'Удалить канал', removeChannelNote: 'Канал исчезнет из списка и больше не будет собираться. Собранные новости останутся в архиве.',
      removed: 'Удалено',
    },
    roles: { analyst: 'Аналитик', economist: 'Экономист', admin: 'Админ' },
    time: { today: 'сегодня, {hm}', yesterday: 'вчера, {hm}' },
    dash: { title: 'Экономический индекс', sub: 'Данные с задержкой 2 дня', users: 'Админ-панель', account: 'Аккаунт', logout: 'Выйти из аккаунта' },
    tabs: { home: 'Главная', topics: 'Темы', posts: 'Новости', method: 'Методика' },
    period: { kun: 'День', hafta: 'Неделя', oy: 'Месяц', chorak: 'Квартал', yil: 'Год', open: 'Не завершён',
      prev: 'Предыдущий период', next: 'Следующий период', pick: 'Выбрать период' },
    ov: {
      eai: 'Внимание · EAI', eaiHint: 'доля экономических новостей', esi: 'Настроение · ESI', esiHint: 'позитив − негатив, 0 = нейтрально',
      pp: 'п.п.', noPrev: 'Нет данных за прошлый период', dynamics: 'Динамика',
      by: { oy: 'По дням', chorak: 'По неделям', yil: 'По месяцам' },
      lastN: { kun: 'Последние {n} дн.', hafta: 'Последние {n} нед.', oy: 'Последние {n} мес.', chorak: 'Последние {n} кв.', yil: 'Последние {n} г.' },
      legEai: 'Внимание, %', legEsi: 'Настроение', legGap: 'Нет данных', chartEai: 'Индекс внимания', chartEsi: 'Индекс настроения',
      tone: 'Тональность', econN: 'экономических новостей: {n}', pos: 'Позитив', neu: 'Нейтрально', neg: 'Негатив',
      coverage: 'Охват', posts: 'Новости', ads: 'Реклама исключена', channels: '{a}/{b} каналов', days: '{a}/{b} дн.', daysOpen: '{a} дн.',
      top: 'Главные темы', all: 'Все', empty: 'Данных пока нет',
    },
    tp: {
      sub: '{period} · экономических новостей: {n}', byTone: 'Настроение по темам', head: 'Тема · число новостей',
      how: 'Как сложился ESI', total: 'Итого = ESI',
      howText: 'Вклад темы = (позитив − негатив) ÷ {n} экономических новостей × 100. Сумма вкладов равна ESI.',
    },
    ps: {
      count: 'экономических новостей: {n}', sort: 'Сортировка', filters: 'Фильтры', topic: 'Тема', tone: 'Тональность', channel: 'Канал',
      all: 'Все', clear: 'Сбросить', show: 'Показать ({n})', source: 'Источник', more: 'Показать ещё', views: 'Просмотры',
      empty: 'За выбранный период и по фильтрам новостей нет.', remove: 'Убрать фильтр «{x}»',
      sortNew: 'Сначала новые', sortNewSub: 'По дате: новые → старые', sortOld: 'Сначала старые',
      sortOldSub: 'По дате: старые → новые', sortViews: 'Самые просматриваемые', sortViewsSub: 'По числу просмотров',
      date: 'Дата', range: 'Период', day: 'Один день', last7: 'Последние 7 дней', last30: 'Последние 30 дней',
      grey: 'Серые', greyTail: ' дни — без данных', apply: 'Применить', nDays: '{n} дн.',
      prevMonth: 'Предыдущий месяц', nextMonth: 'Следующий месяц',
    },
    md: {
      sub: 'Как рассчитываются индексы', eai: 'Индекс внимания · EAI', eaiF: 'EAI = 100 × экономические ÷ нерекламные',
      eaiText: 'Какой процент нерекламных новостей посвящён экономике Узбекистана. Шкала 0–100%.',
      esi: 'Индекс настроения · ESI', esiF: 'ESI = 100 × (позитив − негатив) ÷ экономические',
      esiText: 'Баланс хороших и плохих новостей среди экономических. Шкала от −100 до +100, 0 — нейтрально.',
    },
    topics: {
      prices_inflation: 'Цены и инфляция', currency_fx: 'Валютный курс', fiscal: 'Бюджет и налоги', trade: 'Внешняя торговля',
      macro: 'Макроэкономика', central_bank: 'Центральный банк', banking_finance: 'Банки и финансы',
      labour_income: 'Труд и доходы', energy_utility: 'Энергетика', business: 'Бизнес', construction_realty: 'Строительство',
    },
    langTitle: 'Язык',
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
      forbidden: 'You are not allowed to do this.',
      bad_handle: 'Invalid channel address.', exists: 'This channel is already in the list.',
      not_channel: 'No such public Telegram channel.',
      tg_unavailable: 'Could not reach Telegram. Try again later.',
      last_channel: 'At least one channel must stay active.', no_account: 'No login found for this user.',
      login_taken: 'This login is taken.', bad_login: 'The login does not meet the rules.', weak_password: 'The password does not meet the rules.',
      no_request: 'The request has already been handled.', self: 'You cannot delete the login you are signed in with.', not_found: 'Not found. The list was refreshed.',
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
      title: 'Admin panel',
      tabUsers: 'Users', tabChannels: 'Channels', chanAdd: 'Add a channel',
      chanSub: 'It joins the index from the next daily collection', chanPh: '@channel or t.me/channel',
      chanAddBtn: 'Add', chanAdded: 'Channel added', chanActive: 'Active', chanPaused: 'Paused',
      chanSince: 'since {d}', pause: 'Pause', resume: 'Resume',
      pauseNote: 'From the next daily collection the channel is left out of the index. Finished days do not change.',
      stats: { active: 'Active', pending: 'Pending', expired: 'Expired', blocked: 'Blocked' },
      reject: 'Reject', approve: 'Create login',
      role: 'Role',
      term: 'Valid for', terms: { 30: '30 days', 90: '90 days', 0: 'No expiry' },
      forRequest: 'Request: {name}', ready: 'Credentials ready',
      newPassword: 'New password', copyLogin: 'Copy login', copyPassword: 'Copy password', copied: 'Copied',
      once: 'The password is shown only now. On first sign-in the login is linked to the Telegram account.',
      delivered: 'Sent to the user via the bot.', notDelivered: 'Could not send via the bot — deliver it yourself.',
      resetNote: 'The old password no longer works; the user signs in again.',
      list: 'List', empty: 'No users yet.', notSignedIn: 'Not signed in yet',
      until: 'until {d}', noExpiry: 'no expiry',
      reset: 'Reset password', extend: 'Extend access', block: 'Block', unblock: 'Unblock',
      done: 'Saved', rejectNote: 'The user will be told via the bot.',
      markDone: 'Mark as done', markDoneNote: 'The user is not notified.',
      tabRequests: 'Requests', newUser: 'New user', createBtn: 'Create', auto: 'Automatic', manual: 'Manual',
      pwAuto: 'Random 12-character password', loginPh: 'e.g. a.karimov', pwPh: 'Enter a password',
      loginFree: 'Login is available', loginTaken: 'This login is taken', checking: 'Checking…',
      loginBad: '3–32 characters: lowercase Latin letters, digits and . _ -; starts with a letter',
      rules: { length: '8–64 characters', mix: 'Letters and digits', space: 'No spaces', login: 'Does not contain the login' },
      pwValid: 'Password is valid', pwInvalid: 'Password is not valid', confirm: 'Confirm', doneBtn: 'Done',
      changePw: 'Change password', newUntil: 'New end date: {d}', newForever: 'New end date: none',
      nowUntil: 'Now: until {d}', nowForever: 'Now: no end date',
      blockNote: 'The user will not be able to use the bot and dashboard. You can unblock later.',
      unblockNote: 'The user will be able to sign in again.',
      f: { name: 'Name', org: 'Organisation', valid: 'Valid', seen: 'Last active', created: 'Created' },
      requestsEmpty: 'No new requests', handled: 'Handled', statusDone: 'Done', statusRejected: 'Declined',
      write: 'Message on Telegram', openAccount: 'Open account',
      remove: 'Delete', removeUser: 'Delete user',
      removeUserNote: 'The login and password are deleted for good; the user can no longer sign in. This cannot be undone.',
      removeChannel: 'Delete channel', removeChannelNote: 'The channel leaves the list and is no longer collected. Its collected posts stay in the archive.',
      removed: 'Deleted',
    },
    roles: { analyst: 'Analyst', economist: 'Economist', admin: 'Admin' },
    time: { today: 'today, {hm}', yesterday: 'yesterday, {hm}' },
    dash: { title: 'Economic index', sub: 'Data with a 2-day lag', users: 'Admin panel', account: 'Account', logout: 'Sign out' },
    tabs: { home: 'Overview', topics: 'Topics', posts: 'News', method: 'Method' },
    period: { kun: 'Day', hafta: 'Week', oy: 'Month', chorak: 'Quarter', yil: 'Year', open: 'In progress',
      prev: 'Previous period', next: 'Next period', pick: 'Choose period' },
    ov: {
      eai: 'Attention · EAI', eaiHint: 'share of economic news', esi: 'Sentiment · ESI', esiHint: 'positive − negative, 0 = neutral',
      pp: 'pp', noPrev: 'No data for the previous period', dynamics: 'Trend',
      by: { oy: 'By day', chorak: 'By week', yil: 'By month' },
      lastN: { kun: 'Last {n} days', hafta: 'Last {n} weeks', oy: 'Last {n} months', chorak: 'Last {n} quarters', yil: 'Last {n} years' },
      legEai: 'Attention, %', legEsi: 'Sentiment', legGap: 'No data', chartEai: 'Attention index', chartEsi: 'Sentiment index',
      tone: 'Tone', econN: '{n} economic news', pos: 'Positive', neu: 'Neutral', neg: 'Negative',
      coverage: 'Coverage', posts: 'Posts', ads: 'Ads excluded', channels: '{a}/{b} channels', days: '{a}/{b} days', daysOpen: '{a} days',
      top: 'Main topics', all: 'All', empty: 'No data yet',
    },
    tp: {
      sub: '{period} · {n} economic news', byTone: 'Sentiment by topic', head: 'Topic · number of news',
      how: 'How ESI is made up', total: 'Total = ESI',
      howText: 'Topic share = (positive − negative) ÷ {n} economic news × 100. The shares add up to ESI.',
    },
    ps: {
      count: '{n} economic news', sort: 'Sort', filters: 'Filters', topic: 'Topic', tone: 'Tone', channel: 'Channel',
      all: 'All', clear: 'Clear', show: 'Show ({n})', source: 'Source', more: 'Load more', views: 'Views',
      empty: 'No news for the selected period and filters.', remove: 'Remove the {x} filter',
      sortNew: 'Newest first', sortNewSub: 'By date: new → old', sortOld: 'Oldest first',
      sortOldSub: 'By date: old → new', sortViews: 'Most viewed', sortViewsSub: 'By number of views',
      date: 'Date', range: 'Range', day: 'Single day', last7: 'Last 7 days', last30: 'Last 30 days',
      grey: 'Grey', greyTail: ' days have no data', apply: 'Apply', nDays: '{n} days',
      prevMonth: 'Previous month', nextMonth: 'Next month',
    },
    md: {
      sub: 'How the indices are calculated', eai: 'Attention index · EAI', eaiF: 'EAI = 100 × economic ÷ non-ad',
      eaiText: 'The share of non-advertising news that is about Uzbekistan’s economy. Scale 0–100%.',
      esi: 'Sentiment index · ESI', esiF: 'ESI = 100 × (positive − negative) ÷ economic',
      esiText: 'The balance of good and bad economic news. Scale −100 to +100, 0 is neutral.',
    },
    topics: {
      prices_inflation: 'Prices & inflation', currency_fx: 'Exchange rate', fiscal: 'Budget & taxes', trade: 'Foreign trade',
      macro: 'Macroeconomy', central_bank: 'Central bank', banking_finance: 'Banking & finance',
      labour_income: 'Labour & income', energy_utility: 'Energy', business: 'Business', construction_realty: 'Construction',
    },
    langTitle: 'Language',
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
export function setLang(l, { save = true } = {}) {
  if (!D[l]) return;
  LANG = l;
  document.documentElement.lang = l;
  if (!save) return;
  try { localStorage.setItem('uzei.lang', l); } catch (e) { /* storage blocked */ }
  api('lang', { lang: l }).catch(() => {});         // the bot answers in the same language
}
/** The language picked here wins; without one the bot's choice is used. */
export function syncLang(serverLang) {
  let saved = null;
  try { saved = localStorage.getItem('uzei.lang'); } catch (e) { /* storage blocked */ }
  if (D[saved]) { if (saved !== serverLang) api('lang', { lang: saved }).catch(() => {}); }
  else if (D[serverLang] && serverLang !== LANG) setLang(serverLang, { save: false });
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

/** Bottom sheet over the page; returns close(). The Telegram back button closes it too. */
export function openSheet(root, title, html, mount) {
  const wrap = document.createElement('div');
  wrap.className = 'sheet-wrap';
  wrap.setAttribute('role', 'dialog');
  wrap.setAttribute('aria-modal', 'true');
  wrap.setAttribute('aria-label', title);
  wrap.innerHTML = `
    <button class="backdrop" data-close aria-label="${esc(t('close'))}"></button>
    <div class="sheet">
      <span class="grip"></span>
      <div class="head"><h2>${esc(title)}</h2>
        <button class="icon-btn" data-close aria-label="${esc(t('close'))}">${icon('close', 16, 2.2)}</button></div>
      <div class="sheet-body"></div>
    </div>`;
  const prevBack = backFn;
  const close = () => { wrap.remove(); setBack(prevBack); };
  const body = wrap.querySelector('.sheet-body');
  const fill = (markup) => { body.innerHTML = markup; if (mount) mount(body, close, fill); };
  wrap.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', () => { haptic(); close(); }));
  root.appendChild(wrap);
  setBack(close);
  fill(html);
  return close;
}
