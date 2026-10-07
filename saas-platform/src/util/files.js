import { readFileSync } from 'node:fs';
import { copyFile, mkdir, rename, unlink, writeFile } from 'node:fs/promises';
import path from 'node:path';

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export function readJsonFile(file, fallback) {
  try {
    return JSON.parse(readFileSync(file, 'utf8'));
  } catch (error) {
    if (error.code === 'ENOENT') return fallback;
    throw new Error(`Could not read ${file}: ${error.message}`);
  }
}

// Write to a temp file, then rename, so a crash never leaves half a file. Some sandboxes and sync tools refuse
// renames; then a copy keeps the data (without the atomic guarantee).
export async function writeFileAtomic(file, text) {
  await mkdir(path.dirname(file), { recursive: true });
  const temp = `${file}.${process.pid}.${Date.now()}.tmp`;
  await writeFile(temp, text, 'utf8');
  for (let attempt = 0; ; attempt++) {
    try {
      await rename(temp, file);
      return;
    } catch (error) {
      if (error.code === 'EBUSY' && attempt < 5) {
        await sleep(50 * (attempt + 1));
        continue;
      }
      if (['EPERM', 'EACCES', 'EXDEV'].includes(error.code)) {
        await copyFile(temp, file);
        await unlink(temp).catch(() => {});
        return;
      }
      throw error;
    }
  }
}

// Serializes writes so they land in order. A failed write doesn't poison the chain: the next save still runs, and
// the caller of the failed save gets the error.
export function createJsonWriter(file) {
  let chain = Promise.resolve();
  return (value) => {
    const text = JSON.stringify(value, null, 2);
    const result = chain.catch(() => {}).then(() => writeFileAtomic(file, text));
    chain = result;
    return result;
  };
}
