import type { Metadata, Viewport } from "next";
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
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" suppressHydrationWarning><body>{children}</body></html>;
}