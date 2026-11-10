import { BRAND } from "@/lib/brand";
import type { Lang } from "@/lib/i18n";

/** Technosat logo. Arabic UI uses the Arabic logo; English and bilingual views use the English logo. */
export function Logo({ lang = "en", height = 36 }: { lang?: Lang; height?: number }) {
  const src = lang === "ar" ? BRAND.logo.ar : BRAND.logo.en;
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={src} alt={BRAND.name} height={height} style={{ height, width: "auto" }} />;
}
