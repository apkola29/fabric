// Writes the diagrams on the static page (site/index.html) as standalone SVG files. Each diagram has its own module;
// edit it, then run: node site/diagrams.mjs
import { writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { allInOne } from './all-in-one.mjs';
import { credentialFlow } from './credential-flow.mjs';
import { whoSeesWhat } from './who-sees-what.mjs';

const OUT = process.argv[2] || path.dirname(fileURLToPath(import.meta.url));
writeFileSync(path.join(OUT, 'who-sees-what.svg'), whoSeesWhat());
writeFileSync(path.join(OUT, 'credential-flow.svg'), credentialFlow());
writeFileSync(path.join(OUT, 'all-in-one.svg'), allInOne());
console.log('wrote who-sees-what.svg, credential-flow.svg and all-in-one.svg');
