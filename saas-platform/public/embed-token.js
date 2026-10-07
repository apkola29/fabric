// When the browser asks for a new embed token. Shared by the app and the back office, and tested in Node.
//
// Microsoft's refresh sample checks every 30 seconds and refreshes with 10 minutes left. Shorter tokens
// (EMBED_TOKEN_MINUTES can be as low as 5) refresh once a third of their lifetime is left instead, so a token is
// never due the moment it arrives. Time counts from when the token arrived (`expiresInSeconds`, by the server's
// clock), so a wrong device clock doesn't matter.
// https://learn.microsoft.com/javascript/api/overview/powerbi/refresh-token

export const TOKEN_CHECK_MS = 30_000;
export const REFRESH_BEFORE_MS = 10 * 60_000;

// The time (by this device's clock) to ask for a new token, given the embed response that brought the current one.
export function refreshTimeOf(embed, now = Date.now()) {
  const lifetimeMs = Number.isFinite(embed?.expiresInSeconds) ? embed.expiresInSeconds * 1000 : Date.parse(embed?.expiration) - now;
  if (!Number.isFinite(lifetimeMs) || lifetimeMs <= 0) return now;
  return now + lifetimeMs - Math.min(REFRESH_BEFORE_MS, lifetimeMs / 3);
}
