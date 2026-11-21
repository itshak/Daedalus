import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const resources = ['wood', 'wine', 'marble', 'glass', 'sulfur'];
test('all five Ikariam resource image assets are bundled as valid WebP files', () => {
  for (const name of resources) {
    const data = readFileSync(new URL(`../public/ikariam-resources/${name}.webp`, import.meta.url));
    assert.ok(data.length > 200 && data.length < 1000, `${name}: expect native small resource art, not large island drawings`);
    assert.equal(data.subarray(0, 4).toString(), 'RIFF', name);
    assert.equal(data.subarray(8, 12).toString(), 'WEBP', name);
  }
});
test('warehouse resource cards and table headings render icons, not generic glyphs', () => {
  const source = readFileSync(new URL('../components/control-center.tsx', import.meta.url), 'utf8');
  assert.match(source, /ikariam-resources\/\$\{resource\}\.webp/);
  assert.match(source, /resource-gem resource-/);
  assert.match(source, /resource-heading/);
  assert.match(source, /<ResourceIcon resource=\{k\}/);
  assert.doesNotMatch(source, /k==="wood"\?"◆"/);
});

test('resource sprites retain native dimensions and transparent card backgrounds', () => {
  const source = readFileSync(new URL('../components/control-center.tsx', import.meta.url), 'utf8');
  const styles = readFileSync(new URL('../app/globals.css', import.meta.url), 'utf8');
  assert.match(source, /wood: \{width: 25, height: 20\}/);
  assert.match(source, /glass: \{width: 23, height: 18\}/);
  assert.match(styles, /\.resource-gem \{[^}]*background:transparent/);
  assert.doesNotMatch(styles, /\.resource-wine \{/);
});
