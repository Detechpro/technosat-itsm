import { cookies } from "next/headers";
import { DISPLAY_COOKIE, LANG_COOKIE, isDisplay, isLang, type Display, type Lang } from "@/lib/i18n";

/** The signed-in or anonymous visitor's language and display choice, read from cookies. */
export async function getPrefs(): Promise<{ lang: Lang; display: Display }> {
  const store = await cookies();
  const l = store.get(LANG_COOKIE)?.value;
  const d = store.get(DISPLAY_COOKIE)?.value;
  return { lang: isLang(l) ? l : "en", display: isDisplay(d) ? d : "both" };
}
