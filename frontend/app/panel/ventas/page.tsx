"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { ProtectedShell } from "@/components/protected-shell";
import { apiDownload, apiGet, apiPost } from "@/lib/api";

type ProductOption = {
  id: number;
  sku: string;
  name: string;
  final_customer_price: number;
  currency_code: string;
  is_active: boolean;
};

type CurrencyOption = { currency_code: string };

type Sale = {
  id: number;
  invoice_code: string;
  product_id: number;
  quantity: number;
  currency_code: string;
  subtotal_usd: number;
  discount_pct: number;
  discount_amount_usd: number;
  total_usd: number;
  customer_name: string;
  customer_phone: string;
  customer_address: string;
  customer_rif: string;
  created_at: string;
};

type InvoiceSummary = {
  invoice_code: string;
  currency_code: string;
  customer_name: string;
  line_count: number;
  subtotal: number;
  discount_pct: number;
  discount_amount: number;
  total: number;
  created_at: string;
};

type CartLine = {
  product_id: number;
  sku: string;
  name: string;
  quantity: number;
  unit_price: number;
};

type GeneralSettings = {
  show_discount_in_invoice: boolean;
};

export default function VentasPage() {
  const [products, setProducts] = useState<ProductOption[]>([]);
  const [currencies, setCurrencies] = useState<string[]>(["USD"]);
  const [sales, setSales] = useState<Sale[]>([]);
  const [cart, setCart] = useState<CartLine[]>([]);
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [customer, setCustomer] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [customerAddress, setCustomerAddress] = useState("");
  const [customerRif, setCustomerRif] = useState("");
  const [currencyCode, setCurrencyCode] = useState("USD");
  const [discountPct, setDiscountPct] = useState("");
  const [message, setMessage] = useState("");
  const [generalSettings, setGeneralSettings] = useState<GeneralSettings>({
    show_discount_in_invoice: true,
  });

  const selectedProduct = useMemo(
    () => products.find((item) => item.id === Number(productId)),
    [products, productId],
  );

  const subtotal = useMemo(
    () => cart.reduce((sum, line) => sum + line.quantity * line.unit_price, 0),
    [cart],
  );
  const effectiveDiscount = useMemo(() => {
    if (discountPct !== "") {
      return Number(discountPct);
    }
    return subtotal > 300 ? 7 : 0;
  }, [discountPct, subtotal]);
  const discountAmount = useMemo(
    () => (subtotal * effectiveDiscount) / 100,
    [subtotal, effectiveDiscount],
  );
  const finalTotal = useMemo(() => subtotal - discountAmount, [subtotal, discountAmount]);
  const invoiceSummaries = useMemo(() => {
    const grouped = new Map<string, InvoiceSummary>();
    for (const line of sales) {
      const existing = grouped.get(line.invoice_code);
      if (!existing) {
        grouped.set(line.invoice_code, {
          invoice_code: line.invoice_code,
          currency_code: line.currency_code,
          customer_name: line.customer_name,
          line_count: 1,
          subtotal: line.subtotal_usd,
          discount_pct: line.discount_pct,
          discount_amount: line.discount_amount_usd,
          total: line.total_usd,
          created_at: line.created_at,
        });
      } else {
        existing.line_count += 1;
        existing.subtotal += line.subtotal_usd;
        existing.discount_amount += line.discount_amount_usd;
        existing.total += line.total_usd;
      }
    }

    return Array.from(grouped.values()).map((summary) => ({
      ...summary,
      subtotal: Number(summary.subtotal.toFixed(2)),
      discount_amount: Number(summary.discount_amount.toFixed(2)),
      total: Number(summary.total.toFixed(2)),
    }));
  }, [sales]);

  const load = async () => {
    const [productList, salesList, currencyData, generalData] = await Promise.all([
      apiGet("/articles"),
      apiGet("/sales"),
      apiGet("/settings/currencies"),
      apiGet("/settings/general"),
    ]);
    setProducts(productList.filter((item: ProductOption) => item.is_active));
    setSales(salesList);
    const options = (currencyData?.rates ?? []).map((row: CurrencyOption) => row.currency_code);
    setCurrencies(options.length ? options : ["USD"]);
    setGeneralSettings({
      show_discount_in_invoice: generalData?.show_discount_in_invoice ?? true,
    });
  };

  useEffect(() => {
    load().catch(() => {
      setProducts([]);
      setSales([]);
      setCurrencies(["USD"]);
    });
  }, []);

  const addLine = (event: FormEvent) => {
    event.preventDefault();
    if (!selectedProduct) {
      setMessage("Selecciona un producto");
      return;
    }

    const qty = Number(quantity);
    if (qty <= 0) {
      setMessage("Cantidad invalida");
      return;
    }

    setCart((prev) => {
      const existing = prev.find((line) => line.product_id === selectedProduct.id);
      if (existing) {
        return prev.map((line) =>
          line.product_id === selectedProduct.id ? { ...line, quantity: line.quantity + qty } : line,
        );
      }
      return [
        ...prev,
        {
          product_id: selectedProduct.id,
          sku: selectedProduct.sku,
          name: selectedProduct.name,
          quantity: qty,
          unit_price: selectedProduct.final_customer_price,
        },
      ];
    });
    setQuantity("1");
    setProductId("");
    setMessage("");
  };

  const removeLine = (productToRemove: number) => {
    setCart((prev) => prev.filter((line) => line.product_id !== productToRemove));
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setMessage("");
    if (!cart.length) {
      setMessage("Agrega al menos un articulo a la factura.");
      return;
    }

    try {
      const response = await apiPost("/sales", {
        customer_name: customer,
        customer_phone: customerPhone,
        customer_address: customerAddress,
        customer_rif: customerRif,
        currency_code: currencyCode,
        discount_pct: effectiveDiscount,
        items: cart.map((line) => ({ product_id: line.product_id, quantity: line.quantity })),
      });
      setMessage(`Factura ${response.invoice_code} registrada con ${response.line_count} lineas.`);
      setCart([]);
      setCustomer("");
      setCustomerPhone("");
      setCustomerAddress("");
      setCustomerRif("");
      setDiscountPct("");
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo registrar la factura");
    }
  };

  return (
    <ProtectedShell title="Ventas" subtitle="Factura multi-articulo con moneda y descuento global">
      <form className="inline-actions" onSubmit={addLine}>
        <select value={productId} onChange={(e) => setProductId(e.target.value)} required>
          <option value="">Producto</option>
          {products.map((item) => (
            <option key={item.id} value={item.id}>
              {item.sku} - {item.name}
            </option>
          ))}
        </select>
        <input type="number" min="1" value={quantity} onChange={(e) => setQuantity(e.target.value)} required />
        <button type="submit">Agregar articulo</button>
      </form>

      <form className="inline-actions" onSubmit={submit}>
        <input placeholder="Cliente" value={customer} onChange={(e) => setCustomer(e.target.value)} />
        <input placeholder="Telefono" value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value)} />
        <input placeholder="Direccion" value={customerAddress} onChange={(e) => setCustomerAddress(e.target.value)} />
        <input placeholder="RIF" value={customerRif} onChange={(e) => setCustomerRif(e.target.value)} />
        <select value={currencyCode} onChange={(e) => setCurrencyCode(e.target.value)}>
          {currencies.map((code) => (
            <option key={code} value={code}>
              {code}
            </option>
          ))}
        </select>
        <input
          type="number"
          step="0.01"
          placeholder="Descuento factura %"
          value={discountPct}
          onChange={(e) => setDiscountPct(e.target.value)}
        />
        <button type="submit">Registrar factura</button>
      </form>

      <p className="muted">
        Moneda: {currencyCode} | Subtotal: {subtotal.toFixed(2)}
        {generalSettings.show_discount_in_invoice
          ? ` | Descuento: ${effectiveDiscount.toFixed(2)}% (${discountAmount.toFixed(2)})`
          : ""}
        {` | Total factura: ${finalTotal.toFixed(2)}`}
      </p>

      {message ? <p className="muted">{message}</p> : null}

      <h3>Lineas de factura</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>SKU</th>
              <th>Producto</th>
              <th>Cantidad</th>
              <th>Precio</th>
              <th>Subtotal</th>
              <th>Accion</th>
            </tr>
          </thead>
          <tbody>
            {cart.map((line) => (
              <tr key={line.product_id}>
                <td>{line.sku}</td>
                <td>{line.name}</td>
                <td>{line.quantity}</td>
                <td>{line.unit_price.toFixed(2)}</td>
                <td>{(line.quantity * line.unit_price).toFixed(2)}</td>
                <td>
                  <button type="button" onClick={() => removeLine(line.product_id)}>
                    Quitar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3>Resumen por factura</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Factura</th>
              <th>Fecha</th>
              <th>Cliente</th>
              <th>Moneda</th>
              <th>Lineas</th>
              <th>Subtotal</th>
              {generalSettings.show_discount_in_invoice ? <th>Desc %</th> : null}
              {generalSettings.show_discount_in_invoice ? <th>Desc Monto</th> : null}
              <th>Total</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {invoiceSummaries.map((invoice) => (
              <tr key={invoice.invoice_code}>
                <td>{invoice.invoice_code}</td>
                <td>{new Date(invoice.created_at).toLocaleString()}</td>
                <td>{invoice.customer_name || "-"}</td>
                <td>{invoice.currency_code}</td>
                <td>{invoice.line_count}</td>
                <td>{invoice.subtotal.toFixed(2)}</td>
                {generalSettings.show_discount_in_invoice ? <td>{invoice.discount_pct.toFixed(2)}</td> : null}
                {generalSettings.show_discount_in_invoice ? <td>{invoice.discount_amount.toFixed(2)}</td> : null}
                <td>{invoice.total.toFixed(2)}</td>
                <td>
                  <button
                    type="button"
                    onClick={() => window.open(`/panel/ventas/recibo?invoice_code=${encodeURIComponent(invoice.invoice_code)}`, "_blank")}
                  >
                    Previsualizar
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      window.open(`/panel/ventas/recibo?invoice_code=${encodeURIComponent(invoice.invoice_code)}&print=1`, "_blank")
                    }
                  >
                    Imprimir
                  </button>
                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        const blob = await apiDownload(`/sales/invoice/${invoice.invoice_code}/pdf`);
                        const url = URL.createObjectURL(blob);
                        const link = document.createElement("a");
                        link.href = url;
                        link.download = `recibo-${invoice.invoice_code}.pdf`;
                        link.click();
                        URL.revokeObjectURL(url);
                      } catch (err) {
                        setMessage(err instanceof Error ? err.message : "No se pudo descargar PDF");
                      }
                    }}
                  >
                    Descargar PDF
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3>Ultimas lineas vendidas</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Factura</th>
              <th>ID</th>
              <th>Producto ID</th>
              <th>Cantidad</th>
              <th>Moneda</th>
              <th>Subtotal</th>
              {generalSettings.show_discount_in_invoice ? <th>Desc %</th> : null}
              {generalSettings.show_discount_in_invoice ? <th>Desc Monto</th> : null}
              <th>Total</th>
              <th>Cliente</th>
            </tr>
          </thead>
          <tbody>
            {sales.map((sale) => (
              <tr key={sale.id}>
                <td>{sale.invoice_code}</td>
                <td>{sale.id}</td>
                <td>{sale.product_id}</td>
                <td>{sale.quantity}</td>
                <td>{sale.currency_code}</td>
                <td>{sale.subtotal_usd.toFixed(2)}</td>
                {generalSettings.show_discount_in_invoice ? <td>{sale.discount_pct.toFixed(2)}</td> : null}
                {generalSettings.show_discount_in_invoice ? <td>{sale.discount_amount_usd.toFixed(2)}</td> : null}
                <td>{sale.total_usd.toFixed(2)}</td>
                <td>{sale.customer_name || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ProtectedShell>
  );
}
