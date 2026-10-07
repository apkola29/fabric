import assert from 'node:assert/strict';
import { test } from 'node:test';
import { REFRESH_BEFORE_MS, TOKEN_CHECK_MS, refreshTimeOf } from '../public/embed-token.js';

// The browser side of embed tokens: when the app and the back office ask for a new one.

const minutes = (ms) => Math.round((ms / 60_000) * 100) / 100;

test('embed tokens are refreshed on time whatever their lifetime, and never the moment they arrive', () => {
  const now = 1_000_000;
  assert.equal(minutes(refreshTimeOf({ expiresInSeconds: 1800 }, now) - now), 20, "a 30-minute token: 10 minutes before, as in Microsoft's sample");
  assert.equal(minutes(refreshTimeOf({ expiresInSeconds: 3600 }, now) - now), 50, 'an hour-long token: still 10 minutes before');
  assert.equal(minutes(refreshTimeOf({ expiresInSeconds: 600 }, now) - now), 6.67, 'a 10-minute token: with a third of its lifetime left');
  const fiveMinutes = refreshTimeOf({ expiresInSeconds: 300 }, now) - now;
  assert.ok(fiveMinutes > 6 * TOKEN_CHECK_MS, 'a 5-minute token is checked several times before it is due');
  assert.equal(REFRESH_BEFORE_MS, 10 * 60_000);
});

test('time counts from when the token arrived; without expiresInSeconds the expiration decides', () => {
  const now = 1_000_000;
  const thirtyMinutesFromNow = new Date(now + 30 * 60_000).toISOString();
  assert.equal(minutes(refreshTimeOf({ expiration: thirtyMinutesFromNow }, now) - now), 20);
  const fastClock = now + 21 * 60_000;
  assert.equal(minutes(refreshTimeOf({ expiresInSeconds: 1800, expiration: thirtyMinutesFromNow }, fastClock) - fastClock), 20, 'a device clock 21 minutes fast changes nothing');
  assert.equal(refreshTimeOf({}, now), now, 'nothing usable: refresh at the next check');
  assert.equal(refreshTimeOf({ expiresInSeconds: 0 }, now), now);
});
