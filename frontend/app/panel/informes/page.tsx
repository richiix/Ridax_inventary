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

type RangeSummary = {
  sales_usd: number;
  amount_paid_usd: number;
  cost_of_sales_usd: number;
  gross_profit_usd: number;
  gross_margin_pct: number;
  sales_commission_pct: number;
  commission_total_usd: number;
  purchases_usd: number;
};

type SalesLine = {
  sale_id: number;
  invoice_code: string;
  sale_date: string;
  product_id: number;
  product_name: string;
  product_type: string;
  brand: string;
  model: string;
  quantity: number;
  line_total_usd: number;
  discount_line_usd: number;
  amount_paid_line_usd: number;
  cost_line_usd: number;
  profit_line_usd: number;
  commission_pct: number;
  commission_line_usd: number;
};

type PurchaseLine = {
  id: number;
  product_id: number;
  product_name: string;
  quantity: number;
  unit_cost_usd: number;
  total_usd: number;
  supplier_name: string;
  created_at: string;
};

type RangeReport = {
  range_from: string;
  range_to: string;
  summary: RangeSummary;
  sales_lines: SalesLine[];
  purchases: PurchaseLine[];
  recommendations: string[];
};

type SellerCommissionLine = {
  seller_user_id: number | null;
  seller_name: string;
  invoice_count: number;
  line_count: number;
  amount_paid_usd: number;
  cost_usd: number;
  profit_usd: number;
  commission_usd: number;
};

type SellerCommissionReport = {
  range_from: string;
  range_to: string;
  commission_pct: number;
  summary: {
    amount_paid_usd: number;
    cost_usd: number;
    profit_usd: number;
    commission_usd: number;
  };
  sellers: SellerCommissionLine[];
};

const toInputDate = (value: Date) => value.toISOString().slice(0, 10);

