"use client";

import { ReactNode, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Sidebar } from "@/components/sidebar";
import { apiGet, apiPut } from "@/lib/api";
import { getToken } from "@/lib/session";

type Props = {
  title: string;
  subtitle: string;
  children: ReactNode;
};

export function ProtectedShell({ title, subtitle, children }: Props) {
  const router = useRouter();
  const [user, setUser] = useState<{
    full_name: string;
    role: string;
    permissions: string[];
    preferred_language: string;
    preferred_currency: string;
  } | null>(null);
  const [language, setLanguage] = useState("es");
  const [currency, setCurrency] = useState("USD");
  const [languageOptions, setLanguageOptions] = useState<string[]>(["es", "en"]);
  const [currencyOptions, setCurrencyOptions] = useState<string[]>(["USD", "EUR", "VES"]);
  const [enabledModules, setEnabledModules] = useState<string[]>([
    "dashboard",
    "articles",
    "inventory",
    "sales",
    "purchases",
    "reports",
    "settings",
  ]);
  const [uiThemeMode, setUiThemeMode] = useState<"dark" | "light" | "warm">("dark");

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.push("/login");
      return;
    }
    Promise.all([apiGet("/auth/me"), apiGet("/settings/preferences/options"), apiGet("/settings/general")])
      .then(([meData, preferenceOptions, generalSettings]) => {
        setUser(meData);
        try {
          window.sessionStorage.setItem("ridax_user_id", String(meData.id ?? ""));
          window.sessionStorage.setItem("ridax_user_role", String(meData.role ?? ""));
        } catch {
          // keep UI functional when storage is unavailable
        }
        const selectedLanguage = meData.preferred_language ?? preferenceOptions.preferred_language ?? "es";
        const selectedCurrency = meData.preferred_currency ?? preferenceOptions.preferred_currency ?? "USD";
        setLanguage(selectedLanguage);
        setCurrency(selectedCurrency);
        setLanguageOptions(preferenceOptions.languages ?? ["es", "en"]);
        setCurrencyOptions(preferenceOptions.currencies ?? ["USD", "EUR", "VES"]);
        setEnabledModules(
          generalSettings.modules_enabled_default ?? [
            "dashboard",
            "articles",
            "inventory",
            "sales",
            "purchases",
            "reports",
            "settings",
          ],
        );
        setUiThemeMode(generalSettings.ui_theme_mode ?? "dark");
      })
      .catch(() => {
        router.push("/login");
      });
  }, [router]);

  const savePreference = async (nextLanguage: string, nextCurrency: string) => {
    try {
      await apiPut("/settings/preferences/me", {
        preferred_language: nextLanguage,
        preferred_currency: nextCurrency,
      });
    } catch {
      // keep UI responsive; preference save errors should not block navigation
    }
  };

  const onLanguageChange = (nextLanguage: string) => {
    setLanguage(nextLanguage);
    savePreference(nextLanguage, currency).catch(() => null);
  };

  const onCurrencyChange = (nextCurrency: string) => {
    setCurrency(nextCurrency);
    savePreference(language, nextCurrency).catch(() => null);
  };

  useEffect(() => {
    const classes = ["theme-dark", "theme-light", "theme-warm"];
    classes.forEach((name) => document.body.classList.remove(name));
    document.body.classList.add(`theme-${uiThemeMode}`);
    return () => {
      classes.forEach((name) => document.body.classList.remove(name));
    };
  }, [uiThemeMode]);

  if (!user) {
    return <main className="loading-screen">Cargando RIDAX...</main>;
  }

  return (
    <div className={`app-shell theme-${uiThemeMode}`}>
      <Sidebar permissions={user.permissions ?? []} enabledModules={enabledModules} />
      <main className="content-shell">
        <header className="content-header">
          <div>
            <h2>{title}</h2>
            <p>{subtitle}</p>
          </div>
          <div className="header-actions">
            <button type="button" className="header-btn" onClick={() => router.push("/panel")}>Ir al Dashboard</button>
            <button type="button" className="header-btn" onClick={() => window.location.reload()}>Refrescar</button>
            <label className="header-label">
              Idioma
              <select className="header-select" value={language} onChange={(e) => onLanguageChange(e.target.value)}>
                {languageOptions.map((option) => (
                  <option key={option} value={option}>
                    {option.toUpperCase()}
                  </option>
                ))}
              </select>
            </label>
            <label className="header-label">
              Moneda
              <select className="header-select" value={currency} onChange={(e) => onCurrencyChange(e.target.value)}>
                {currencyOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
            <div className="user-pill">
              <span>{user.full_name}</span>
              <strong>{user.role}</strong>
            </div>
          </div>
        </header>
        <section className="content-card">{children}</section>
      </main>
    </div>
  );
}
