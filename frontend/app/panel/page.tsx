"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ProtectedShell } from "@/components/protected-shell";
import { apiGet } from "@/lib/api";

type DashboardData = {
  total_articles: number;
  low_stock_articles: number;
  sales_usd: number;
  purchases_usd: number;
  gross_margin_usd: number;
  range_from: string;
  range_to: string;
};

type TimeseriesPoint = {
  date: string;
  sales_usd: number;
  purchases_usd: number;
};

function toInputDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getDefaultRange(): { from: string; to: string } {
  const today = new Date();
  const from = new Date(today);
  from.setDate(today.getDate() - 29);
  return { from: toInputDate(from), to: toInputDate(today) };
}

export default function DashboardPage() {
  const defaults = getDefaultRange();
  const [fromDate, setFromDate] = useState(defaults.from);
  const [toDate, setToDate] = useState(defaults.to);
  const [data, setData] = useState<DashboardData | null>(null);
  const [points, setPoints] = useState<TimeseriesPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadDashboard = async (from: string, to: string) => {
    setLoading(true);
    setError("");
    try {
      const [summary, timeseries] = await Promise.all([
        apiGet(`/dashboard/summary?from=${from}&to=${to}`),
        apiGet(`/dashboard/timeseries?from=${from}&to=${to}`),
      ]);
      setData(summary);
      setPoints(timeseries.points ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cargar el dashboard");
      setData(null);
      setPoints([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard(defaults.from, defaults.to).catch(() => null);
  }, []);

  const onApply = async (event: FormEvent) => {
    event.preventDefault();
    if (!fromDate || !toDate || fromDate > toDate) {
      setError("Selecciona un rango de fechas valido");
      return;
    }
    await loadDashboard(fromDate, toDate);
  };

  const onReset = async () => {
    const next = getDefaultRange();
    setFromDate(next.from);
    setToDate(next.to);
    await loadDashboard(next.from, next.to);
  };

  return (
    <ProtectedShell
      title="Dashboard"
      subtitle="Vista central con filtros por fecha y grafica de barras"
    >
      <form className="inline-actions" onSubmit={onApply}>
        <label className="field-label">
          Desde
          <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} required />
        </label>
        <label className="field-label">
          Hasta
          <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} required />
        </label>
        <button type="submit">Aplicar</button>
        <button type="button" onClick={onReset}>Ultimos 30 dias</button>
      </form>

      {error ? <p className="error-message">{error}</p> : null}
      {loading ? <p className="muted">Cargando indicadores...</p> : null}

      {!loading && data ? (
        <>
          <p className="muted">
            Rango activo: {data.range_from} a {data.range_to}
          </p>
          <div className="stats-grid">
            <article className="stat-item">
              <p>Articulos activos</p>
              <strong>{data.total_articles}</strong>
            </article>
            <article className="stat-item">
              <p>Stock bajo</p>
              <strong>{data.low_stock_articles}</strong>
            </article>
            <article className="stat-item">
              <p>Ventas del rango (USD)</p>
              <strong>{data.sales_usd.toFixed(2)}</strong>
            </article>
            <article className="stat-item">
              <p>Compras del rango (USD)</p>
              <strong>{data.purchases_usd.toFixed(2)}</strong>
            </article>
            <article className="stat-item">
              <p>Margen bruto (USD)</p>
              <strong>{data.gross_margin_usd.toFixed(2)}</strong>
            </article>
          </div>

          <h3>Ventas vs Compras por dia</h3>
          {points.length === 0 ? (
            <p className="muted">No hay datos para el rango seleccionado.</p>
          ) : (
            <div style={{ width: "100%", height: 340 }}>
              <ResponsiveContainer>
                <BarChart data={points} margin={{ top: 12, right: 16, left: 0, bottom: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(132, 182, 230, 0.22)" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(value) => value.slice(5)}
                    stroke="#9cb2c7"
                  />
                  <YAxis stroke="#9cb2c7" />
                  <Tooltip
                    contentStyle={{
                      background: "#0b1b2e",
                      border: "1px solid rgba(132, 182, 230, 0.35)",
                      borderRadius: 10,
                    }}
                  />
                  <Legend />
                  <Bar dataKey="sales_usd" name="Ventas" fill="#48d7a1" radius={[6, 6, 0, 0]} />
                  <Bar dataKey="purchases_usd" name="Compras" fill="#ff7d47" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      ) : null}
    </ProtectedShell>
  );
}
