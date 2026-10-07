import path from 'node:path';

// Item definitions travel as base64 "parts". These helpers build and read them.

export const encodePayload = (text) => Buffer.from(text, 'utf8').toString('base64');
export const decodePayload = (payload) => Buffer.from(payload, 'base64').toString('utf8');
export const textPart = (partPath, text) => ({ path: partPath, payload: encodePayload(text), payloadType: 'InlineBase64' });
export const jsonPart = (partPath, value) => textPart(partPath, JSON.stringify(value, null, 2));

const TEXT_EXTENSIONS = new Set([
  '.json', '.tmdl', '.pbir', '.pbism', '.py', '.ipynb', '.sql', '.m', '.pq', '.yml', '.yaml',
  '.txt', '.md', '.xml', '.csv', '.dax', '.kql', '.scala', '.r', '.bim',
]);

// Only text parts can have IDs rewritten; binary parts (images in report resources) must pass through untouched.
export function isTextPart(part) {
  if (path.posix.basename(part.path) === '.platform') return true;
  if (TEXT_EXTENSIONS.has(path.posix.extname(part.path).toLowerCase())) return true;
  const bytes = Buffer.from(part.payload || '', 'base64');
  if (bytes.includes(0)) return false;
  return !bytes.toString('utf8').includes('\uFFFD');
}
