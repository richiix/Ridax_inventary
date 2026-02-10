"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { apiDownload, apiGet } from "@/lib/api";

type InvoicePayload = {
  invoice_code: string;
  created_at: string;
  currency_code: string;
  company: {
    name: string;
    phone: string;
    address: string;
    rif: string;
  };
  customer: {
    name: string;
    phone: string;
    address: string;
    rif: string;
  };
  totals: {
    subtotal: number;
    discount_pct: number;
    discount_amount: number;
    tax_pct: number;
    tax_amount: number;
    total: number;
    show_discount: boolean;
    tax_enabled: boolean;
  };
  items: Array<{
    sale_id: number;
    product_id: number;
    quantity: number;
    unit_price: number;
    subtotal: number;
    discount_amount: number;
    tax_amount: number;
    total: number;
  }>;
};

function ReciboPreviewContent() {
  const search = useSearchParams();
  const invoiceCode = search.get("invoice_code") ?? "";
  const [invoice, setInvoice] = useState<InvoicePayload | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!invoiceCode) {
      setError("Falta el codigo de factura");
      setInvoice(null);
      return;
    }

    setError("");
    apiGet(`/sales/invoice/${invoiceCode}`)
      .then((data) => {
        setInvoice(data);
      })
      .catch((err) => {
        setInvoice(null);
        setError(err instanceof Error ? err.message : "No se pudo cargar recibo");
      });
  }, [invoiceCode]);

  useEffect(() => {
    if (invoice && search.get("print") === "1") {
      setTimeout(() => {
        window.print();
      }, 400);
    }
  }, [invoice, search]);

  if (error) {
    return <main className="loading-screen">{error}</main>;
  }

  if (!invoice) {
    return <main className="loading-screen">Cargando recibo...</main>;
  }

  return (
    <main className="login-wrapper">
      <section className="login-card" style={{ width: "min(920px, 100%)" }}>
        <div className="inline-actions no-print">
          <button type="button" onClick={() => window.print()}>
            Imprimir
          </button>
          <button
            type="button"
            onClick={async () => {
              const blob = await apiDownload(`/sales/invoice/${invoice.invoice_code}/pdf`);
              const url = URL.createObjectURL(blob);
              const link = document.createElement("a");
              link.href = url;
              link.download = `recibo-${invoice.invoice_code}.pdf`;
              link.click();
              URL.revokeObjectURL(url);
            }}
          >
            Descargar PDF
          </button>
          <Link href="/panel/ventas" className="header-btn">
            Volver a Ventas
          </Link>
        </div>

        <h1>Recibo</h1>
        <p>
          Codigo: <strong>{invoice.invoice_code}</strong> | Fecha: {new Date(invoice.created_at).toLocaleString()} | Moneda: {invoice.currency_code}
        </p>

        <div className="stats-grid">
          <article className="stat-item">
            <p>Empresa</p>
            <strong>{invoice.company.name}</strong>
            <p>Telefono: {invoice.company.phone || "-"}</p>
            <p>Direccion: {invoice.company.address || "-"}</p>
            <p>RIF: {invoice.company.rif || "-"}</p>
          </article>
          <article className="stat-item">
            <p>Cliente</p>
            <strong>{invoice.customer.name || "Consumidor final"}</strong>
            <p>Telefono: {invoice.customer.phone || "-"}</p>
            <p>Direccion: {invoice.customer.address || "-"}</p>
            <p>RIF: {invoice.customer.rif || "-"}</p>
          </article>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Producto ID</th>
                <th>Cantidad</th>
                <th>Precio</th>
                <th>Subtotal</th>
                <th>Desc</th>
                <th>IVA</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {invoice.items.map((item) => (
                <tr key={item.sale_id}>
                  <td>{item.product_id}</td>
                  <td>{item.quantity}</td>
                  <td>{item.unit_price.toFixed(2)}</td>
                  <td>{item.subtotal.toFixed(2)}</td>
                  <td>{item.discount_amount.toFixed(2)}</td>
                  <td>{item.tax_amount.toFixed(2)}</td>
                  <td>{item.total.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="stats-grid">
          <article className="stat-item">
            <p>Subtotal</p>
            <strong>{invoice.totals.subtotal.toFixed(2)}</strong>
          </article>
          {invoice.totals.show_discount ? (
            <article className="stat-item">
              <p>Descuento ({invoice.totals.discount_pct.toFixed(2)}%)</p>
              <strong>{invoice.totals.discount_amount.toFixed(2)}</strong>
            </article>
          ) : null}
          {invoice.totals.tax_enabled ? (
            <article className="stat-item">
              <p>IVA ({invoice.totals.tax_pct.toFixed(2)}%)</p>
              <strong>{invoice.totals.tax_amount.toFixed(2)}</strong>
            </article>
          ) : null}
          <article className="stat-item">
            <p>Total</p>
            <strong>{invoice.totals.total.toFixed(2)} {invoice.currency_code}</strong>
          </article>
        </div>
      </section>
    </main>
  );
}

export default function ReciboPreviewPage() {
  return (
    <Suspense fallback={<main className="loading-screen">Cargando recibo...</main>}>
      <ReciboPreviewContent />
    </Suspense>
  );
}
