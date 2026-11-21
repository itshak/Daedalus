import { readFileSync } from "node:fs";
import { test } from "node:test";
import assert from "node:assert/strict";
import { LOCALE_COOKIE, RU, parseLocale, translate, formatNumber, formatDate } from "../lib/i18n.ts";

const read = path => readFileSync(new URL("../" + path, import.meta.url), "utf8");

test("Russian language codes and English fallback are explicit", () => {
  assert.equal(parseLocale("ru-RU"), "ru");
  assert.equal(parseLocale("ru"), "ru");
  assert.equal(parseLocale("EN-us"), "en");
  assert.equal(parseLocale(null), "en");
  assert.equal(parseLocale("de-DE"), "en");
  assert.equal(LOCALE_COOKIE, "daedalus-locale");
});

test("Russian glossary translates major screens and game terminology", () => {
  for (const [source, expected] of Object.entries({
    "Overview": "Обзор",
    "Warehouses": "Склады",
    "Automations": "Автоматизация",
    "Military": "Армия",
    "Settings": "Настройки",
    "Wood": "Древесина",
    "Glass": "Хрусталь",
    "Construction List": "Строительство",
    "Sign in securely": "Войти",
  })) {
    assert.equal(translate(source, "ru"), expected);
    assert.equal(translate(source, "en"), source);
  }
  assert.equal(translate("Unknown backend status", "ru"), "Unknown backend status");
  assert.ok(Object.keys(RU).length > 300, "all screens must be covered by the glossary");
});

test("Russian count placeholders and number/date formatting", () => {
  assert.equal(translate("{selected} of {total} accounts", "ru", { selected: 3, total: 5 }), "Аккаунтов: 3 из 5");
  assert.equal(translate("{cities} city snapshots · {accounts} accounts reported", "ru", { cities: 12, accounts: 2 }), "Снимков городов: 12 · аккаунтов с данными: 2");
  assert.equal(formatNumber(12345, "en"), "12,345");
  assert.equal(formatNumber(12345, "ru").replace(/[\u00A0\u202F]/g, " "), "12 345");
  assert.equal(formatDate("2026-11-21T10:30:00Z", "ru").includes("2026"), true);
  assert.equal(formatNumber(null, "ru"), "—");
});

test("login, settings, global toolbar and HTML support persisted Russian", () => {
  const login = read("app/login/page.tsx");
  const shell = read("components/control-center.tsx");
  const layout = read("app/layout.tsx");
  const provider = read("components/language-provider.tsx");
  assert.match(login, /LanguageSelector compact/);
  assert.match(shell, /Language preference/);
  assert.match(shell, /LanguageSelector compact/);
  assert.match(layout, /lang=\{locale\}/);
  assert.match(provider, /navigator\.languages/);
  assert.match(provider, /document\.cookie/);
  assert.match(provider, /document\.documentElement\.lang = locale/);
  assert.doesNotMatch(shell, /tr\("accounts"\)/, "API identifiers must not be localized");
  assert.match(shell, /controller<\{accounts:Account\[\]\}>\("accounts"\)/);
});

test("every static translated UI key used by dashboard or sign-in exists in glossary", () => {
  const sources = [read("components/control-center.tsx"), read("app/login/page.tsx")];
  for (const source of sources) {
    const used = [...source.matchAll(/\b(?:tr|t)\("([^"]+)"(?:\)|,)/g)].map(match => match[1]);
    const missing = [...new Set(used.filter(key => !Object.hasOwn(RU, key)))];
    assert.deepEqual(missing, [], "missing translations: " + missing.join(", "));
  }
});
