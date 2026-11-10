import type { Metadata } from "next";
import Link from "next/link";
import { requestCode, setPrefs } from "./actions";
import { getPrefs } from "@/lib/prefs";
import { Logo } from "@/components/Logo";
import type { Lang } from "@/lib/i18n";

export const metadata: Metadata = { title: "Technosat · IT Service Portal" };

/** Front page copy. Company facts come from technosat.sa. English and Arabic only. */
const copy = {
  en: {
    nav: { home: "Home", solutions: "Solutions", services: "Services", about: "About us", contact: "Contact us", signIn: "Sign in", contactUs: "Contact Us" },
    pill: "Technosat IT Service Portal · Saudi Arabia",
    headline: "IT tickets, approvals and dashboards in one place",
    lead: "Technosat's service desk for clients and internal teams. Log requests in English or Arabic, route them for approval, and follow every ticket on a live dashboard.",
    checks: [
      "Numbered tickets routed to the right team",
      "Requests in English, Arabic, or both",
      "Approvals and onboarding checklists built in",
      "Live dashboards with due dates and overdue flags",
    ],
    cardTitle: "Sign in to the portal",
    cardText: "Enter your work email and we will send you a one-time code.",
    cardLabel: "Work email",
    cardButton: "Send code",
    cardNote: "Access is limited to authorized accounts.",
    solutionsTitle: "What the portal does",
    solutions: [
      { t: "Ticket intake", d: "Each request gets a numbered ticket and goes straight to the team that owns it." },
      { t: "English and Arabic", d: "Write a request in either language. Both versions are stored and shown to whoever needs them." },
      { t: "Approvals", d: "Equipment and onboarding requests wait for the manager's decision before any work starts." },
      { t: "Onboarding and offboarding", d: "Standard checklists assign tasks to HR, IT and managers in the right order." },
      { t: "Dashboards and due dates", d: "Counts by status, category and priority, with due dates and overdue flags." },
      { t: "Access and audit", d: "Employees see their own requests. Every key action is recorded for review." },
    ],
    servicesTitle: "Technosat services",
    services: [
      { t: "Data Center Solutions", d: "Smart data center design and build, power, cooling, racks and cabling." },
      { t: "Network Solutions", d: "LAN, WAN, wireless, unified communications, storage and disaster recovery, with security." },
      { t: "Network Operation Center", d: "Network monitoring, command and control rooms, video walls and CCTV." },
      { t: "Security Operation Center", d: "SIEM, threat detection, log analysis, vulnerability scanning and penetration testing." },
      { t: "Resourcing Services", d: "Staffing, managed outsourcing, recruitment and payroll." },
      { t: "Consultation & Professional Services", d: "IT consulting, ITIL implementation, enterprise architecture and network audits." },
      { t: "Software & Application Development", d: "Web and mobile apps, UI/UX design, systems integration and e-services." },
      { t: "Smart Solutions", d: "Building management, smart meeting rooms, access control, IP surveillance and digital signage." },
    ],
    whyTitle: "Why Technosat",
    why: [
      { t: "Team of professionals", d: "Experienced staff in project management, design, project control and strategic planning." },
      { t: "Trusted by prestigious clients", d: "Government and royal departments across the GCC rely on our work." },
      { t: "Track record", d: "A growing business built on projects that were closed successfully." },
    ],
    productsTitle: "In-house products",
    products: ["Meeting+", "Mawid", "Musaned", "One Click", "Mersal", "Private Asset", "Jameaty", "Naqel", "Mahmiyat", "Payment Gateway", "SMS Gateway", "E-Sport", "AQT Power Saver"],
    contactTitle: "Contact us",
    contact: { address: "Address", phone: "Phone", email: "Email", careers: "Careers" },
    addressValue: "P.O. Box 305099, Riyadh 11361, Saudi Arabia",
    footer: "Technosat. All rights reserved.",
  },
  ar: {
    nav: { home: "الرئيسية", solutions: "الحلول", services: "الخدمات", about: "من نحن", contact: "اتصل بنا", signIn: "تسجيل الدخول", contactUs: "تواصل معنا" },
    pill: "بوابة خدمات تقنية المعلومات من تكنوسات · المملكة العربية السعودية",
    headline: "تذاكر تقنية المعلومات والموافقات ولوحات المتابعة في مكان واحد",
    lead: "مكتب خدمة تكنوسات للعملاء والفرق الداخلية. سجّل الطلبات بالإنجليزية أو العربية، ووجّهها للموافقة، وتابع كل تذكرة على لوحة مباشرة.",
    checks: [
      "تذاكر مرقمة تُوجَّه إلى الفريق المختص",
      "طلبات بالإنجليزية أو العربية أو بالاثنتين",
      "موافقات وقوائم تهيئة الموظفين مدمجة",
      "لوحات مباشرة مع مواعيد الاستحقاق والتأخير",
    ],
    cardTitle: "تسجيل الدخول إلى البوابة",
    cardText: "أدخل بريدك الوظيفي وسنرسل لك رمزاً لمرة واحدة.",
    cardLabel: "البريد الوظيفي",
    cardButton: "إرسال الرمز",
    cardNote: "الوصول مقتصر على الحسابات المصرح لها.",
    solutionsTitle: "ما تقدمه البوابة",
    solutions: [
      { t: "استقبال التذاكر", d: "يحصل كل طلب على تذكرة مرقمة ويذهب مباشرة إلى الفريق المسؤول عنه." },
      { t: "الإنجليزية والعربية", d: "اكتب الطلب بأي من اللغتين. تُحفظ النسختان وتظهران لمن يحتاجهما." },
      { t: "الموافقات", d: "تنتظر طلبات المعدات والتهيئة قرار المدير قبل بدء أي عمل." },
      { t: "التهيئة وإنهاء الخدمة", d: "قوائم مهام قياسية توزع المهام على الموارد البشرية وتقنية المعلومات والمديرين بالترتيب الصحيح." },
      { t: "اللوحات ومواعيد الاستحقاق", d: "أعداد حسب الحالة والفئة والأولوية، مع مواعيد الاستحقاق وتنبيهات التأخير." },
      { t: "الصلاحيات والتدقيق", d: "يرى الموظف طلباته فقط، وتُسجَّل كل الإجراءات المهمة للمراجعة." },
    ],
    servicesTitle: "خدمات تكنوسات",
    services: [
      { t: "حلول مراكز البيانات", d: "تصميم مراكز البيانات الذكية وبنائها، والطاقة والتبريد والخزائن والكابلات." },
      { t: "حلول الشبكات", d: "الشبكات المحلية والواسعة واللاسلكية والاتصالات الموحدة والتخزين والتعافي من الكوارث، مع الأمن." },
      { t: "مركز العمليات الشبكية", d: "مراقبة الشبكات وغرف القيادة والتحكم وشاشات العرض والمراقبة المرئية." },
      { t: "مركز عمليات الأمن", d: "أنظمة SIEM واكتشاف التهديدات وتحليل السجلات وفحص الثغرات واختبار الاختراق." },
      { t: "خدمات التوظيف", d: "التوظيف والاستعانة المُدارة بمصادر خارجية والاستقطاب والرواتب." },
      { t: "الاستشارات والخدمات المهنية", d: "استشارات تقنية المعلومات وتطبيق ITIL وهندسة المؤسسات وتدقيق الشبكات." },
      { t: "تطوير البرمجيات والتطبيقات", d: "تطبيقات الويب والجوال وتصميم تجربة المستخدم والتكامل بين الأنظمة والخدمات الإلكترونية." },
      { t: "الحلول الذكية", d: "إدارة المباني وغرف الاجتماعات الذكية والتحكم في الدخول والمراقبة بكاميرات IP واللافتات الرقمية." },
    ],
    whyTitle: "لماذا تكنوسات",
    why: [
      { t: "فريق من المحترفين", d: "كوادر ذات خبرة في إدارة المشاريع والتصميم ومراقبة المشاريع والتخطيط الاستراتيجي." },
      { t: "ثقة عملاء مرموقين", d: "تعتمد عليها جهات حكومية وملكية في دول الخليج." },
      { t: "سجل إنجازات", d: "أعمال متنامية تقوم على مشاريع أُنجزت بنجاح." },
    ],
    productsTitle: "منتجاتنا الداخلية",
    products: ["Meeting+", "Mawid", "Musaned", "One Click", "Mersal", "Private Asset", "Jameaty", "Naqel", "Mahmiyat", "Payment Gateway", "SMS Gateway", "E-Sport", "AQT Power Saver"],
    contactTitle: "اتصل بنا",
    contact: { address: "العنوان", phone: "الهاتف", email: "البريد الإلكتروني", careers: "الوظائف" },
    addressValue: "ص.ب 305099، الرياض 11361، المملكة العربية السعودية",
    footer: "تكنوسات. جميع الحقوق محفوظة.",
  },
} as const;

