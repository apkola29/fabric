import { CLOSED_STAGES, STAGE_PROBABILITY, TERRITORIES } from './schema.js';

// Fabricated but realistic CRM data for one customer company. Deterministic per seed and day: the dates are relative to
// the day the data is loaded, so a pilot set up next year still has an open pipeline, this year's wins and planned
// activities.

const DAY = 86_400_000;
const pad = (n, width = 4) => String(n).padStart(width, '0');
const isoDate = (ms) => new Date(ms).toISOString().slice(0, 10);
const CLOSED = new Set(CLOSED_STAGES);
export const utcToday = () => new Date().toISOString().slice(0, 10);

// The calendar a CRM without sample data starts with: the last two years through the end of next year.
export function defaultCalendarRange(today = utcToday()) {
  const year = Number(today.slice(0, 4));
  return { from: `${year - 2}-01-01`, to: `${year + 1}-12-31` };
}

export function createRandom(seedText) {
  let seed = [...String(seedText)].reduce((hash, char) => Math.imul(hash ^ char.charCodeAt(0), 16777619) >>> 0, 2166136261);
  return () => {
    seed = (seed + 0x6d2b79f5) >>> 0;
    let t = seed;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function calendarRows(from = defaultCalendarRange().from, to = defaultCalendarRange().to) {
  const rows = [];
  for (let t = Date.parse(`${from}T00:00:00Z`), end = Date.parse(`${to}T00:00:00Z`); t <= end; t += DAY) {
    const d = new Date(t);
    const year = d.getUTCFullYear();
    const month = d.getUTCMonth() + 1;
    const weekday = (d.getUTCDay() + 6) % 7;
    rows.push({
      date: isoDate(t),
      year,
      quarter: `Q${Math.ceil(month / 3)}`,
      month,
      month_name: d.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' }),
      year_month: `${year}-${pad(month, 2)}`,
      month_start: `${year}-${pad(month, 2)}-01`,
      week_start: isoDate(t - weekday * DAY),
    });
  }
  return rows;
}

// Accounts per territory (a US state) and the cities they're in.
const PLACES = {
  Texas: { weight: 45, cities: ['Austin', 'Dallas', 'Houston', 'San Antonio', 'El Paso', 'Fort Worth'] },
  'New Mexico': { weight: 20, cities: ['Albuquerque', 'Santa Fe', 'Las Cruces', 'Roswell'] },
  Georgia: { weight: 35, cities: ['Atlanta', 'Savannah', 'Augusta', 'Macon', 'Athens'] },
};
// Every customer gets its own sales team, drawn from these pools by the customer's seed: three reps for Texas, three
// for Georgia and two for New Mexico, plus a sales manager. Rep IDs stay rep-01 to rep-08.
const REP_POOLS = {
  Texas: ['Avery Chen', 'Jordan Patel', 'Sam Rivera', 'Casey Morgan', 'Drew Collins', 'Jamie Ortiz', 'Logan Reed', 'Harper Quinn', 'Reese Walker'],
  'New Mexico': ['Luis Romero', 'Priya Nair', 'Elena Vigil', 'Mateo Baca', 'Mei Lin', 'Arjun Mehta'],
  Georgia: ['Grace Kim', 'Taylor Brooks', 'Morgan Lee', 'Riley Schmidt', 'Amara Okoye', 'Noah Jansen', 'Marcus Bell', 'Elodie Martin'],
};
const TEAM_SHAPE = [['Texas', 3], ['Georgia', 3], ['New Mexico', 2]];
const MANAGERS = ['Maria Alvarez', 'Daniel Okafor', 'Nadia Hassan', 'Owen Fischer', 'Leah Thompson', 'Victor Ramos'];
for (const territory of TERRITORIES) if (!PLACES[territory] || !REP_POOLS[territory]) throw new Error(`The sample data has no places or reps for the ${territory} territory.`);

const workEmail = (name, domain) => `${name.toLowerCase().replace(/[^a-z]+/g, '.')}@${domain}`;

// Sample data is seeded from the customer's name (its slug), so a demo customer called Fabrikam always gets the same
// sales team and accounts, on any machine. Real customers start with an empty CRM.
export const sampleSeedOf = (tenant) => tenant.slug || tenant.id;

// The customer's sales manager and reps. Deterministic per seed, and independent of the rest of the sample data.
export function salesTeam(seedText, companyDomain = 'example.com') {
  const random = createRandom(`${seedText}|team`);
  const take = (pool) => pool.splice(Math.floor(random() * pool.length), 1)[0];
  const manager = take([...MANAGERS]);
  const reps = [];
  for (const [territory, size] of TEAM_SHAPE) {
    const pool = [...REP_POOLS[territory]];
    for (let i = 0; i < size; i++) {
      const name = take(pool);
      reps.push({ rep_id: `rep-${pad(reps.length + 1, 2)}`, name, email: workEmail(name, companyDomain), region: territory });
    }
  }
  return { manager: { name: manager, email: workEmail(manager, companyDomain) }, reps };
}

// The people a pilot signs in as: the sales manager (every territory) and one rep per territory. Their emails match
// the sales team in the CRM, so a rep's sign-in and the accounts they own line up.
export function pilotPersonas(seedText, companyDomain) {
  const { manager, reps } = salesTeam(seedText, companyDomain);
  return [
    { role: 'manager', name: manager.name, email: manager.email, territories: [] },
    ...TERRITORIES.map((territory) => {
      const rep = reps.find((r) => r.region === territory);
      return { role: 'rep', name: rep.name, email: rep.email, territories: [territory] };
    }),
  ];
}
const NAME_PARTS = [
  ['North', 'Blue', 'Summit', 'Harbor', 'Granite', 'Cedar', 'Bright', 'Iron', 'Silver', 'Prairie', 'Coastal', 'Evergreen', 'Atlas', 'Pioneer', 'Redwood', 'Lakeside'],
  ['Labs', 'Partners', 'Health', 'Foods', 'Logistics', 'Systems', 'Clinics', 'Supply', 'Works', 'Group', 'Energy', 'Retail', 'Academy', 'Motors', 'Analytics', 'Freight'],
];
const INDUSTRY_BY_SUFFIX = {
  Health: 'Healthcare', Clinics: 'Healthcare', Foods: 'Retail', Retail: 'Retail', Logistics: 'Logistics', Freight: 'Logistics',
  Systems: 'Software', Analytics: 'Software', Labs: 'Software', Energy: 'Energy', Academy: 'Education', Motors: 'Manufacturing',
  Works: 'Manufacturing', Supply: 'Manufacturing', Partners: 'Financial Services', Group: 'Financial Services',
};
const FIRST = ['Ana', 'Ben', 'Chloe', 'Diego', 'Elena', 'Farah', 'Gabe', 'Hana', 'Ivan', 'Jade', 'Kofi', 'Lena', 'Mateo', 'Nora', 'Omar', 'Pia', 'Quinn', 'Rosa', 'Sven', 'Tara', 'Umar', 'Vera', 'Wes', 'Yuki'];
const LAST = ['Adams', 'Berg', 'Costa', 'Dubois', 'Evans', 'Fischer', 'Garcia', 'Hughes', 'Ito', 'Jensen', 'Khan', 'Lopez', 'Moreau', 'Novak', 'Okafor', 'Park', 'Quist', 'Rossi', 'Silva', 'Tanaka', 'Usman', 'Varga', 'Weber', 'Young'];
const TITLES = ['CEO', 'CFO', 'Head of Operations', 'IT Director', 'Procurement Manager', 'VP Sales', 'Data Lead', 'Office Manager'];
const PRODUCTS = ['Platform license', 'Analytics add-on', 'Support renewal', 'Expansion', 'Pilot', 'Training package', 'Integration services'];
const SUBJECTS = {
  Call: ['Discovery call', 'Check-in call', 'Pricing call', 'Renewal call'],
  Email: ['Follow-up email', 'Proposal sent', 'Contract questions', 'Intro email'],
  Meeting: ['Kickoff meeting', 'Pricing review', 'Executive briefing', 'Quarterly review'],
  Demo: ['Product demo', 'Analytics demo', 'Technical deep dive'],
};
const DURATIONS = { Call: [10, 45], Email: [5, 15], Meeting: [30, 90], Demo: [45, 90] };

export function fabricateCrm(seedText, { today = utcToday(), companyDomain = 'example.com', accounts: accountCount = 120 } = {}) {
  const random = createRandom(seedText);
  const pick = (list) => list[Math.floor(random() * list.length)];
  const int = (min, max) => min + Math.floor(random() * (max - min + 1));
  const weighted = (pairs) => {
    let r = random() * pairs.reduce((sum, [, weight]) => sum + weight, 0);
    for (const [value, weight] of pairs) if ((r -= weight) <= 0) return value;
    return pairs[pairs.length - 1][0];
  };
  const todayMs = Date.parse(`${today}T00:00:00Z`);
  if (!Number.isFinite(todayMs)) throw new Error(`today must be a date (YYYY-MM-DD), not "${today}".`);
  // Accounts were added over the 2.75 years up to 15 weeks ago; deals close from 20 months ago to 10 weeks ahead.
  const accountsFromMs = todayMs - 1004 * DAY;
  const closesFromMs = todayMs - 624 * DAY;
  const stamp = (ms) => new Date(ms).toISOString();
  const atHour = (ms) => ms + int(8, 17) * 3_600_000 + int(0, 59) * 60_000;

  const salesReps = salesTeam(seedText, companyDomain).reps;

  // Three focus industries per customer make about 60% of its accounts, so two customers' books look different.
  const industries = [...new Set(Object.values(INDUSTRY_BY_SUFFIX))];
  const focus = new Set();
  while (focus.size < 3) focus.add(pick(industries));
  const focusSuffixes = NAME_PARTS[1].filter((s) => focus.has(INDUSTRY_BY_SUFFIX[s]));
  const pickSuffix = () => (random() < 0.6 ? pick(focusSuffixes) : pick(NAME_PARTS[1]));

  const accounts = [];
  const usedNames = new Set();
  while (accounts.length < accountCount) {
    const prefix = pick(NAME_PARTS[0]);
    const suffix = pickSuffix();
    let name = `${prefix} ${suffix}`;
    if (usedNames.has(name)) name = `${prefix} ${suffix} ${pick(['Co', 'International', 'Holdings', 'Inc'])}`;
    if (usedNames.has(name)) continue;
    usedNames.add(name);
    const state = weighted(Object.entries(PLACES).map(([key, value]) => [key, value.weight]));
    const revenue = Math.round(10 ** (6 + random() * 2.7) / 1000) * 1000;
    const created = accountsFromMs + Math.floor(random() * 900) * DAY;
    accounts.push({
      account_id: `acc-${pad(accounts.length + 1)}`,
      name,
      industry: INDUSTRY_BY_SUFFIX[suffix] || 'Software',
      country: 'United States',
      city: pick(PLACES[state].cities),
      state,
      annual_revenue: revenue,
      employees: Math.max(5, Math.round(revenue / int(150_000, 400_000))),
      owner_id: pick(salesReps.filter((r) => r.region === state)).rep_id,
      created_at: stamp(atHour(created)),
      updated_at: stamp(atHour(Math.min(todayMs - DAY, created + int(10, 300) * DAY))),
    });
  }

  const contacts = [];
  for (const account of accounts) {
    const domain = `${account.name.toLowerCase().replace(/[^a-z]+/g, '')}.com`;
    for (let i = 0, n = int(2, 4); i < n; i++) {
      const first = pick(FIRST);
      const last = pick(LAST);
      contacts.push({
        contact_id: `con-${pad(contacts.length + 1)}`,
        account_id: account.account_id,
        first_name: first,
        last_name: last,
        email: `${first}.${last}@${domain}`.toLowerCase(),
        phone: `+1-555-${pad(int(100, 999), 3)}-${pad(int(0, 9999))}`,
        title: pick(TITLES),
        created_at: account.created_at,
        updated_at: account.updated_at,
      });
    }
  }

  const opportunities = [];
  const activities = [];
  const addActivity = (account, opportunity, dateMs, owner) => {
    const type = weighted([['Email', 40], ['Call', 30], ['Meeting', 20], ['Demo', 10]]);
    const [min, max] = DURATIONS[type];
    activities.push({
      activity_id: `act-${pad(activities.length + 1, 5)}`,
      account_id: account.account_id,
      opportunity_id: opportunity?.opportunity_id ?? null,
      type,
      subject: pick(SUBJECTS[type]),
      activity_date: isoDate(dateMs),
      duration_minutes: int(min, max),
      completed: dateMs <= todayMs,
      owner_id: owner,
      created_at: stamp(atHour(Math.min(dateMs, todayMs))),
      updated_at: stamp(atHour(Math.min(dateMs, todayMs))),
    });
  };

  for (const account of accounts) {
    const count = weighted([[1, 20], [2, 30], [3, 25], [4, 15], [6, 10]]);
    const accountDayMs = Math.floor(Date.parse(account.created_at) / DAY) * DAY;
    for (let i = 0; i < count; i++) {
      // A deal closes at least 30 days after its account was added.
      let closeMs = Math.max(accountDayMs + 30 * DAY, closesFromMs + Math.floor(random() * 700) * DAY);
      // Deals well past their close date are decided; recent ones may still be open (overdue), future ones mostly open.
      const overdueDays = (todayMs - closeMs) / DAY;
      const stage =
        overdueDays > 45
          ? weighted([['Closed Won', 55], ['Closed Lost', 45]])
          : overdueDays > 0
            ? weighted([['Closed Won', 40], ['Closed Lost', 25], ['Negotiation', 15], ['Proposal', 12], ['Qualification', 8]])
            : weighted([['Prospecting', 30], ['Qualification', 25], ['Proposal', 22], ['Negotiation', 15], ['Closed Won', 5], ['Closed Lost', 3]]);
      // A deal decided before its expected date closed on the day it was decided, which is in the past.
      if (CLOSED.has(stage) && closeMs > todayMs) closeMs = todayMs - Math.max(1, Math.round((closeMs - todayMs) / DAY / 3)) * DAY;
      const sizeFactor = account.annual_revenue > 50_000_000 ? 3 : account.annual_revenue > 10_000_000 ? 1.8 : 1;
      // Created after the account, before the close date, and never in the future.
      const createdMs = Math.min(todayMs - DAY, Math.max(accountDayMs, closeMs - int(30, 200) * DAY));
      // Most deals belong to the account owner; the rest to another rep in the same territory.
      const owner = random() < 0.8 ? account.owner_id : pick(salesReps.filter((r) => r.region === account.state)).rep_id;
      const opportunity = {
        opportunity_id: `opp-${pad(opportunities.length + 1)}`,
        account_id: account.account_id,
        name: `${account.name}: ${pick(PRODUCTS)}`,
        stage,
        amount: Math.round((int(5, 120) * 1000 * sizeFactor) / 500) * 500,
        probability: STAGE_PROBABILITY[stage],
        close_date: isoDate(closeMs),
        owner_id: owner,
        created_at: stamp(atHour(createdMs)),
        updated_at: stamp(atHour(Math.min(todayMs - DAY, Math.max(createdMs, closeMs - int(0, 20) * DAY)))),
      };
      opportunities.push(opportunity);
      const lastActivityMs = Math.min(closeMs, todayMs + 21 * DAY);
      for (let a = 0, n = int(1, 6); a < n; a++) {
        const span = Math.max(1, Math.floor((lastActivityMs - createdMs) / DAY));
        addActivity(account, opportunity, createdMs + int(0, span) * DAY, owner);
      }
    }
    for (let a = 0, n = int(0, 3); a < n; a++) {
      addActivity(account, null, Date.parse(account.created_at) + int(0, Math.floor((todayMs - Date.parse(account.created_at)) / DAY)) * DAY, account.owner_id);
    }
  }

  // The calendar covers every date in the data, and at least the last two years through the end of next year.
  const dates = [...accounts.map((a) => a.created_at), ...opportunities.flatMap((o) => [o.created_at, o.close_date]), ...activities.map((t) => t.activity_date)].map((d) => d.slice(0, 10)).sort();
  const range = defaultCalendarRange(today);
  const calendar = calendarRows(dates[0] < range.from ? `${dates[0].slice(0, 4)}-01-01` : range.from, dates.at(-1) > range.to ? `${dates.at(-1).slice(0, 4)}-12-31` : range.to);

  return { sales_reps: salesReps, accounts, contacts, opportunities, activities, calendar };
}
