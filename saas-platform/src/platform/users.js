import { randomBytes, randomUUID, scrypt as scryptCallback, timingSafeEqual } from 'node:crypto';
import { promisify } from 'node:util';
import { TERRITORIES } from '../crm/workload.js';
import { HttpError } from '../http/router.js';
import { emailDomain } from './sessions.js';

// Named sign-ins for customers' users in the local prototype: the platform team adds each person and gives them a
// password. Passwords are hashed with scrypt at OWASP's minimum cost and must be at least 15 characters (NIST SP
// 800-63B-4 for password-only sign-in). A real deployment signs people in with Microsoft Entra External ID or the
// customer's own Entra ID instead, and keeps this module only for the tenant mapping.

const scrypt = promisify(scryptCallback);
const COST = { N: 2 ** 17, r: 8, p: 1 };
const KEY_LENGTH = 32;
const MAX_MEMORY = 256 * 1024 * 1024;
export const MIN_PASSWORD_LENGTH = 15;
const MAX_PASSWORD_LENGTH = 256;
const MAX_USERS_PER_CUSTOMER = 500;

export class UserError extends HttpError {
  constructor(message, status = 400) {
    super(status, message);
  }
}

const derive = (password, salt, length, { N, r, p }) => scrypt(String(password).normalize('NFKC'), salt, length, { N, r, p, maxmem: MAX_MEMORY });

export async function hashPassword(password) {
  const salt = randomBytes(16);
  const key = await derive(password, salt, KEY_LENGTH, COST);
  return ['scrypt', COST.N, COST.r, COST.p, salt.toString('base64'), key.toString('base64')].join('$');
}

export async function verifyPassword(password, stored) {
  const [scheme, N, r, p, salt, hash] = String(stored || '').split('$');
  if (scheme !== 'scrypt' || !salt || !hash || typeof password !== 'string') return false;
  const expected = Buffer.from(hash, 'base64');
  const key = await derive(password, Buffer.from(salt, 'base64'), expected.length, { N: Number(N), r: Number(r), p: Number(p) });
  return timingSafeEqual(key, expected);
}

// Unknown emails cost the same as wrong passwords, so response times don't reveal who has an account.
let decoy = null;
export async function rejectSlowly(password) {
  decoy ||= hashPassword(randomBytes(24).toString('base64'));
  await verifyPassword(String(password || ''), await decoy);
  return false;
}

// 20 characters from 120 random bits.
export const generatePassword = () => randomBytes(15).toString('base64url');

export function checkPassword(password) {
  if (typeof password !== 'string' || [...password].length < MIN_PASSWORD_LENGTH) throw new UserError(`Passwords need at least ${MIN_PASSWORD_LENGTH} characters.`);
  if (password.length > MAX_PASSWORD_LENGTH) throw new UserError(`Passwords can be at most ${MAX_PASSWORD_LENGTH} characters.`);
  return password;
}

export const normalizeEmail = (email) => String(email || '').trim().toLowerCase();
export const usersOf = (tenant) => tenant.users || [];
export const findUser = (tenant, email) => usersOf(tenant).find((u) => u.email === normalizeEmail(email)) || null;

// What each person may see. Sales managers see every territory; sales reps see the accounts in their territories, in
// the CRM, the reports and the assistant. The demo sign-in (no named sign-ins) and sign-ins from before roles existed
// keep the full access they had.
export const ROLES = { manager: 'Sales manager', rep: 'Sales rep' };

// Report permissions per person, as in Microsoft's App-Owns-Data Starter Kit: everyone who has reports may view them;
// editing a report (Save) and creating reports (New report, Save as) are granted per person. They take effect only
// where the edition includes report authoring and REPORT_AUTHORING is on.
export const REPORT_RIGHTS = { edit: 'Edit reports', create: 'Create reports' };

export function reportRightsOf(user) {
  // The demo sign-in (no named sign-ins) keeps the full access it had.
  if (!user) return { edit: true, create: true };
  return { edit: Boolean(user.canEdit), create: Boolean(user.canCreate) };
}

export function accessOf(user) {
  if (!user || user.role !== 'rep') return { role: 'manager', territories: null };
  return { role: 'rep', territories: TERRITORIES.filter((t) => (user.territories || []).includes(t)) };
}