export default function InformesPage() {
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [daily, setDaily] = useState<Daily | null>(null);
  const [rangeReport, setRangeReport] = useState<RangeReport | null>(null);
  const [sellerCommissionReport, setSellerCommissionReport] = useState<SellerCommissionReport | null>(null);
  const [rangePreset, setRangePreset] = useState("30d");
  const [fromDate, setFromDate] = useState(toInputDate(new Date(Date.now() - 29 * 24 * 60 * 60 * 1000)));
  const [toDate, setToDate] = useState(toInputDate(new Date()));
  const [message, setMessage] = useState("");

  const applyPreset = (preset: string) => {
    const now = new Date();
    const end = toInputDate(now);
    if (preset === "today") {
      setFromDate(end);
      setToDate(end);
      return;
    }
    const days = preset === "7d" ? 6 : 29;
    const start = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
    setFromDate(toInputDate(start));
    setToDate(end);
  };

  const loadRange = async (start: string, end: string) => {
    setMessage("");
    try {
      const [data, sellerData] = await Promise.all([
        apiGet(`/reports/range?from=${encodeURIComponent(start)}&to=${encodeURIComponent(end)}`),
        apiGet(`/reports/commission-by-seller?from=${encodeURIComponent(start)}&to=${encodeURIComponent(end)}`),
      ]);
      setRangeReport(data);
      setSellerCommissionReport(sellerData);
    } catch (err) {
      setRangeReport(null);
      setSellerCommissionReport(null);
      setMessage(err instanceof Error ? err.message : "No se pudo cargar informe por rango");
    }
  };

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

    loadRange(fromDate, toDate).catch(() => null);
  }, []);

  useEffect(() => {
    if (rangePreset !== "custom") {
      applyPreset(rangePreset);
    }
  }, [rangePreset]);

  useEffect(() => {
    if (fromDate && toDate) {
      loadRange(fromDate, toDate).catch(() => null);
    }
  }, [fromDate, toDate]);

  return (
    <ProtectedShell title="Informes" subtitle="KPIs y resultados diarios">
      <section className="article-form-section">
        <h3>Filtro de rango</h3>
        <div className="inline-actions">
          <select value={rangePreset} onChange={(e) => setRangePreset(e.target.value)}>
            <option value="today">Hoy</option>
            <option value="7d">Ultimos 7 dias</option>
            <option value="30d">Ultimos 30 dias</option>
            <option value="custom">Personalizado</option>
          </select>
          <label className="field-label">
            Inicio
            <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
          </label>
          <label className="field-label">
            Fin
            <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
          </label>
          <button type="button" onClick={() => loadRange(fromDate, toDate)}>
            Aplicar rango
          </button>
        </div>
      </section>

      {message ? <p className="alert-warning">{message}</p> : null}

      {!kpis || !daily ? (
        <p className="muted">Cargando informes...</p>
      ) : (
        <>
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

          {rangeReport ? (
            <>
              <div className="ventas-divider" />
              <h3>
                Informe detallado ({rangeReport.range_from} a {rangeReport.range_to})
              </h3>
              <div className="stats-grid">
                <article className="stat-item">
                  <p>Monto vendido (USD)</p>
                  <strong>{rangeReport.summary.sales_usd.toFixed(2)}</strong>
                </article>
                <article className="stat-item">
                  <p>Monto cobrado real (USD)</p>
                  <strong>{rangeReport.summary.amount_paid_usd.toFixed(2)}</strong>
                </article>
                <article className="stat-item">
                  <p>Costo de ventas (USD)</p>
                  <strong>{rangeReport.summary.cost_of_sales_usd.toFixed(2)}</strong>
                </article>
                <article className="stat-item">
                  <p>Ganancia bruta (USD)</p>
                  <strong>{rangeReport.summary.gross_profit_usd.toFixed(2)}</strong>
                </article>
                <article className="stat-item">
                  <p>Margen bruto (%)</p>
                  <strong>{rangeReport.summary.gross_margin_pct.toFixed(2)}%</strong>
                </article>
                <article className="stat-item">
                  <p>Comision ventas (%)</p>
                  <strong>{rangeReport.summary.sales_commission_pct.toFixed(2)}%</strong>
                </article>
                <article className="stat-item">
                  <p>Comision total (USD)</p>
                  <strong>{rangeReport.summary.commission_total_usd.toFixed(2)}</strong>
                </article>
                <article className="stat-item">
                  <p>Compras en rango (USD)</p>
                  <strong>{rangeReport.summary.purchases_usd.toFixed(2)}</strong>
                </article>
              </div>

              <section className="article-form-section">
                <h3>Recomendaciones</h3>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Recomendacion</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rangeReport.recommendations.map((item, index) => (
                        <tr key={`rec-${index + 1}`}>
                          <td>{index + 1}</td>
                          <td>{item}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className="article-form-section">
                <h3>Ventas por producto</h3>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Fecha</th>
                        <th>Factura</th>
                        <th>Producto</th>
                        <th>Tipo</th>
                        <th>Marca</th>
                        <th>Modelo</th>
                        <th>Cant.</th>
                        <th>Vendido USD</th>
                        <th>Desc USD</th>
                        <th>Cobrado USD</th>
                        <th>Costo USD</th>
                        <th>Ganancia USD</th>
                        <th>Comision USD</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rangeReport.sales_lines.map((line) => (
                        <tr key={line.sale_id}>
                          <td>{new Date(line.sale_date).toLocaleString()}</td>
                          <td>{line.invoice_code}</td>
                          <td>{line.product_name}</td>
                          <td>{line.product_type || "-"}</td>
                          <td>{line.brand || "-"}</td>
                          <td>{line.model || "-"}</td>
                          <td>{line.quantity}</td>
                          <td>{line.line_total_usd.toFixed(2)}</td>
                          <td>{line.discount_line_usd.toFixed(2)}</td>
                          <td>{line.amount_paid_line_usd.toFixed(2)}</td>
                          <td>{line.cost_line_usd.toFixed(2)}</td>
                          <td className={line.profit_line_usd >= 0 ? "badge-ok" : "badge-warn"}>{line.profit_line_usd.toFixed(2)}</td>
                          <td>{line.commission_line_usd.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              {sellerCommissionReport ? (
                <section className="article-form-section">
                  <h3>Comision por vendedor</h3>
                  <p className="muted">
                    Tasa usada: {sellerCommissionReport.commission_pct.toFixed(2)}% | Comision total: {sellerCommissionReport.summary.commission_usd.toFixed(2)} USD
                  </p>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Vendedor</th>
                          <th>Facturas</th>
                          <th>Lineas</th>
                          <th>Cobrado USD</th>
                          <th>Costo USD</th>
                          <th>Ganancia USD</th>
                          <th>Comision USD</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sellerCommissionReport.sellers.map((seller) => (
                          <tr key={seller.seller_user_id ?? seller.seller_name}>
                            <td>{seller.seller_name}</td>
                            <td>{seller.invoice_count}</td>
                            <td>{seller.line_count}</td>
                            <td>{seller.amount_paid_usd.toFixed(2)}</td>
                            <td>{seller.cost_usd.toFixed(2)}</td>
                            <td className={seller.profit_usd >= 0 ? "badge-ok" : "badge-warn"}>{seller.profit_usd.toFixed(2)}</td>
                            <td>{seller.commission_usd.toFixed(2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              ) : null}

              <section className="article-form-section">
                <h3>Compras realizadas</h3>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Fecha</th>
                        <th>ID compra</th>
                        <th>Producto</th>
                        <th>Cant.</th>
                        <th>Costo unitario</th>
                        <th>Total USD</th>
                        <th>Proveedor</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rangeReport.purchases.map((purchase) => (
                        <tr key={purchase.id}>
                          <td>{new Date(purchase.created_at).toLocaleString()}</td>
                          <td>{purchase.id}</td>
                          <td>{purchase.product_name}</td>
                          <td>{purchase.quantity}</td>
                          <td>{purchase.unit_cost_usd.toFixed(2)}</td>
                          <td>{purchase.total_usd.toFixed(2)}</td>
                          <td>{purchase.supplier_name || "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          ) : null}
        </>
      )}
    </ProtectedShell>
  );
}
