// No dependencies: Vercel executes this before installing packages.
// Print DEPLOY only for a genuine version increment on main. Any missing
// history, invalid metadata, exception or other branch fails closed.
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

function version(value) {
  if (typeof value !== 'string') throw Error('Invalid version');
  const m = /^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-(alpha|beta|rc)\.([1-9][0-9]*))?$/.exec(value);
  if (!m) throw Error('Invalid version');
  const parts = [Number(m[1]), Number(m[2]), Number(m[3]), m[4] ? ['alpha','beta','rc'].indexOf(m[4]) : 3, Number(m[5] || 0)];
  if (!parts.every(Number.isSafeInteger)) throw Error('Invalid version');
  return parts;
}
export function isVersionIncrease(previous, current) {
  const a = version(previous), b = version(current);
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return b[i] > a[i];
  return false;
}
export function shouldDeploy({ env, ref, previous, current, lock }) {
  try {
    return env === 'production' && ref === 'main' && current === lock && isVersionIncrease(previous, current);
  } catch { return false; }
}
function decision() {
  try {
    const env = process.env.VERCEL_ENV, ref = process.env.VERCEL_GIT_COMMIT_REF;
    if (env !== 'production' || ref !== 'main') return false;
    const previous = JSON.parse(execFileSync('git', ['show','HEAD^:apps/web/package.json'], { encoding: 'utf8', stdio: ['ignore','pipe','ignore'], timeout: 5000 })).version;
    const current = JSON.parse(readFileSync('package.json','utf8')).version;
    const lock = JSON.parse(readFileSync('package-lock.json','utf8'));
    if (lock.version !== lock.packages?.['']?.version) return false;
    return shouldDeploy({ env, ref, previous, current, lock: lock.version });
  } catch { return false; }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) console.log(decision() ? 'DEPLOY' : 'SKIP');
