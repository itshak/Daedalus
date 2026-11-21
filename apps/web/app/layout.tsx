import type { Metadata, Viewport } from "next";
import { cookies, headers } from "next/headers";
import { LanguageProvider } from "@/components/language-provider";
import { LOCALE_COOKIE, parseLocale } from "@/lib/i18n";
import "./globals.css";
export const metadata: Metadata = {
  title: "Daedalus — Control Center",
  description: "Private multi-account Ikariam operations and monitoring",
  robots: { index: false, follow: false },
  manifest: "/manifest.webmanifest",
  applicationName: "Daedalus",
  icons: { icon: [{ url: "/favicon.ico", sizes: "any" }, { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" }], apple: "/icons/apple-touch-icon.png" }
};
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#11161d" };
export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const savedLocale = (await cookies()).get(LOCALE_COOKIE)?.value;
  const browserLocale = (await headers()).get("accept-language")?.split(",")[0];
  const locale = parseLocale(savedLocale ?? browserLocale);
  return <html lang={locale} suppressHydrationWarning><body><LanguageProvider initialLocale={locale}>{children}</LanguageProvider></body></html>;
}
