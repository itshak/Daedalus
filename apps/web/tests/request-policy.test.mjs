import { test } from 'node:test';
import assert from 'node:assert/strict';
import { allowedRequest, validatedControllerOrigin } from '../lib/request-policy.ts';
const params = (text = '') => new URLSearchParams(text);
test('backend origin is strictly HTTPS and lacks URL credentials/paths', () => {
  assert.equal(validatedControllerOrigin('https://daedalus.tongrix.com'), 'https://daedalus.tongrix.com');
  for (const url of ['http://backend.test', 'https://u:p@backend.test', 'https://backend.test/path', 'https://backend.test/?secret=1', 'javascript:bad', '']) assert.equal(validatedControllerOrigin(url), null);
});
test('read allowlist matches only supported controller routes', () => {
  for (const path of ['health', 'accounts', 'capabilities', 'task-control', 'warehouses/account-1', 'accounts/account-1/cities', 'accounts/account-1/tasks', 'accounts/account-1/cities/123/buildings', 'accounts/account-1/military']) assert.equal(allowedRequest('GET', path.split('/'), params()), true, path);
  for (const path of ['login-vaults', 'native-browser-login', 'auth-assistance/pending', 'engine/connected-accounts', 'accounts/a/browser-login/start', 'accounts/a/cities/../../vaults', 'accounts/a/cities/0/buildings']) assert.equal(allowedRequest('GET', path.split('/'), params()), false, path);
});
test('task preflight and markets validate query shape', () => {
  assert.equal(allowedRequest('GET', 'accounts/a/tasks/preflight'.split('/'), params('task=research')), true);
  assert.equal(allowedRequest('GET', 'accounts/a/tasks/preflight'.split('/'), params()), false);
  assert.equal(allowedRequest('GET', 'accounts/a/cities/12/market-quotes'.split('/'), params('side=buy&resource_type=0')), true);
  assert.equal(allowedRequest('GET', 'accounts/a/cities/12/market-quotes'.split('/'), params('side=escape&resource_type=2')), false);
});
test('mutation allowlist forbids browser authentication and metadata editing', () => {
  assert.equal(allowedRequest('PUT', ['account-config'], params()), false);
  assert.equal(allowedRequest('POST', 'accounts/a/tasks'.split('/'), params()), true);
  assert.equal(allowedRequest('POST', 'accounts/a/tasks/123/stop'.split('/'), params()), true);
  assert.equal(allowedRequest('POST', 'accounts/a/browser-login/start'.split('/'), params()), false);
});

test('recovery routes allow only audited nonsecret controls', () => {
  for (const path of [
    'recovery', 'accounts/a/recovery', 'accounts/a/recovery/jobs',
  ]) assert.equal(allowedRequest('GET', path.split('/'), params()), true, path);
  for (const path of [
    'accounts/a/recovery/pause', 'accounts/a/recovery/unpause',
    'accounts/a/recovery/resume-now', 'accounts/a/recovery/import-saved-token',
    'recovery/policy/bulk',
  ]) assert.equal(allowedRequest('POST', path.split('/'), params()), true, path);
  assert.equal(allowedRequest('PUT', 'accounts/a/recovery/policy'.split('/'), params()), true);
  for (const path of [
    'accounts/a/recovery/lobby-token', 'accounts/a/recovery/secret',
    'accounts/a/recovery/credentials', 'accounts/a/recovery/execute',
    'accounts/a/browser-login/start', 'accounts/a/recovery/../../password',
  ]) {
    assert.equal(allowedRequest('POST', path.split('/'), params()), false, path);
    assert.equal(allowedRequest('PUT', path.split('/'), params()), false, path);
  }
  assert.equal(allowedRequest('PUT', 'accounts/a/recovery/pause'.split('/'), params()), false);
  assert.equal(allowedRequest('GET', 'accounts/a/recovery/secret'.split('/'), params()), false);
});