export default async function LandingPage() {
  const { lang } = await getPrefs();
  const c = copy[lang as Lang];
  const dir = lang === "ar" ? "rtl" : "ltr";
  return (
    <div className="landing" dir={dir}>
      <header className="landing-nav">
        <Logo lang={lang} height={36} />
        <nav>
          <a href="#top">{c.nav.home}</a>
          <a href="#solutions">{c.nav.solutions}</a>
          <a href="#services">{c.nav.services}</a>
          <a href="#about">{c.nav.about}</a>
          <a href="#contact">{c.nav.contact}</a>
        </nav>
        <div className="nav-right">
          <Link className="btn" href="/login">{c.nav.signIn}</Link>
          <a className="btn btn-primary" href="#contact">{c.nav.contactUs}</a>
          <form action={setPrefs} className="landing-prefs">
            <select name="lang" defaultValue={lang} aria-label="Language">
              <option value="en">English</option>
              <option value="ar">العربية</option>
            </select>
            <input type="hidden" name="display" value={lang} />
            <button type="submit">{lang === "ar" ? "حفظ" : "Save"}</button>
          </form>
        </div>
      </header>

      <section id="top" className="lp-hero">
        <div className="lp-wrap">
          <div>
            <span className="lp-pill">{c.pill}</span>
            <h1>{c.headline}</h1>
            <p className="lead">{c.lead}</p>
            <ul className="lp-checks">
              {c.checks.map((item) => (
                <li key={item}><span className="lp-check" aria-hidden="true">✓</span><span>{item}</span></li>
              ))}
            </ul>
          </div>
          <div className="lp-card">
            <h2>{c.cardTitle}</h2>
            <p className="muted" style={{ marginTop: 0 }}>{c.cardText}</p>
            <form action={requestCode}>
              <input type="hidden" name="next" value="/dashboard" />
              <label htmlFor="work-email">{c.cardLabel}</label>
              <input id="work-email" name="email" type="email" autoComplete="email" required dir="ltr" placeholder="you@technosat.sa" />
              <p style={{ marginTop: 14 }}><button className="btn btn-primary" type="submit" style={{ width: "100%" }}>{c.cardButton}</button></p>
            </form>
            <p className="help" style={{ textAlign: "center" }}>{c.cardNote}</p>
          </div>
        </div>
      </section>

      <section id="solutions" className="section">
        <h2>{c.solutionsTitle}</h2>
        <div className="service-grid">
          {c.solutions.map((s, i) => (
            <article className="service-card" key={s.t}>
              <span className="service-index">{String(i + 1).padStart(2, "0")}</span>
              <h3>{s.t}</h3>
              <p>{s.d}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="services" className="section">
        <h2>{c.servicesTitle}</h2>
        <div className="service-grid">
          {c.services.map((s, i) => (
            <article className="service-card" key={s.t}>
              <span className="service-index">{String(i + 1).padStart(2, "0")}</span>
              <h3>{s.t}</h3>
              <p>{s.d}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="about" className="section steps-band">
        <h2>{c.whyTitle}</h2>
        <ol className="steps">
          {c.why.map((s, i) => (
            <li key={s.t}><span className="step-num">{i + 1}</span><h3>{s.t}</h3><p>{s.d}</p></li>
          ))}
        </ol>
      </section>

      <section className="section">
        <h2>{c.productsTitle}</h2>
        <div className="chips">
          {c.products.map((p) => (<span className="chip" key={p}>{p}</span>))}
        </div>
      </section>

      <section id="contact" className="section">
        <h2>{c.contactTitle}</h2>
        <div className="contact-grid">
          <div className="card"><div className="crumbs">{c.contact.address}</div><p dir="ltr" style={{ margin: 0 }}>{c.addressValue}</p></div>
          <div className="card"><div className="crumbs">{c.contact.phone}</div><p dir="ltr" style={{ margin: 0 }}>+966 11 2455534</p></div>
          <div className="card"><div className="crumbs">{c.contact.email}</div><p dir="ltr" style={{ margin: 0 }}>contactus@technosat.sa</p></div>
          <div className="card"><div className="crumbs">{c.contact.careers}</div><p dir="ltr" style={{ margin: 0 }}>hr@technosat.sa</p></div>
        </div>
      </section>

      <footer className="landing-foot">
        <span className="logo-panel"><Logo lang={lang} height={28} /></span>
        <span>{c.footer}</span>
        <a href="https://technosat.sa/" style={{ marginInlineStart: "auto", color: "#9fb3cc" }}>technosat.sa</a>
      </footer>
    </div>
  );
}
