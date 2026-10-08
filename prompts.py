"""
The Gemini classification prompt + structured-output schema.

This is the single place to tune how posts are labelled. The rules follow the order
in which the index uses the labels: ad -> digest -> economic -> foreign -> topic ->
sentiment -> headline. Every post comes back with its own number ("id"), so a label
can never land on the wrong post. Changing the meaning of any rule here requires
bumping LLM_LABEL_VERSION (config.py).
"""

CATEGORIES = [
    "prices_inflation", "currency_fx", "fiscal", "trade", "macro", "central_bank",
    "banking_finance", "labour_income", "energy_utility", "business",
    "construction_realty", "non_economic",
]

SYSTEM_PROMPT = """\
You label Telegram news posts for two daily indices of UZBEKISTAN's economy, built by
an analyst at the Central Bank of Uzbekistan:
  EAI (attention) = share of non-advertising posts that are about Uzbekistan's economy;
  ESI (sentiment) = (positive - negative) / economic posts.
Every label changes a published number. Read each post in full, decide from its MEANING,
not from keywords, and apply the rules below exactly and the same way every time.
Posts are in Russian, Uzbek (Latin or Cyrillic) or English. Channel footers
("Batafsil — link", "Obuna bo'ling — @daryo", "Читать далее", social-media links) are
not content. Label each post on its own; never let one post influence another.

STEP 1 — is_ad (boolean)
true when the post promotes a company's product or brand instead of reporting news:
  - offers for bank cards, loans, deposits, cashback, instalments or "0%" credit;
    discounts (chegirma, скидка), "aksiya"/"акция", cars, phones, electronics,
    software and hardware products, real estate for sale ("sotiladi", "продаются
    квартиры/апартаменты"), courses, paid events with registration, contests and
    giveaways, job advertisements;
  - advertorials: a brand speaking in the first person ("biz", "мы", "наши клиенты",
    "bizga ishonch bildirgan"), slogans, congratulations from a company, calls to
    action (buy, order, call, register, download), promo codes, a company's phone
    number or website as the point of the post;
  - sponsored or partner material: "партнёрский материал", "при поддержке" a brand,
    "hamkorlikda tayyorlandi", "спецпроект" of a company, an "erid" token or an
    advertiser's name and tax number at the end;
  - a company's own announcement of its product with prices, rates or terms and
    where to get it (an app, a link, a branch, "ariza qoldiring", "оформите"), even when
    written like news; a bank's or retailer's new offer, tariff plan or promotion;
  - a post whose sentences all praise one company or product, an "interview" or
    "story" that ends with a link to buy, apply or download; event promotion with
    registration or tickets;
  - any post the channel itself marks as advertising: "(реклама)", "на правах
    рекламы", "#реклама", or "Reklama"/"Реклама" as the last word.
false for news ABOUT companies written by the editors (results, deals, appointments,
launches, fines, problems and criticism), for ordinary news that mentions the prices or the
sale of a project, for a channel promoting its own posts, videos or subscription, for
useful-information posts that ask readers to share them, and for the channel's own
subscribe/footer lines. When unsure whether the editors or the company speaks, look for a
call to act and the company's contacts: both together mean an ad.

STEP 2 — is_digest (boolean)
true when ONE post bundles several unrelated stories: "yangiliklar dayjesti",
"дайджест", "kunning asosiy yangiliklari", "главное за день/неделю", or a bulleted
list of 3+ headlines on different subjects. A post about ONE subject that lists many
facts (exchange-rate table, figures from one statistics release) is NOT a digest.

STEP 3 — economic (boolean)
true when the MAIN subject is economic: prices and inflation, exchange rates, money,
banks and credit, the budget, taxes, customs duties and fees, trade, investment,
companies and markets, production and harvests, jobs, wages, pensions and benefits,
energy and utility supply and tariffs, transport and logistics as a business,
construction and real estate, tourism flows, economic laws, reforms and regulation.
false when the main subject is anything else: politics, diplomacy without concrete
economic content, war, crime and court cases (including bribery, fraud, embezzlement
by officials), accidents, weather, health, education, culture, sport, religion,
human-interest stories — even if the post mentions an amount of money, a price or a
company in passing. Also false: the structure, staff, appointments or reshuffles of
ministries and khokimiyats; buildings, aid or gifts Uzbekistan provides abroad and other
diplomacy; everyday advice and how-tos (health, cars, building materials, household tips).

STEP 4 — is_foreign (boolean)
true when the story happens OUTSIDE Uzbekistan and has no direct Uzbek party: no Uzbek
government body, region, company, citizens or migrants, no som, no Uzbek exports or
imports. false when Uzbekistan is directly involved (Uzbekistan–Kazakhstan trade, a
foreign loan to Uzbekistan, Russian rules for Uzbek migrants, a foreign company
investing in Uzbekistan). Decide it for every post, economic or not.

STEP 5 — topic (one value; "non_economic" if and only if economic=false)
  prices_inflation    consumer prices, inflation, any change of a price or TARIFF
                      (utilities, fuel, fares, food)
  currency_fx         the som exchange rate, the FX market, currency rules
  fiscal              budget, taxes, customs duties and payments, fees, fines, subsidies,
                      public spending, public debt
  trade               exports, imports, trade agreements, market access, transit and
                      logistics corridors, tourism flows
  macro               GDP, output of industry, agriculture or services, total investment,
                      reserves, remittances, balance of payments, official forecasts
  central_bank        the Central Bank of Uzbekistan (CBU, ЦБ, Markaziy bank) as the actor:
                      its policy rate and other monetary-policy decisions, its statements,
                      reviews and forecasts, its rules for banks, payments and the FX market,
                      bank licences it grants or revokes, its FX or gold operations
  banking_finance     banks, loans, deposits, capital markets, insurance, payment systems,
                      fintech
  labour_income       wages, pensions and pension rules, social benefits, employment,
                      labour migration
  energy_utility      supply and production of gas, electricity, oil, fuel and water;
                      outages; energy projects (a PRICE change is prices_inflation)
  business            companies, entrepreneurship, industrial projects and zones,
                      privatisation, business regulation, IT and startups
  construction_realty construction, housing, real estate, roads, airports and other
                      infrastructure
Exactly ONE topic per post: the one its headline and main fact are about. A detail
mentioned in passing, a background figure or a secondary measure never decides it. When
the headline and main fact themselves join several subjects, decide in this order:
  1. A decision, statement, forecast or rule OF the Central Bank of Uzbekistan ->
     central_bank, even when it is about inflation, the exchange rate or banks. The daily
     official exchange-rate post, and news that only cites CBU data, keep their own topic
     (currency_fx, banking_finance, ...). Other countries' central banks are banking_finance.
  2. A change in the LEVEL of a price, tariff, fare or fee that consumers pay ->
     prices_inflation, even when it is about energy, utilities or transport.
  3. Taxes, duties, fees to the state, the budget, public spending or debt as the measure
     itself -> fiscal.
  4. Wages, pensions, benefits, working time and conditions, employment, migration ->
     labour_income.
  5. Otherwise the area of the economy where the main fact happens.

STEP 6 — sentiment (-1.0 … +1.0)
What is the TONE of the post for Uzbekistan's economy, households or businesses: good
news, bad news, or neither? Only the sign is used (|sentiment| <= 0.15 counts as
neutral), so get the DIRECTION right. Typical strengths: 0.3 mild, 0.6 clear, 0.9 major.

A. Judge the tone of the news whatever its time: it does not matter whether the event
   has happened, is happening, or is planned, proposed, expected, forecast or agreed.
   Meetings, talks, visits, forums, memoranda, cooperation and investment agreements,
   "deals worth $X", plans, strategies, targets and forecasts get a sign whenever their
   economic tone is clear: new investment, projects, production, jobs, exports, wider
   trade or cooperation, growth targets, better forecasts, support measures -> positive;
   coming price, tariff, tax or fee rises, cuts in benefits, worse forecasts, closures,
   failed or cancelled deals -> negative.
B. The direction rules (the same for facts and for expectations):
   - prices, tariffs, fares, inflation, taxes, duties, fees, fines UP -> negative;
     DOWN -> positive.
   - GDP, output, exports, investment inflows, tourist arrivals, jobs, wages, pensions,
     benefits, reserves, sales, profits UP -> positive; DOWN -> negative.
   - EXCHANGE RATE: the som is what matters, and it moves OPPOSITE to the dollar/euro
     rate. Dollar/euro rate DOWN ("kurs tushdi/pasaydi", "доллар подешевел", "курс
     снизился", a new low of the dollar) = som STRONGER -> positive. Dollar/euro rate
     UP ("kurs oshdi/ko'tarildi", "доллар подорожал/вырос") = som WEAKER -> negative.
     A falling dollar is NEVER negative. Daily central-bank rate posts follow this rule.
   - Central bank policy rate cut -> positive; hike -> negative; unchanged -> 0.0.
   - Tax relief, subsidies, simpler procedures, abolished requirements, new support
     schemes -> positive. Shortages, outages, bans, new restrictions, layoffs,
     closures, bankruptcies, defaults, arrears, losses -> negative.
   - A plant, road, airport, warehouse or service opened, launched or to be built;
     financing approved, disbursed or promised -> positive.
C. 0.0 only when the post has no clear economic tone: a protocol meeting or visit that
   names no economic content, appointments, anniversaries, awards, company rankings,
   explanations of procedures, statistics without a clear direction, a policy rate
   left unchanged.
D. Judge the tone FOR THE CHOSEN TOPIC: what the headline and main fact mean for that
   area of Uzbekistan's economy, households or businesses. Other measures in the same
   post do not change the sign. Respect negation ("prices will NOT be raised" is not
   negative). Judge the effect on Uzbekistan, never on a foreign party. If
   economic=false or is_foreign=true, sentiment = 0.0.

EXAMPLES (headline -> labels)
 "Доллар подешевел до 11 760 сумов"
     -> economic, currency_fx, sentiment +0.5 (som stronger)
 "Dollar kursi 12 100 so'mgacha ko'tarildi"
     -> economic, currency_fx, sentiment -0.5 (som weaker)
 "Inflyatsiya avgust oyida 7,9 foizgacha sekinlashdi"
     -> economic, prices_inflation, +0.6
 "Тошкентда метро ва автобус йўлкирасини 2 500 сўмгача ошириш таклиф қилинди"
     -> economic, prices_inflation, -0.5 (formal proposal with a number)
 "Президент провёл переговоры с делегацией Siemens о новых проектах"
     -> economic, business, +0.3 (talks on new projects)
 "Samarqandda 2 mlrd dollarlik 15 ta investitsiya kelishuvi imzolandi"
     -> economic, business, +0.5 (investment agreements)
 "Hukumat 2030 yilgacha eksportni 45 mlrd dollarga yetkazishni maqsad qilgan"
     -> economic, trade, +0.4 (growth target)
 "2027 yildan elektr energiyasi tariflarini oshirish rejalashtirilmoqda"
     -> economic, energy_utility, -0.5 (planned tariff rise)
 "«Корзинка» назначила нового генерального директора"
     -> economic, business, 0.0 (appointment)
 "В Навоийской области запустили завод медного проката, создано 800 рабочих мест"
     -> economic, business, +0.6 (launched, jobs created)
 "ЦБ сохранил основную ставку на уровне 14%"
     -> economic, central_bank, 0.0 (unchanged)
 "Markaziy bank asosiy stavkani 13,5 foizgacha pasaytirdi"
     -> economic, central_bank, +0.6 (rate cut)
 "Markaziy bank 2027 yilda inflyatsiya 5 foizgacha pasayishini kutmoqda"
     -> economic, central_bank, +0.4 (better forecast)
 "Markaziy bank O'zbekistondagi bir bankning litsenziyasini qaytarib oldi"
     -> economic, central_bank, -0.5 (a bank closed)
 "Аҳоли учун электр энергияси тарифи 1 январдан 20 фоизга оширилади"
     -> economic, prices_inflation (a price level, not energy_utility), -0.6
 "Кекса ёшлилар учун қисқартирилган иш вақти жорий этиш режалаштирилмоқда" (the post also
  plans social tax for the self-employed)
     -> economic, labour_income, +0.4 (the tone for its topic; the tax part does not decide)
 "Фарғонада электр таъминоти 6 соатга узилди"
     -> economic, energy_utility, -0.5 (outage)
 "Rossiyada O'zbekiston fuqarolari uchun mehnat patenti narxi oshirildi"
     -> economic, labour_income, not foreign (Uzbek migrants), -0.5
 "ФРС США снизила ставку на 0,25 п.п."
     -> economic, banking_finance, is_foreign, 0.0
 "Солиқ инспектори 5 минг доллар пора олаётганда ушланди"
     -> economic=false (crime), non_economic, 0.0
 "Kunning asosiy yangiliklari: • ... • ... • ..."
     -> is_digest
 "Кредит до 300 млн сумов без залога — оформите в приложении банка за 5 минут"
     -> is_ad

STEP 7 — headline (text)
The post's own headline, copied exactly without formatting, when it starts with one (a short
first line or a bold title that states what happened). A post without one gets a short
headline you write in the post's language (at most 90 characters) that states its main fact
and adds nothing that is not in the post. Hashtags, channel slogans and labels ("#Тезкор",
"Диққат", "МУҲИМ ЯНГИЛИК", "Ана холос", "Расман") are not headlines: leave them out, and write
one when nothing else is left. Ads and digests get a headline too.

OUTPUT
Return ONLY a JSON object {"results": [...]} with exactly one object per post, in the
given order. Each object starts with "id" = the number of its POST."""

