"use client";
import { useRouter } from "next/navigation";
import { useLanguage } from "../../lib/i18n/LanguageContext";
import { LanguageSwitcher } from "../shared/LanguageSwitcher";

const SIDEBAR_ITEMS = [
  { href: "/admin/users",         labelKey: "adminLayout.menuUsers",         icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0" },
  { href: "/admin/machines",      labelKey: "adminLayout.menuMachines",      icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
  { href: "/mc/timecards",        labelKey: "adminLayout.menuTimecards",     icon: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" },
  { href: "/admin/settings",      labelKey: "adminLayout.menuSettings",      icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" },
  { href: "/admin/language",      labelKey: "adminLayout.menuLanguage",      icon: "M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 0 1 6.412 9m6.088 9h7M11 21l5-10 5 10M12.5 5l-4 4L6.412 7" },
  { href: "/admin/calendar",      labelKey: "adminLayout.menuCalendar",      icon: "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2z" },
  { href: "/admin/raw",           labelKey: "adminLayout.menuRaw",           icon: "M4 6h16M4 10h16M4 14h16M4 18h16" },
  { href: "/admin/system-logs",   labelKey: "adminLayout.menuSystemLogs",    icon: "M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 0 2-2h2a2 2 0 0 0 2 2" },
  { href: "/admin/clamp-master",  labelKey: "adminLayout.menuClampMaster",   icon: "M4 6h16M4 12h16M4 18h7" },
  { href: "/admin/nc-tool-master",labelKey: "adminLayout.menuNcToolMaster",  icon: "M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" },
  { href: "/admin/pdf-editor",    labelKey: "adminLayout.menuPdfEditor",     icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z" },
  { href: "/admin/special-sheets",labelKey: "adminLayout.menuSpecialSheets", icon: "M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 0 2-2h2a2 2 0 0 0 2 2M12 12h.01M12 16h.01" },
  { href: "/admin/upload-agent",  labelKey: "adminLayout.menuUploadAgent",   icon: "M8 17l4 4 4-4M12 12v9M20.88 18.09A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.29" },
  { href: "/admin/file-browser",  labelKey: "adminLayout.menuFileBrowser",   icon: "M3 7v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-6l-2-2H5a2 2 0 0 0-2 2z" },
];

const BOTTOM_ITEMS = ["/admin/pdf-editor", "/admin/special-sheets", "/admin/upload-agent", "/admin/file-browser", "/admin/language"];

interface AdminLayoutProps {
  pathname: string;
  children: React.ReactNode;
}

export function AdminLayout({ pathname, children }: AdminLayoutProps) {
  const router = useRouter();
  const { t } = useLanguage();
  return (
    <div className="h-screen bg-slate-50 flex flex-col overflow-hidden">
      <header className="bg-white border-b border-slate-200 px-5 py-2.5 flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-sky-600 flex items-center justify-center">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
              <rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/>
            </svg>
          </div>
          <span className="text-sm font-bold text-slate-800 tracking-wide">{t("adminLayout.panelTitle", "MachCore 管理パネル")}</span>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <LanguageSwitcher compact hidden />
          <button onClick={() => router.push(sessionStorage.getItem("admin_origin") === "nc" ? "/nc" : "/mc")}
            className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded transition-colors">{t("common.backToDashboard", "← ダッシュボード")}</button>
          <button onClick={() => { sessionStorage.removeItem("admin_token"); router.push("/admin/login"); }}
            className="text-xs bg-red-50 hover:bg-red-100 text-red-600 px-3 py-1.5 rounded transition-colors">{t("common.logout", "ログアウト")}</button>
        </div>
      </header>
      <div className="flex flex-1 min-h-0 overflow-hidden">
        <aside className="w-52 shrink-0 bg-white border-r border-slate-200 flex flex-col py-4 gap-0.5 overflow-y-auto">
          <div className="px-4 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">{t("common.menu", "メニュー")}</div>
          {SIDEBAR_ITEMS.filter(i => !BOTTOM_ITEMS.includes(i.href)).map(item => (
            <a key={item.href} href={item.href}
              className={"mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors " +
                (pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900")}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>
              {t(item.labelKey)}
            </a>
          ))}
          <div className="mx-3 my-1 border-t border-slate-200" />
          {BOTTOM_ITEMS.map(href => {
            const item = SIDEBAR_ITEMS.find(i => i.href === href)!;
            return (
              <a key={href} href={href}
                className={"mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors " +
                  (pathname === href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900")}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>
                {t(item.labelKey)}
              </a>
            );
          })}
        </aside>
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
