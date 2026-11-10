/**
 * Technosat brand tokens. Logos come from the official files in public/brand/.
 * Colours are the Technosat palette supplied by the user.
 */
export const BRAND = {
  name: "Technosat",
  productName: { en: "IT Service Portal", ar: "بوابة خدمات تقنية المعلومات" },
  logo: { en: "/brand/technosat-logo-en.png", ar: "/brand/technosat-logo-ar.png" },
  primary: "#1b6cb0",
  primaryDark: "#14507f",
  accent: "#6fb0e6", // dark-mode tint of the primary, for highlights only
  sidebar: "#13324f",
  surface: "#f5f7fb",
  text: "#1d2433",
  muted: "#6b6f76",
} as const;
