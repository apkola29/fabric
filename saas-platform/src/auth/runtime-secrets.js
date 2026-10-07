import { randomBytes } from 'node:crypto';
import { existsSync } from 'node:fs';
import path from 'node:path';
import readline from 'node:readline/promises';
import { dataDirOf } from '../config.js';

// Credentials are asked for when the app starts, in the terminal of whoever runs it, and never written to a file in
// the project. In production (and anywhere without a terminal) they come from the environment instead: a managed
// identity, a certificate path, Key Vault, or variables set by the hosting platform.
//
//   platform identity   FABRIC_AUTH_MODE=sp: a certificate (PEM path) or, for development, a client secret
//   SECRETS_KEY         unlocks the customers' stored credentials (SECRETS_PROVIDER=file)
//   ADMIN_KEY           the back office sign-in (the server only)
//   SESSION_SECRET      made up for the run when missing outside production, so sessions end when the server stops

const MIN_SECRETS_KEY = 16;
const MIN_ADMIN_KEY = 24;
const generate = (bytes) => randomBytes(bytes).toString('base64url');

export class PromptCancelled extends Error {
  constructor() {
    super('Cancelled.');
    this.name = 'PromptCancelled';
  }
}

// `purpose`: 'server' also asks for the back-office key and makes a session key; 'cli' and 'setup' don't.
// `input`/`output` stand in for the terminal in tests; `interactive` is true when someone can answer.
export async function askForSecrets(env = process.env, { purpose = 'server', input = process.stdin, output = process.stderr, interactive = Boolean(input.isTTY) } = {}) {
  const values = { ...env };
  const mode = String(values.FABRIC_AUTH_MODE || 'mock').trim().toLowerCase();
  const production = String(values.APP_ENV || '').trim().toLowerCase() === 'production';
  const say = (line = '') => output.write(`${line}\n`);
  if (mode === 'mock') return values;

  const prompt = createPrompter({ input, output, interactive });
  try {
    // The platform identity's credential.
    const hasCredential = ['AZURE_CLIENT_SECRET', 'AZURE_CLIENT_CERTIFICATE_PATH', 'MANAGED_IDENTITY_CLIENT_ID', 'AZURE_FEDERATED_TOKEN_FILE'].some((name) => values[name]);
    if (mode === 'sp' && !hasCredential && interactive) {
      say(`The platform identity (app ${values.AZURE_CLIENT_ID || 'not set'}) needs its credential. It's used for this run only and never saved.`);
      const choice = await prompt.choose('How does it sign in?', ['A certificate: a PEM file with its private key (recommended)', 'A client secret (development only)']);
      if (choice === 0) values.AZURE_CLIENT_CERTIFICATE_PATH = await prompt.ask('Path to the PEM file', { required: true });
      else values.AZURE_CLIENT_SECRET = await prompt.hidden('Client secret', { required: true });
    }

    // The key to the customers' stored credentials: asked for when the store exists, chosen when it doesn't.
    const provider = String(values.SECRETS_PROVIDER || (production ? 'keyvault' : 'file')).trim().toLowerCase();
    if (provider === 'file' && !values.SECRETS_KEY && interactive) {
      const stored = existsSync(path.join(dataDirOf(values), 'secrets.json'));
      if (stored) {
        values.SECRETS_KEY = await prompt.hidden('Key for the stored customer credentials (SECRETS_KEY)', { required: true });
      } else {
        say('Customer service account credentials are stored encrypted with a key you keep. You will be asked for it at every start.');
        const chosen = await prompt.hidden(`Choose a key (${MIN_SECRETS_KEY}+ characters; press Enter to make one)`, { minLength: MIN_SECRETS_KEY, allowEmpty: true });
        if (chosen) {
          if ((await prompt.hidden('Type it again')) !== chosen) throw new Error("The keys don't match. Nothing was changed.");
          values.SECRETS_KEY = chosen;
        } else {
          values.SECRETS_KEY = generate(32);
          say(`Your key (shown once; save it in a password manager): ${values.SECRETS_KEY}`);
        }
      }
    }

    if (purpose === 'server') {
      if (!values.ADMIN_KEY && interactive) {
        const key = await prompt.hidden(`Back-office key (${MIN_ADMIN_KEY}+ characters; press Enter to make one for this run)`, { minLength: MIN_ADMIN_KEY, allowEmpty: true });
        values.ADMIN_KEY = key || generate(32);
        if (!key) say(`Back-office key for this run (shown once): ${values.ADMIN_KEY}`);
      }
      if (!values.SESSION_SECRET && !production) values.SESSION_SECRET = generate(36);
    }
  } finally {
    prompt.close();
  }
  return values;
}

