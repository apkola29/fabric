import { Readable, Writable } from 'node:stream';

// Calls the HTTP handler in-process with fake request/response objects (no sockets needed). `remoteAddress` is the
// caller's network address, when a test needs one.
export async function inject(handler, { method = 'GET', url, headers = {}, body, remoteAddress } = {}) {
  let payload = [];
  const requestHeaders = Object.fromEntries(Object.entries(headers).map(([key, value]) => [key.toLowerCase(), value]));
  if (body !== undefined) {
    if (Buffer.isBuffer(body) || typeof body === 'string') payload = [Buffer.from(body)];
    else {
      payload = [Buffer.from(JSON.stringify(body))];
      requestHeaders['content-type'] ||= 'application/json';
    }
  }
  const req = Readable.from(payload);
  Object.assign(req, { method, url, headers: requestHeaders });
  if (remoteAddress) req.socket = { remoteAddress };

  const chunks = [];
  const res = new Writable({
    write(chunk, _encoding, callback) {
      chunks.push(Buffer.from(chunk));
      callback();
    },
  });
  Object.assign(res, { statusCode: 200, headersSent: false, sentHeaders: {} });
  res.setHeader = (key, value) => {
    res.sentHeaders[key.toLowerCase()] = value;
  };
  res.writeHead = (status, extra = {}) => {
    res.statusCode = status;
    for (const [key, value] of Object.entries(extra)) res.setHeader(key, value);
    res.headersSent = true;
    return res;
  };
  const finished = new Promise((resolve) => res.on('finish', resolve));
  await handler(req, res);
  await finished;
  const text = Buffer.concat(chunks).toString('utf8');
  return { status: res.statusCode, headers: res.sentHeaders, text, json: () => JSON.parse(text) };
}

// A scripted fetch: each route returns a Response (or a function producing one). Records every call.
export function scriptedFetch(routes) {
  const calls = [];
  const fetchImpl = async (url, init = {}) => {
    const call = { url: String(url), method: init.method || 'GET', headers: init.headers || {}, body: init.body };
    calls.push(call);
    for (const route of routes) {
      const matches = route.match instanceof RegExp ? route.match.test(call.url) : call.url.includes(route.match);
      if (matches && (!route.method || route.method === call.method)) {
        const next = Array.isArray(route.respond) ? route.respond.shift() : route.respond;
        if (!next) throw new Error(`No more scripted responses for ${call.method} ${call.url}`);
        return typeof next === 'function' ? next(call) : next.clone();
      }
    }
    throw new Error(`Unexpected request: ${call.method} ${call.url}`);
  };
  return { fetchImpl, calls };
}

export const json = (status, body, headers = {}) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status, headers: { 'content-type': 'application/json', ...headers } });

export const staticTokens = { getToken: async (scope) => `token-for-${scope}`, describe: () => ({ mode: 'test', label: 'Test' }) };
