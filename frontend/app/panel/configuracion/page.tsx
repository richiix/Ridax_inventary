"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { ProtectedShell } from "@/components/protected-shell";
import { apiGet, apiPost, apiPut } from "@/lib/api";

type RoleItem = { id: number; name: string; permissions: string[] };
type CurrencyResponse = {
  base_currency: string;
  operational_currency: string;
  rates: Array<{ currency_code: string; rate_to_usd: number }>;
};
type ReceiptCompanySettings = {
  company_name: string;
  company_phone: string;
  company_address: string;
  company_rif: string;
};
type UserPreferences = { preferred_language: string; preferred_currency: string };
type ManagedUserPreference = {
  id: number;
  full_name: string;
  role: string;
  preferred_language: string;
  preferred_currency: string;
  telegram_chat_id: string;
};
type GeneralSettings = {
  modules_enabled_default: string[];
  show_discount_in_invoice: boolean;
  sales_rounding_mode: "none" | "nearest_integer";
  default_markup_percent: number;
  sales_commission_pct: number;
  invoice_tax_enabled: boolean;
  invoice_tax_percent: number;
  ui_theme_mode: "dark" | "light";
};

const tabs = ["Moneda", "General", "Facturas y gastos", "Seguridad"] as const;
type TabName = (typeof tabs)[number];

const moduleOptions = [
  { key: "dashboard", label: "Dashboard" },
  { key: "articles", label: "Articulos" },
  { key: "inventory", label: "Inventario" },
  { key: "sales", label: "Ventas" },
  { key: "purchases", label: "Compras" },
  { key: "reports", label: "Informes" },
  { key: "settings", label: "Configuracion" },
];

