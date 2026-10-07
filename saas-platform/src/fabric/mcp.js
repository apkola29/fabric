// Minimal MCP client (streamable HTTP) for a published Fabric data agent:
// initialize -> notifications/initialized -> tools/list -> tools/call.
// https://learn.microsoft.com/fabric/data-science/data-agent-mcp-server

export const MCP_PROTOCOL_VERSION = '2025-06-18';

export class McpError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'McpError';
    if (status) this.upstreamStatus = status;
  }
}

export class McpHttpSession {
  constructor({ url, getToken, fetchImpl = fetch, timeoutMs = 180_000 }) {
    this.url = url;
    this.getToken = getToken;
    this.fetchImpl = fetchImpl;
    this.timeoutMs = timeoutMs;
    this.nextId = 0;
    this.sessionId = null;
    this.protocolVersion = null;
  }

  async headers() {
    const headers = {
      authorization: `Bearer ${await this.getToken()}`,
      'content-type': 'application/json',
      accept: 'application/json, text/event-stream',
    };
    if (this.sessionId) headers['mcp-session-id'] = this.sessionId;
    if (this.protocolVersion) headers['mcp-protocol-version'] = this.protocolVersion;
    return headers;
  }

  async post(message) {
    const res = await this.fetchImpl(this.url, {
      method: 'POST',
      headers: await this.headers(),
      body: JSON.stringify(message),
      signal: AbortSignal.timeout(this.timeoutMs),
    });
    const sessionId = res.headers.get('mcp-session-id');
    if (sessionId) this.sessionId = sessionId;
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new McpError(`MCP ${message.method} failed (HTTP ${res.status}): ${text.slice(0, 300) || res.statusText}`, res.status);
    }
    if (message.id === undefined || res.status === 202) {
      await res.body?.cancel().catch(() => {});
      return null;
    }
    const type = res.headers.get('content-type') || '';
    if (type.includes('text/event-stream')) return readSseResponse(res, message.id);
    const body = await res.json();
    return Array.isArray(body) ? body.find((m) => m?.id === message.id) : body;
  }

  async request(method, params = {}) {
    const id = ++this.nextId;
    const message = await this.post({ jsonrpc: '2.0', id, method, params });
    if (!message) throw new McpError(`The MCP server sent no response to ${method}.`);
    if (message.error) throw new McpError(`MCP ${method} error ${message.error.code}: ${message.error.message}`);
    return message.result;
  }

  async initialize(clientInfo) {
    const result = await this.request('initialize', { protocolVersion: MCP_PROTOCOL_VERSION, capabilities: {}, clientInfo });
    this.protocolVersion = result?.protocolVersion || MCP_PROTOCOL_VERSION;
    await this.post({ jsonrpc: '2.0', method: 'notifications/initialized' });
    return result;
  }

  async close() {
    if (!this.sessionId) return;
    const res = await this.fetchImpl(this.url, { method: 'DELETE', headers: await this.headers(), signal: AbortSignal.timeout(10_000) });
    await res.body?.cancel().catch(() => {});
  }
}

async function readSseResponse(res, id) {
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (value) buffer += decoder.decode(value, { stream: true });
      if (done) buffer += '\n\n';
      buffer = buffer.replace(/\r\n/g, '\n');
      let boundary;
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const event = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const data = event
          .split('\n')
          .filter((line) => line.startsWith('data:'))
          .map((line) => line.slice(5).replace(/^ /, ''))
          .join('\n');
        if (!data) continue;
        let parsed;
        try {
          parsed = JSON.parse(data);
        } catch {
          continue;
        }
        const hit = (Array.isArray(parsed) ? parsed : [parsed]).find((m) => m && m.id === id && ('result' in m || 'error' in m));
        if (hit) return hit;
      }
      if (done) break;
    }
  } finally {
    reader.cancel().catch(() => {});
  }
  throw new McpError('The MCP stream ended before the data agent answered.');
}

export async function askDataAgentOverMcp({ url, getToken, question, fetchImpl = fetch, timeoutMs, clientInfo = { name: 'fabric-saas-platform', version: '0.1.0' } }) {
  const session = new McpHttpSession({ url, getToken, fetchImpl, timeoutMs });
  try {
    await session.initialize(clientInfo);
    const listed = await session.request('tools/list');
    const tool = listed?.tools?.[0];
    if (!tool) throw new McpError('The data agent exposes no MCP tool. Publish the data agent first.');
    // The agent exposes one tool; read the question argument name from its schema instead of hard-coding it.
    const argument = Object.keys(tool.inputSchema?.properties || {})[0] || 'question';
    const result = await session.request('tools/call', { name: tool.name, arguments: { [argument]: question } });
    const content = result?.content || [];
    const answer = content
      .filter((block) => block?.type === 'text')
      .map((block) => block.text)
      .join('\n')
      .trim();
    if (result?.isError) throw new McpError(answer || 'The data agent returned an error.');
    // Charts the agent drew (its code interpreter tool, in preview), when the server returns them as image content.
    const images = content.filter((block) => block?.type === 'image' && typeof block.data === 'string').map((block) => ({ mimeType: String(block.mimeType || ''), data: block.data }));
    return images.length ? { answer, tool: tool.name, images } : { answer, tool: tool.name };
  } finally {
    await session.close().catch(() => {});
  }
}
