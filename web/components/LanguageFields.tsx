"use client";

import { useState } from "react";

type Source = "en" | "ar" | "both";

export function LanguageFields({
  defaultLang,
  labels,
  placeholders,
}: {
  defaultLang: "en" | "ar";
  labels: { language: string; english: string; arabic: string; both: string; titleEn: string; titleAr: string; descriptionEn: string; descriptionAr: string };
  placeholders: { titleEn: string; titleAr: string; descEn: string; descAr: string };
}) {
  const [source, setSource] = useState<Source>(defaultLang);
  const showEn = source === "en" || source === "both";
  const showAr = source === "ar" || source === "both";
  return (
    <>
      <label htmlFor="source_language">{labels.language}</label>
      <select id="source_language" name="source_language" value={source} onChange={(e) => setSource(e.target.value as Source)}>
        <option value="en">{labels.english}</option>
        <option value="ar">{labels.arabic}</option>
        <option value="both">{labels.both}</option>
      </select>

      {showEn && (
        <>
          <label htmlFor="title">{labels.titleEn}</label>
          <input id="title" name="title" minLength={5} maxLength={200} placeholder={placeholders.titleEn} required={source === "en"} />
        </>
      )}
      {showAr && (
        <>
          <label htmlFor="title_ar">{labels.titleAr}</label>
          <input id="title_ar" name="title_ar" dir="rtl" lang="ar" maxLength={200} placeholder={placeholders.titleAr} required={source === "ar"} />
        </>
      )}

      {showEn && (
        <>
          <label htmlFor="description">{labels.descriptionEn}</label>
          <textarea id="description" name="description" placeholder={placeholders.descEn} required={source === "en"} />
        </>
      )}
      {showAr && (
        <>
          <label htmlFor="description_ar">{labels.descriptionAr}</label>
          <textarea id="description_ar" name="description_ar" dir="rtl" lang="ar" placeholder={placeholders.descAr} required={source === "ar"} />
        </>
      )}
    </>
  );
}