export default function ConfiguracionPage() {
  const [activeTab, setActiveTab] = useState<TabName>("Moneda");
  const [message, setMessage] = useState("");
  const [currentRole, setCurrentRole] = useState("");

  const [roles, setRoles] = useState<RoleItem[]>([]);
  const [permissionCatalog, setPermissionCatalog] = useState<string[]>([]);
  const [selectedRoleId, setSelectedRoleId] = useState<number | null>(null);
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);

  const [languages, setLanguages] = useState<{ enabled: string[] } | null>(null);
  const [currencies, setCurrencies] = useState<CurrencyResponse | null>(null);
  const [operationalCurrency, setOperationalCurrency] = useState("USD");

  const [userPreferences, setUserPreferences] = useState<UserPreferences>({ preferred_language: "es", preferred_currency: "USD" });
  const [managedUsers, setManagedUsers] = useState<ManagedUserPreference[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [selectedUserLanguage, setSelectedUserLanguage] = useState("es");
  const [selectedUserCurrency, setSelectedUserCurrency] = useState("USD");
  const [selectedUserTelegram, setSelectedUserTelegram] = useState("");

  const [receiptCompany, setReceiptCompany] = useState<ReceiptCompanySettings>({ company_name: "RIDAX", company_phone: "", company_address: "", company_rif: "" });
  const [general, setGeneral] = useState<GeneralSettings>({
    modules_enabled_default: moduleOptions.map((m) => m.key),
    show_discount_in_invoice: true,
    sales_rounding_mode: "none",
    default_markup_percent: 20,
    sales_commission_pct: 7,
    invoice_tax_enabled: false,
    invoice_tax_percent: 16,
    ui_theme_mode: "dark",
  });

  const [newCurrencyCode, setNewCurrencyCode] = useState("");
  const [newCurrencyRate, setNewCurrencyRate] = useState("1");

  const [channel, setChannel] = useState("telegram");
  const [destination, setDestination] = useState("");
  const [text, setText] = useState("RIDAX prueba de integracion");
  const [backupFile, setBackupFile] = useState<File | null>(null);
  const [replaceOnRestore, setReplaceOnRestore] = useState(true);

  const selectedRole = useMemo(() => roles.find((r) => r.id === selectedRoleId) ?? null, [roles, selectedRoleId]);

  const loadAll = async () => {
    const [rolesData, permissionsData, langData, currencyData, receiptData, prefData, usersData, generalData, meData] = await Promise.all([
      apiGet("/settings/roles"),
      apiGet("/settings/permissions/catalog"),
      apiGet("/settings/languages"),
      apiGet("/settings/currencies"),
      apiGet("/settings/receipt-company"),
      apiGet("/settings/preferences/me"),
      apiGet("/settings/users/preferences"),
      apiGet("/settings/general"),
      apiGet("/auth/me"),
    ]);

    setRoles(rolesData);
    setPermissionCatalog(permissionsData.permissions ?? []);
    setLanguages(langData);
    setCurrencies(currencyData);
    setOperationalCurrency(currencyData.operational_currency ?? "USD");
    setReceiptCompany(receiptData);
    setUserPreferences(prefData);
    setManagedUsers(usersData);
    setGeneral(generalData);
    setCurrentRole((meData?.role ?? "").toLowerCase());

    setSelectedRoleId(rolesData[0]?.id ?? null);
    setSelectedPermissions(rolesData[0]?.permissions ?? []);
    setSelectedUserId(usersData[0]?.id ?? null);
    setSelectedUserLanguage(usersData[0]?.preferred_language ?? "es");
    setSelectedUserCurrency(usersData[0]?.preferred_currency ?? "USD");
    setSelectedUserTelegram(usersData[0]?.telegram_chat_id ?? "");
  };

  useEffect(() => {
    loadAll().catch(() => setMessage("No se pudo cargar configuracion"));
  }, []);

  useEffect(() => {
    if (selectedRole) setSelectedPermissions(selectedRole.permissions ?? []);
  }, [selectedRole]);

  useEffect(() => {
    const selected = managedUsers.find((u) => u.id === selectedUserId);
    if (selected) {
      setSelectedUserLanguage(selected.preferred_language);
      setSelectedUserCurrency(selected.preferred_currency);
      setSelectedUserTelegram(selected.telegram_chat_id ?? "");
    }
  }, [selectedUserId, managedUsers]);

  const saveUserPreferences = async (event: FormEvent) => {
    event.preventDefault();
    setMessage("");
    try {
      await apiPut("/settings/preferences/me", userPreferences);
      setMessage("Preferencias del usuario actualizadas.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo guardar preferencias");
    }
  };

  const saveManagedUserPreferences = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedUserId) return;
    setMessage("");
    try {
      await apiPut(`/settings/users/${selectedUserId}/preferences`, {
        preferred_language: selectedUserLanguage,
        preferred_currency: selectedUserCurrency,
        telegram_chat_id: selectedUserTelegram,
      });
      setMessage("Preferencias del usuario actualizadas por admin.");
      setManagedUsers(await apiGet("/settings/users/preferences"));
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo guardar preferencias del usuario");
    }
  };

  const saveRolePermissions = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedRoleId) return;
    setMessage("");
    try {
      await apiPut(`/settings/roles/${selectedRoleId}/permissions`, { permissions: selectedPermissions });
      setRoles(await apiGet("/settings/roles"));
      setMessage("Permisos del rol actualizados.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo guardar permisos del rol");
    }
  };

  const togglePermission = (permission: string) => {
    setSelectedPermissions((prev) => (prev.includes(permission) ? prev.filter((p) => p !== permission) : [...prev, permission]));
  };

  const saveReceiptCompany = async (event: FormEvent) => {
    event.preventDefault();
    setMessage("");
    try {
      await apiPut("/settings/receipt-company", receiptCompany);
      setMessage("Datos de recibo actualizados.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo guardar datos de recibo");
    }
  };

  const saveGeneralSettings = async (event: FormEvent) => {
    event.preventDefault();
    setMessage("");
    try {
      await apiPut("/settings/general", general);
      setMessage("Configuracion general actualizada. Recarga para aplicar modo visual.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo guardar configuracion general");
    }
  };

  const saveOperationalCurrency = async (event: FormEvent) => {
    event.preventDefault();
    if (!operationalCurrency) return;
    setMessage("");
    try {
      await apiPut("/settings/operational-currency", { currency_code: operationalCurrency });
      setCurrencies(await apiGet("/settings/currencies"));
      setMessage("Moneda operativa actualizada.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo actualizar moneda operativa");
    }
  };

  const saveCurrencyRate = async (event: FormEvent) => {
    event.preventDefault();
    if (!newCurrencyCode) return;
    setMessage("");
    try {
      await apiPut("/settings/currencies/rate", {
        currency_code: newCurrencyCode.toUpperCase(),
        rate_to_usd: Number(newCurrencyRate),
      });
      setCurrencies(await apiGet("/settings/currencies"));
      setNewCurrencyCode("");
      setNewCurrencyRate("1");
      setMessage("Moneda/tasa actualizada.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo guardar moneda");
    }
  };

  const refreshVesFromBcv = async () => {
    setMessage("");
    try {
      await apiPost("/settings/currencies/update-ves-bcv", {});
      setCurrencies(await apiGet("/settings/currencies"));
      setMessage("Tasa VES actualizada desde BCV.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo actualizar VES desde BCV");
    }
  };

  const sendTest = async (event: FormEvent) => {
    event.preventDefault();
    setMessage("");
    try {
      await apiPost(`/integrations/send-test?channel=${encodeURIComponent(channel)}&destination=${encodeURIComponent(destination)}&text=${encodeURIComponent(text)}`, {});
      setMessage("Mensaje de prueba enviado.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo enviar el mensaje");
    }
  };

  const exportSecurityBackup = async () => {
    setMessage("");
    try {
      const payload = await apiGet("/settings/security/backup");
      const pretty = JSON.stringify(payload, null, 2);
      const blob = new Blob([pretty], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const stamp = new Date().toISOString().replace(/[:.]/g, "-");
      const link = document.createElement("a");
      link.href = url;
      link.download = `ridax-respaldo-seguridad-${stamp}.json`;
      link.click();
      URL.revokeObjectURL(url);
      setMessage("Respaldo exportado en JSON legible.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo exportar respaldo");
    }
  };

  const restoreSecurityBackup = async (event: FormEvent) => {
    event.preventDefault();
    if (!backupFile) {
      setMessage("Selecciona un archivo de respaldo JSON.");
      return;
    }

    setMessage("");
    try {
      const raw = await backupFile.text();
      const parsed = JSON.parse(raw);
      const response = await apiPost(`/settings/security/restore?replace_data=${replaceOnRestore ? "true" : "false"}`, parsed);
      setMessage(
        `Restauracion completada. Productos: ${response.updated_products}, compras: ${response.added_purchases ?? 0}, ventas: ${response.added_sales}, movimientos: ${response.added_inventory_movements}, historial precios: ${response.added_product_price_history ?? 0}`,
      );
      await loadAll();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo restaurar respaldo");
    }
  };

  return (
    <ProtectedShell title="Configuracion" subtitle="Control global por pestañas">
      <div className="tab-row">
        {tabs.filter((tab) => (tab === "Seguridad" ? currentRole === "admin" : true)).map((tab) => (
          <button key={tab} type="button" className={activeTab === tab ? "tab-btn active" : "tab-btn"} onClick={() => setActiveTab(tab)}>
            {tab}
          </button>
        ))}
      </div>

      {activeTab === "Moneda" ? (
        <>
          <form className="inline-actions" onSubmit={saveOperationalCurrency}>
            <label className="field-label">Moneda operativa
              <select value={operationalCurrency} onChange={(e) => setOperationalCurrency(e.target.value)}>
                {(currencies?.rates ?? []).map((rate) => (
                  <option key={rate.currency_code} value={rate.currency_code}>{rate.currency_code}</option>
                ))}
              </select>
            </label>
            <button type="submit">Guardar moneda operativa</button>
            <button type="button" onClick={refreshVesFromBcv}>Actualizar VES desde BCV</button>
          </form>

          <form className="inline-actions" onSubmit={saveCurrencyRate}>
            <label className="field-label">Nueva moneda
              <input placeholder="Ej. COP" value={newCurrencyCode} onChange={(e) => setNewCurrencyCode(e.target.value)} />
            </label>
            <label className="field-label">Tasa a USD
              <input type="number" step="0.0001" value={newCurrencyRate} onChange={(e) => setNewCurrencyRate(e.target.value)} />
            </label>
            <button type="submit">Guardar moneda/tasa</button>
          </form>

          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Codigo</th><th>Tasa a USD</th><th>Actualizado</th></tr>
              </thead>
              <tbody>
                {(currencies?.rates ?? []).map((rate: any) => (
                  <tr key={rate.currency_code}>
                    <td>{rate.currency_code}</td>
                    <td>{rate.rate_to_usd}</td>
                    <td>{rate.updated_at ? new Date(rate.updated_at).toLocaleString() : "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}

      {activeTab === "General" ? (
        <>
          <form className="article-form" onSubmit={saveGeneralSettings}>
            <section className="article-form-section">
              <h3>Modulos habilitados (default global)</h3>
              <div className="inline-actions">
                {moduleOptions.map((module) => (
                  <label key={module.key} className="field-label">
                    <input
                      type="checkbox"
                      checked={general.modules_enabled_default.includes(module.key)}
                      onChange={() => {
                        setGeneral((prev) => {
                          const exists = prev.modules_enabled_default.includes(module.key);
                          return {
                            ...prev,
                            modules_enabled_default: exists
                              ? prev.modules_enabled_default.filter((m) => m !== module.key)
                              : [...prev.modules_enabled_default, module.key],
                          };
                        });
                      }}
                    />
                    {module.label}
                  </label>
                ))}
              </div>
            </section>

            <section className="article-form-section">
              <h3>Factura</h3>
              <div className="inline-actions">
                <label className="field-label">
                  <input
                    type="checkbox"
                    checked={general.show_discount_in_invoice}
                    onChange={(e) => setGeneral((prev) => ({ ...prev, show_discount_in_invoice: e.target.checked }))}
                  />
                  Mostrar descuento en factura
                </label>

                <label className="field-label">Redondeo en venta
                  <select
                    value={general.sales_rounding_mode}
                    onChange={(e) => setGeneral((prev) => ({ ...prev, sales_rounding_mode: e.target.value as any }))}
                  >
                    <option value="none">Sin redondeo</option>
                    <option value="nearest_integer">Redondeo total al entero mas proximo</option>
                  </select>
                </label>

                <label className="field-label">Modo de visualizacion
                  <select
                    value={general.ui_theme_mode}
                    onChange={(e) => setGeneral((prev) => ({ ...prev, ui_theme_mode: e.target.value as any }))}
                  >
                    <option value="dark">🌙 Modo oscuro (original)</option>
                    <option value="light">☀️ Modo claro</option>
                  </select>
                </label>
              </div>
            </section>

            <div className="inline-actions">
              <button type="submit">Guardar general</button>
            </div>
          </form>

          <h3>Preferencias por usuario (Admin)</h3>
          <form className="inline-actions" onSubmit={saveManagedUserPreferences}>
            <label className="field-label">Usuario
              <select value={selectedUserId ?? ""} onChange={(e) => setSelectedUserId(Number(e.target.value))}>
                {managedUsers.map((user) => (
                  <option key={user.id} value={user.id}>{user.full_name} ({user.role})</option>
                ))}
              </select>
            </label>
            <label className="field-label">Idioma
              <select value={selectedUserLanguage} onChange={(e) => setSelectedUserLanguage(e.target.value)}>
                {(languages?.enabled ?? ["es", "en"]).map((language) => (
                  <option key={language} value={language}>{language.toUpperCase()}</option>
                ))}
              </select>
            </label>
            <label className="field-label">Moneda
              <select value={selectedUserCurrency} onChange={(e) => setSelectedUserCurrency(e.target.value)}>
                {(currencies?.rates ?? []).map((rate) => (
                  <option key={rate.currency_code} value={rate.currency_code}>{rate.currency_code}</option>
                ))}
              </select>
            </label>
            <label className="field-label">Telegram chat_id
              <input value={selectedUserTelegram} onChange={(e) => setSelectedUserTelegram(e.target.value)} placeholder="Ej. 123456789" />
            </label>
            <button type="submit">Guardar usuario</button>
          </form>
          <p className="muted">
            Ayuda Telegram: cada usuario debe abrir el bot RIDAX y enviar <code>/start</code>. Luego obtienes su <code>chat_id</code>
            (desde el webhook o logs del bot) y lo registras aqui para habilitar recuperacion de contrasena por Telegram.
          </p>

          <h3>Permisos por rol</h3>
          <form className="article-form" onSubmit={saveRolePermissions}>
            <div className="inline-actions">
              <label className="field-label">Rol activo
                <select value={selectedRoleId ?? ""} onChange={(e) => setSelectedRoleId(Number(e.target.value))}>
                  {roles.map((role) => (
                    <option key={role.id} value={role.id}>{role.name}</option>
                  ))}
                </select>
              </label>
            </div>
            <div className="article-form-section">
              <h3>Permisos del rol</h3>
              <div className="inline-actions">
                {permissionCatalog.map((permission) => (
                  <label key={permission} className="field-label">
                    <input type="checkbox" checked={selectedPermissions.includes(permission)} onChange={() => togglePermission(permission)} />
                    {permission}
                  </label>
                ))}
              </div>
            </div>
            <div className="inline-actions"><button type="submit">Guardar permisos del rol</button></div>
          </form>
        </>
      ) : null}

      {activeTab === "Facturas y gastos" ? (
        <>
          <form className="article-form" onSubmit={saveGeneralSettings}>
            <section className="article-form-section">
              <h3>Facturacion</h3>
              <div className="inline-actions">
                <label className="field-label">Porcentaje de marcado predeterminado
                  <input
                    type="number"
                    step="0.01"
                    value={general.default_markup_percent}
                    onChange={(e) => setGeneral((prev) => ({ ...prev, default_markup_percent: Number(e.target.value) }))}
                  />
                </label>
                <label className="field-label">Comision de venta (%)
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={general.sales_commission_pct}
                    onChange={(e) => setGeneral((prev) => ({ ...prev, sales_commission_pct: Number(e.target.value) }))}
                  />
                </label>
                <label className="field-label">
                  <input
                    type="checkbox"
                    checked={general.invoice_tax_enabled}
                    onChange={(e) => setGeneral((prev) => ({ ...prev, invoice_tax_enabled: e.target.checked }))}
                  />
                  Cobrar IVA en factura
                </label>
                <label className="field-label">Porcentaje de IVA
                  <input
                    type="number"
                    step="0.01"
                    disabled={!general.invoice_tax_enabled}
                    value={general.invoice_tax_percent}
                    onChange={(e) => setGeneral((prev) => ({ ...prev, invoice_tax_percent: Number(e.target.value) }))}
                  />
                </label>
              </div>
            </section>
            <div className="inline-actions"><button type="submit">Guardar facturas y gastos</button></div>
          </form>

          <h3>Datos de empresa para recibo</h3>
          <form className="inline-actions" onSubmit={saveReceiptCompany}>
            <input placeholder="Empresa" value={receiptCompany.company_name} onChange={(e) => setReceiptCompany((prev) => ({ ...prev, company_name: e.target.value }))} required />
            <input placeholder="Telefono" value={receiptCompany.company_phone} onChange={(e) => setReceiptCompany((prev) => ({ ...prev, company_phone: e.target.value }))} />
            <input placeholder="Direccion" value={receiptCompany.company_address} onChange={(e) => setReceiptCompany((prev) => ({ ...prev, company_address: e.target.value }))} />
            <input placeholder="RIF" value={receiptCompany.company_rif} onChange={(e) => setReceiptCompany((prev) => ({ ...prev, company_rif: e.target.value }))} />
            <button type="submit">Guardar datos recibo</button>
          </form>

          <h3>Preferencias del usuario actual</h3>
          <form className="inline-actions" onSubmit={saveUserPreferences}>
            <label className="field-label">Idioma
              <select value={userPreferences.preferred_language} onChange={(e) => setUserPreferences((prev) => ({ ...prev, preferred_language: e.target.value }))}>
                {(languages?.enabled ?? ["es", "en"]).map((language) => (
                  <option key={language} value={language}>{language.toUpperCase()}</option>
                ))}
              </select>
            </label>
            <label className="field-label">Moneda en curso
              <select value={userPreferences.preferred_currency} onChange={(e) => setUserPreferences((prev) => ({ ...prev, preferred_currency: e.target.value }))}>
                {(currencies?.rates ?? []).map((rate) => (
                  <option key={rate.currency_code} value={rate.currency_code}>{rate.currency_code}</option>
                ))}
              </select>
            </label>
            <button type="submit">Guardar preferencias</button>
          </form>

          <h3>WhatsApp / Telegram</h3>
          <form className="inline-actions" onSubmit={sendTest}>
            <select value={channel} onChange={(e) => setChannel(e.target.value)}>
              <option value="telegram">Telegram</option>
              <option value="whatsapp">WhatsApp</option>
            </select>
            <input placeholder="Destino (chat_id o numero)" value={destination} onChange={(e) => setDestination(e.target.value)} required />
            <input value={text} onChange={(e) => setText(e.target.value)} required />
            <button type="submit">Enviar prueba</button>
          </form>
        </>
      ) : null}

      {activeTab === "Seguridad" && currentRole === "admin" ? (
        <>
          <section className="article-form-section">
            <h3>Respaldo y restauracion de ventas e inventario</h3>
            <p className="muted">
              Usa formato JSON legible (<code>ridax-backup-v2</code>) para exportar y restaurar datos completos.
            </p>
            <div className="inline-actions">
              <button type="button" onClick={exportSecurityBackup}>Exportar respaldo JSON</button>
            </div>
          </section>

          <form className="article-form" onSubmit={restoreSecurityBackup}>
            <section className="article-form-section">
              <h3>Cargar archivo de restauracion</h3>
              <div className="inline-actions">
                <input
                  type="file"
                  accept="application/json,.json"
                  onChange={(e) => setBackupFile(e.target.files?.[0] ?? null)}
                />
                <label className="field-label">
                  <input
                    type="checkbox"
                    checked={replaceOnRestore}
                    onChange={(e) => setReplaceOnRestore(e.target.checked)}
                  />
                  Reemplazar datos actuales antes de restaurar
                </label>
                <button type="submit">Restaurar respaldo</button>
              </div>
              <p className="muted">
                Recomendado: mantener activado el reemplazo para una restauracion limpia de ventas e inventario.
              </p>
            </section>
          </form>
        </>
      ) : null}

      {message ? <p className="muted">{message}</p> : null}
    </ProtectedShell>
  );
}