export function checkAccess(role, territories) {
  if (!Object.hasOwn(ROLES, role)) throw new UserError('Choose a role: manager (every territory) or rep (named territories).');
  if (role === 'manager') return { role, territories: [] };
  const list = [...new Set((Array.isArray(territories) ? territories : [territories]).filter(Boolean).map(String))];
  const unknown = list.filter((t) => !TERRITORIES.includes(t));
  if (unknown.length) throw new UserError(`Unknown territory: ${unknown.join(', ')}. Territories are ${TERRITORIES.join(', ')}.`);
  if (!list.length) throw new UserError('Choose at least one territory for a sales rep.');
  return { role, territories: TERRITORIES.filter((t) => list.includes(t)) };
}

// What the back office may show: never the password hash.
export const publicUser = ({ id, email, name, role, territories, canEdit, canCreate, createdAt, passwordSetAt, lastSignInAt }) => {
  const access = accessOf({ role, territories });
  return { id, email, name, role: access.role, territories: access.territories || [], canEdit: Boolean(canEdit), canCreate: Boolean(canCreate), createdAt, passwordSetAt, lastSignInAt: lastSignInAt || null };
};

// A person signs in to one customer only, and their email must use one of that customer's sign-in domains.
export async function addUser({ store, tenant, email, name = '', password = null, role, territories = [], canEdit = false, canCreate = false }) {
  const address = normalizeEmail(email);
  const domain = emailDomain(address);
  if (!domain) throw new UserError('Enter a valid email address.');
  if (!(tenant.domains || []).includes(domain)) {
    throw new UserError(`${address} isn't on one of ${tenant.name}'s sign-in domains (${(tenant.domains || []).join(', ') || 'none set'}).`);
  }
  const access = checkAccess(role, territories);
  const owner = store.list().find((t) => findUser(t, address));
  if (owner) throw new UserError(owner.id === tenant.id ? `${address} already has a sign-in.` : `${address} already signs in to another customer.`, 409);
  if (usersOf(tenant).length >= MAX_USERS_PER_CUSTOMER) throw new UserError(`A customer can have at most ${MAX_USERS_PER_CUSTOMER} sign-ins here.`);
  const label = String(name || '').trim().replace(/\s+/g, ' ').slice(0, 80);
  const chosen = password === null || password === undefined || password === '' ? generatePassword() : checkPassword(password);
  const passwordHash = await hashPassword(chosen);
  // Hashing takes a moment; someone else may have added the same person meanwhile.
  if (store.list().some((t) => findUser(t, address))) throw new UserError(`${address} already has a sign-in.`, 409);
  const now = new Date().toISOString();
  const user = { id: randomUUID(), email: address, name: label, ...access, canEdit: canEdit === true, canCreate: canCreate === true, passwordHash, sessionVersion: 1, createdAt: now, passwordSetAt: now, lastSignInAt: null };
  tenant.users = [...usersOf(tenant), user];
  return { user, password: password ? null : chosen };
}

// A new role, territories or report permissions end the person's sessions, so an open report never keeps access they
// no longer have.
export function updateUser({ tenant, userId, name, role, territories, canEdit, canCreate }) {
  const user = usersOf(tenant).find((u) => u.id === userId);
  if (!user) throw new UserError('There is no such sign-in.', 404);
  if (name !== undefined) user.name = String(name || '').trim().replace(/\s+/g, ' ').slice(0, 80);
  let changed = false;
  if (role !== undefined || territories !== undefined) {
    const before = accessOf(user);
    const access = checkAccess(role ?? before.role, territories ?? before.territories ?? []);
    changed = access.role !== before.role || access.territories.join('|') !== (before.territories || []).join('|');
    Object.assign(user, access);
  }
  for (const [key, value] of [['canEdit', canEdit], ['canCreate', canCreate]]) {
    if (value === undefined || value === null) continue;
    if (typeof value !== 'boolean') throw new UserError(`${key} must be true or false.`);
    if (Boolean(user[key]) !== value) changed = true;
    user[key] = value;
  }
  if (changed) user.sessionVersion = (user.sessionVersion || 1) + 1;
  return { user, signedOut: changed };
}

// A new password ends the person's existing sessions.
export async function resetPassword({ tenant, userId, password = null }) {
  const user = usersOf(tenant).find((u) => u.id === userId);
  if (!user) throw new UserError('There is no such sign-in.', 404);
  const chosen = password ? checkPassword(password) : generatePassword();
  user.passwordHash = await hashPassword(chosen);
  user.sessionVersion = (user.sessionVersion || 1) + 1;
  user.passwordSetAt = new Date().toISOString();
  return { user, password: password ? null : chosen };
}

export function removeUser({ tenant, userId }) {
  const user = usersOf(tenant).find((u) => u.id === userId);
  if (!user) throw new UserError('There is no such sign-in.', 404);
  tenant.users = usersOf(tenant).filter((u) => u.id !== userId);
  return user;
}
