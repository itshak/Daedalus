import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import assert from 'node:assert/strict';

const read = (path) => readFileSync(new URL('../' + path, import.meta.url), 'utf8');

test('login shows one official wordmark without repeating the emblem', () => {
  const login = read('app/login/page.tsx');
  assert.equal((login.match(/src="\/brand\/daedalus-/g) ?? []).length, 1);
  assert.match(login, /src="\/brand\/daedalus-horizontal-light\.svg"/);
  assert.doesNotMatch(login, /login-emblem/);
  assert.match(login, /Welcome back/);
});

test('dashboard uses one wordmark; hero and footer remain uncluttered', () => {
  const center = read('components/control-center.tsx');
  assert.equal((center.match(/src="\/brand\/daedalus-/g) ?? []).length, 1);
  assert.match(center, /sidebar-wordmark/);
  assert.doesNotMatch(center, /footer-mark/);
});

test('provisioning retains its single official logo', () => {
  const page = read('app/page.tsx');
  assert.match(page, /setup-logo/);
});
