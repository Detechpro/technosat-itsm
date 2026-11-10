import type { Display } from "@/lib/i18n";

/**
 * Shows a bilingual field. "both" displays the primary language with the other underneath.
 * A missing translation is shown as a dash, never as an empty line.
 */
export function BilingualText({ en, ar, display, primary, as: Tag = "span", className }: {
  en?: string; ar?: string; display: Display; primary: "en" | "ar";
  as?: "span" | "div" | "h1" | "h2"; className?: string;
}) {
  const first = primary === "ar" ? ar : en;
  const second = primary === "ar" ? en : ar;
  const pick = display === "both" ? first : display === "ar" ? ar : en;
  const other = display === "both" ? second : undefined;
  return (
    <Tag className={className}>
      <span lang={pick === ar && pick ? "ar" : "en"} dir={pick === ar && pick ? "rtl" : "ltr"}>{pick || "—"}</span>
      {display === "both" && other && (
        <span className="secondary-title" lang={other === ar ? "ar" : "en"} dir={other === ar ? "rtl" : "ltr"}>{other}</span>
      )}
    </Tag>
  );
}
