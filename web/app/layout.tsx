import type { Metadata, Viewport } from "next";
import "./globals.css";
import { BRAND } from "@/lib/brand";
import { getPrefs } from "@/lib/prefs";

export const metadata: Metadata = {
  title: { default: BRAND.productName.en, template: `%s · ${BRAND.productName.en}` },
  description: "Requests, approvals, onboarding and IT assets",
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = { themeColor: BRAND.primary, width: "device-width", initialScale: 1 };

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const { lang } = await getPrefs();
  return (
    <html lang={lang} dir={lang === "ar" ? "rtl" : "ltr"}>
      <body data-lang={lang}>{children}</body>
    </html>
  );
}
