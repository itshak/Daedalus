"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { Globe2 } from "lucide-react";
import { LOCALE_COOKIE, parseLocale, translate, type Locale } from "@/lib/i18n";

type LanguageContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (message: string, values?: Record<string, string | number>) => string;
};
const LanguageContext = createContext<LanguageContextValue | null>(null);

function persist(locale: Locale) {
  document.cookie = LOCALE_COOKIE + "=" + locale + "; Path=/; SameSite=Lax; Max-Age=31536000" + (location.protocol === "https:" ? "; Secure" : "");
  document.documentElement.lang = locale;
}

export function LanguageProvider({ children, initialLocale, hasPreference }: { children: ReactNode; initialLocale: Locale; hasPreference: boolean }) {
  const [locale, updateLocale] = useState<Locale>(initialLocale);
  useEffect(() => {
    if (hasPreference) {
      document.documentElement.lang = initialLocale;
      return;
    }
    // Only the browser knows its Accept-Language order. Never override a saved selection.
    const detected = parseLocale(navigator.languages?.[0] ?? navigator.language);
    updateLocale(detected);
    persist(detected);
  }, [hasPreference, initialLocale]);

  const setLocale = useCallback((choice: Locale) => {
    updateLocale(choice);
    persist(choice);
  }, []);
  const t = useCallback((message: string, values?: Record<string, string | number>) => translate(message, locale, values), [locale]);
  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const value = useContext(LanguageContext);
  if (!value) throw new Error("LanguageProvider is missing");
  return value;
}

export function LanguageSelector({ compact = false }: { compact?: boolean }) {
  const { locale, setLocale, t } = useLanguage();
  return <label className={"language-switcher" + (compact ? " language-switcher-compact" : "")}>
    <Globe2 aria-hidden="true" size={16} />
    {!compact && <span>{t("Language")}</span>}
    <select aria-label={t("Language")} value={locale} onChange={event => setLocale(parseLocale(event.target.value))}>
      <option value="en">English</option>
      <option value="ru">Русский</option>
    </select>
  </label>;
}
