// Writes src/crm/report-assets/Platform-app-Insights.measures.dax and refreshes the generated sections of
// report-creation-prompt.md from the model and the starter report. Run it after changing src/crm/model.js,
// src/crm/schema.js or src/crm/report.js: node scripts/report-assets.js
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { MEASURES_FILE, PROMPT_FILE, daxProblems, measuresDax, promptProblems, refreshPrompt } from '../src/crm/assets.js';

const read = (file) => readFileSync(file, 'utf8').replace(/\r\n/g, '\n');

function write(url, text) {
  const file = fileURLToPath(url);
  const before = existsSync(file) ? read(file) : null;
  const shown = path.relative(process.cwd(), file);
  if (before === text) return console.log(`unchanged  ${shown}`);
  writeFileSync(file, text);
  console.log(`${before === null ? 'created' : 'updated'}    ${shown}`);
}

const daxIssues = daxProblems();
if (daxIssues.length) {
  console.error(`Nothing written: the measures in src/crm/model.js break the naming conventions.\n- ${daxIssues.join('\n- ')}`);
  process.exit(1);
}
write(MEASURES_FILE, measuresDax());

const prompt = refreshPrompt(read(PROMPT_FILE));
write(PROMPT_FILE, prompt);
const promptIssues = promptProblems(prompt);
if (promptIssues.length) {
  console.error(`Fix the hand-written part of the prompt:\n- ${promptIssues.join('\n- ')}`);
  process.exitCode = 1;
}
