import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "IT Service Portal", template: "%s · IT Service Portal" },
  description: "Requests, approvals, onboarding and IT assets",
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = { themeColor: "#1f4fd8", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