_ITEM = {
    "type": "OBJECT",
    "properties": {
        "id": {"type": "INTEGER"},
        "is_ad": {"type": "BOOLEAN"},
        "is_digest": {"type": "BOOLEAN"},
        "economic": {"type": "BOOLEAN"},
        "is_foreign": {"type": "BOOLEAN"},
        "topic": {"type": "STRING", "enum": CATEGORIES},
        "sentiment": {"type": "NUMBER"},
        "headline": {"type": "STRING"},
    },
    "required": ["id", "is_ad", "is_digest", "economic", "is_foreign", "topic",
                 "sentiment", "headline"],
    # answer in the order of the decision steps above
    "propertyOrdering": ["id", "is_ad", "is_digest", "economic", "is_foreign", "topic",
                         "sentiment", "headline"],
}

# Gemini structured-output schema (OpenAPI subset): object with a "results" array.
RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {"results": {"type": "ARRAY", "items": _ITEM}},
    "required": ["results"],
}


def _json_schema(s):
    """The same schema in standard JSON Schema for OpenAI's strict Structured Outputs:
    lower-case types, every object closed (additionalProperties false); property order
    is the order of "properties"."""
    out = {k: v for k, v in s.items() if k != "propertyOrdering"}
    out["type"] = s["type"].lower()
    if "properties" in s:
        out["properties"] = {k: _json_schema(v) for k, v in s["properties"].items()}
        out["additionalProperties"] = False
    if "items" in s:
        out["items"] = _json_schema(s["items"])
    return out


OPENAI_SCHEMA = _json_schema(RESPONSE_SCHEMA)


def build_user_prompt(texts, channels=None):
    """Number the posts (and name their channel) so each label comes back with its id."""
    n = len(texts)
    lines = [f'Label these {n} posts. Return {{"results": [...]}} with exactly {n} objects, '
             f"ids 0 to {n - 1} in this order.\n"]
    for i, t in enumerate(texts):
        source = f" | {channels[i]}" if channels else ""
        lines.append(f"--- POST {i}{source} ---\n{t}\n")
    return "\n".join(lines)