// Questions on a terminal (hidden input for secrets), or one line per answer from a stream (tests, pipes).
export function createPrompter({ input, output, interactive }) {
  const lines = interactive && !input.isTTY ? lineReader(input) : null;
  const write = (text) => output.write(text);

  async function readLine(question) {
    if (!interactive) throw new Error(`${question}: no terminal to ask in. Set it in the environment instead.`);
    if (lines) {
      write(`${question}: `);
      const answer = await lines.next();
      write('\n');
      if (answer === null) throw new PromptCancelled();
      return answer.trim();
    }
    const rl = readline.createInterface({ input, output, terminal: true });
    try {
      return (await rl.question(`${question}: `)).trim();
    } finally {
      rl.close();
    }
  }

  // Raw mode, so nothing typed is echoed; Backspace works and Ctrl+C cancels.
  function readHiddenLine(question) {
    if (!interactive) return Promise.reject(new Error(`${question}: no terminal to ask in. Set it in the environment instead.`));
    if (lines) return readLine(question);
    return new Promise((resolve, reject) => {
      write(`${question}: `);
      const wasRaw = Boolean(input.isRaw);
      input.setRawMode(true);
      input.setEncoding('utf8');
      input.resume();
      let value = '';
      const finish = (error) => {
        input.removeListener('data', onData);
        input.setRawMode(wasRaw);
        input.pause();
        write('\n');
        if (error) reject(error);
        else resolve(value);
      };
      function onData(chunk) {
        for (const ch of chunk) {
          if (ch === '\r' || ch === '\n') return finish();
          if (ch === '\u0003') return finish(new PromptCancelled());
          if (ch === '\u007f' || ch === '\b') value = value.slice(0, -1);
          else if (ch >= ' ') value += ch;
        }
      }
      input.on('data', onData);
    });
  }

  async function until(read, question, { required = false, minLength = 0, allowEmpty = false } = {}) {
    for (let attempt = 0; attempt < 5; attempt++) {
      const answer = await read(question);
      if (!answer && allowEmpty) return '';
      if (!answer && (required || minLength)) {
        write('An answer is needed.\n');
        continue;
      }
      if (answer && answer.length < minLength) {
        write(`It must be at least ${minLength} characters.\n`);
        continue;
      }
      return answer;
    }
    throw new Error(`No usable answer to "${question}".`);
  }

  return {
    ask: (question, options) => until(readLine, question, options),
    hidden: (question, options) => until(readHiddenLine, question, options),
    async choose(question, choices) {
      write(`${question}\n${choices.map((c, i) => `  ${i + 1}. ${c}`).join('\n')}\n`);
      for (let attempt = 0; attempt < 5; attempt++) {
        const index = Number(await readLine('Choose')) - 1;
        if (Number.isInteger(index) && index >= 0 && index < choices.length) return index;
        write(`Type a number from 1 to ${choices.length}.\n`);
      }
      throw new Error('No choice was made.');
    },
    close() {
      lines?.close();
    },
  };
}

// Answers from a non-terminal stream, one line each.
function lineReader(input) {
  let buffer = '';
  let ended = false;
  const waiting = [];
  const flush = () => {
    while (waiting.length) {
      const at = buffer.indexOf('\n');
      if (at >= 0) {
        const line = buffer.slice(0, at).replace(/\r$/, '');
        buffer = buffer.slice(at + 1);
        waiting.shift()(line);
      } else if (ended) {
        const rest = buffer.replace(/\r$/, '');
        buffer = '';
        waiting.shift()(rest || null);
      } else break;
    }
  };
  const onData = (chunk) => {
    buffer += chunk.toString('utf8');
    flush();
  };
  const onEnd = () => {
    ended = true;
    flush();
  };
  input.on('data', onData);
  input.on('end', onEnd);
  return {
    next: () =>
      new Promise((resolve) => {
        waiting.push(resolve);
        flush();
      }),
    close() {
      input.removeListener('data', onData);
      input.removeListener('end', onEnd);
      input.pause?.();
    },
  };
}
