"use client";

import { useEffect, useState } from "react";

import { ProtectedShell } from "@/components/protected-shell";
import { apiGet } from "@/lib/api";

type Kpis = {
  currency_code: string;
  sales_usd: number;
  discounts_usd: number;
  purchases_usd: number;
  gross_margin_usd: number;
};

type Daily = {
  date: string;
  sales_usd: number;
  purchases_usd: number;
};

export default function InformesPage() {
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [daily, setDaily] = useState<Daily | null>(null);

  useEffect(() => {
    Promise.all([apiGet("/reports/kpis"), apiGet("/reports/daily")])
      .then(([kpiData, dailyData]) => {
        setKpis(kpiData);
        setDaily(dailyData);
      })
      .catch(() => {
        setKpis(null);
        setDaily(null);
      });
  }, []);

  return (
    <ProtectedShell title="Informes" subtitle="KPIs y resultados diarios">
      {!kpis || !daily ? (
        <p className="muted">Cargando informes...</p>
      ) : (
        <div className="stats-grid">
          <article className="stat-item">
            <p>Ventas 7 dias (USD)</p>
            <strong>{kpis.sales_usd.toFixed(2)}</strong>
          </article>
          <article className="stat-item">
            <p>Compras 7 dias (USD)</p>
            <strong>{kpis.purchases_usd.toFixed(2)}</strong>
          </article>
          <article className="stat-item">
            <p>Descuentos 7 dias ({kpis.currency_code})</p>
            <strong>{kpis.discounts_usd.toFixed(2)}</strong>
          </article>
          <article className="stat-item">
            <p>Margen bruto 7 dias</p>
            <strong>{kpis.gross_margin_usd.toFixed(2)}</strong>
          </article>
          <article className="stat-item">
            <p>Hoy ({daily.date}) ventas/compras</p>
            <strong>
              {daily.sales_usd.toFixed(2)} / {daily.purchases_usd.toFixed(2)}
            </strong>
          </article>
        </div>
      )}
    </ProtectedShell>
  );
}
