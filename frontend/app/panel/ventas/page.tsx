"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { ProtectedShell } from "@/components/protected-shell";
import { apiDownload, apiGet, apiPatch, apiPost } from "@/lib/api";

type ProductOption = {
  id: number;
  sku: string;
  name: string;
  product_type: string;
  brand: string;
  model: string;
  final_customer_price: number;
  wholesale_price: number;
  retail_price: number;
  currency_code: string;
  stock: number;
  is_active: boolean;
};

type CurrencyOption = { currency_code: string; rate_to_usd: number };

type SellerOption = {
  id: number;
  full_name: string;
  email: string;
};

type Sale = {
  id: number;
  invoice_code: string;
  product_id: number;
  product_name?: string;
  product_type?: string;
  brand?: string;
  model?: string;
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
  seller_user_id?: number;
  seller_name?: string;
  sale_date?: string;
  payment_currency_code?: string;
  payment_amount?: number;
  payment_rate_to_usd?: number;
  payment_amount_usd?: number;
  commission_pct?: number;
  commission_amount_usd?: number;
  manual_total_override?: boolean;
  manual_total_input_usd?: number | null;
  manual_total_original_usd?: number | null;
  is_voided?: boolean;
  voided_at?: string;
  voided_by?: number;
  voided_by_name?: string;
  void_reason?: string;
  created_at: string;
};

type InvoiceSummary = {
  invoice_code: string;
  currency_code: string;
  customer_name: string;
  seller_name: string;
  sale_date: string;
  payment_currency_code: string;
  payment_amount: number;
  payment_amount_usd: number;
  is_voided: boolean;
  voided_at: string;
  voided_by_name: string;
  void_reason: string;
  line_count: number;
  subtotal: number;
  discount_pct: number;
  discount_amount: number;
  total: number;
  commission_amount_usd: number;
  manual_total_override: boolean;
  created_at: string;
};

type CartLine = {
  product_id: number;
  sku: string;
  name: string;
  brand: string;
  quantity: number;
  unit_price: number;
  wholesale_price: number;
  retail_price: number;
};

type InvoiceEditLine = {
  product_id: number;
  quantity: number;
};

type InvoiceDetail = {
  invoice_code: string;
  customer: {
    name: string;
    phone: string;
    address: string;
    rif: string;
  };
  sale: {
    seller_user_id: number | null;
    sale_date: string;
  };
  payment: {
    currency_code: string;
    amount: number | null;
  };
  manual_override?: {
    enabled: boolean;
    manual_total_input_usd: number | null;
  };
  items: InvoiceEditLine[];
};

type GeneralSettings = {
  show_discount_in_invoice: boolean;
};

export default function VentasPage() {
  const [products, setProducts] = useState<ProductOption[]>([]);
  const [currencies, setCurrencies] = useState<string[]>(["USD"]);
  const [currencyRates, setCurrencyRates] = useState<Record<string, number>>({ USD: 1 });
  const [sellers, setSellers] = useState<SellerOption[]>([]);
  const [sales, setSales] = useState<Sale[]>([]);
  const [cart, setCart] = useState<CartLine[]>([]);
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [customer, setCustomer] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [customerAddress, setCustomerAddress] = useState("");
  const [customerRif, setCustomerRif] = useState("");
  const [currencyCode, setCurrencyCode] = useState("USD");
  const [paymentCurrencyCode, setPaymentCurrencyCode] = useState("USD");
  const [paymentAmount, setPaymentAmount] = useState("");
  const [manualInvoiceTotal, setManualInvoiceTotal] = useState("");
  const [sellerUserId, setSellerUserId] = useState("");
  const [sellerRole, setSellerRole] = useState("");
  const [saleDate, setSaleDate] = useState(() => new Date().toISOString().slice(0, 16));
  const [selectedInvoices, setSelectedInvoices] = useState<string[]>([]);
  const [showVoidedInvoices, setShowVoidedInvoices] = useState(false);
  const [editingInvoiceCode, setEditingInvoiceCode] = useState("");
  const [editCustomer, setEditCustomer] = useState("");
  const [editCustomerPhone, setEditCustomerPhone] = useState("");
  const [editCustomerAddress, setEditCustomerAddress] = useState("");
  const [editCustomerRif, setEditCustomerRif] = useState("");
  const [editSellerUserId, setEditSellerUserId] = useState("");
  const [editSaleDate, setEditSaleDate] = useState("");
  const [editPaymentCurrencyCode, setEditPaymentCurrencyCode] = useState("USD");
  const [editPaymentAmount, setEditPaymentAmount] = useState("");
  const [editManualInvoiceTotal, setEditManualInvoiceTotal] = useState("");
  const [editLines, setEditLines] = useState<InvoiceEditLine[]>([]);
  const [editProductId, setEditProductId] = useState("");
  const [editQuantity, setEditQuantity] = useState("1");
  const [discountPct, setDiscountPct] = useState("");
  const [submitAlert, setSubmitAlert] = useState("");
  const [cartWarning, setCartWarning] = useState(false);
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
  const effectivePaymentAmount = useMemo(() => {
    if (paymentAmount.trim() === "") {
      const rate = currencyRates[paymentCurrencyCode] ?? 1;
      return Number((finalTotal * rate).toFixed(2));
    }
    return Number(paymentAmount);
  }, [paymentAmount, paymentCurrencyCode, currencyRates, finalTotal]);
  const paymentAmountUsd = useMemo(() => {
    const rate = currencyRates[paymentCurrencyCode] ?? 1;
    if (!rate || Number.isNaN(effectivePaymentAmount)) {
      return 0;
    }
    return Number((effectivePaymentAmount / rate).toFixed(2));
  }, [effectivePaymentAmount, paymentCurrencyCode, currencyRates]);
  const paymentDifferenceUsd = useMemo(
    () => Number((paymentAmountUsd - finalTotal).toFixed(2)),
    [paymentAmountUsd, finalTotal],
  );
  const invoiceSummaries = useMemo(() => {
    const grouped = new Map<string, InvoiceSummary>();
    for (const line of sales) {
      const existing = grouped.get(line.invoice_code);
      if (!existing) {
        grouped.set(line.invoice_code, {
          invoice_code: line.invoice_code,
          currency_code: line.currency_code,
          customer_name: line.customer_name,
          seller_name: line.seller_name || "-",
          sale_date: line.sale_date || line.created_at,
          payment_currency_code: line.payment_currency_code || "USD",
          payment_amount: Number(line.payment_amount ?? 0),
          payment_amount_usd: Number(line.payment_amount_usd ?? 0),
          is_voided: Boolean(line.is_voided),
          voided_at: line.voided_at || "",
          voided_by_name: line.voided_by_name || "",
          void_reason: line.void_reason || "",
          line_count: 1,
          subtotal: line.subtotal_usd,
          discount_pct: line.discount_pct,
          discount_amount: line.discount_amount_usd,
          total: line.total_usd,
          commission_amount_usd: Number(line.commission_amount_usd ?? 0),
          manual_total_override: Boolean(line.manual_total_override),
          created_at: line.created_at,
        });
      } else {
        existing.line_count += 1;
        existing.subtotal += line.subtotal_usd;
        existing.discount_amount += line.discount_amount_usd;
        existing.total += line.total_usd;
        existing.commission_amount_usd += Number(line.commission_amount_usd ?? 0);
        existing.manual_total_override = existing.manual_total_override || Boolean(line.manual_total_override);
        if (!existing.void_reason && line.void_reason) {
          existing.void_reason = line.void_reason;
        }
        if (!existing.voided_by_name && line.voided_by_name) {
          existing.voided_by_name = line.voided_by_name;
        }
        if (!existing.voided_at && line.voided_at) {
          existing.voided_at = line.voided_at;
        }
      }
    }

    return Array.from(grouped.values()).map((summary) => ({
      ...summary,
      subtotal: Number(summary.subtotal.toFixed(2)),
      discount_amount: Number(summary.discount_amount.toFixed(2)),
      total: Number(summary.total.toFixed(2)),
      commission_amount_usd: Number(summary.commission_amount_usd.toFixed(2)),
    }));
  }, [sales]);
  const isAdmin = sellerRole === "admin";
  const canVoidInvoices = isAdmin && !showVoidedInvoices;
  const canEditLines = isAdmin;
  const selectedInvoiceSet = useMemo(() => new Set(selectedInvoices), [selectedInvoices]);

  const load = async () => {
    const salesPath = showVoidedInvoices ? "/sales?only_voided=true" : "/sales";
    const [productsResult, salesResult, currenciesResult, generalResult, vendorsResult, meResult] = await Promise.allSettled([
      apiGet("/sales/products"),
      apiGet(salesPath),
      apiGet("/sales/currencies"),
      apiGet("/settings/general"),
      apiGet("/sales/vendors"),
      apiGet("/auth/me"),
    ]);

    if (productsResult.status === "fulfilled") {
      setProducts(productsResult.value.filter((item: ProductOption) => item.is_active));
    } else {
      setProducts([]);
      setMessage("No se pudo cargar productos para venta");
    }

    if (salesResult.status === "fulfilled") {
      setSales(salesResult.value);
      const available = new Set((salesResult.value as Sale[]).map((line) => line.invoice_code));
      setSelectedInvoices((prev) => prev.filter((code) => available.has(code)));
    } else {
      setSales([]);
      setSelectedInvoices([]);
      if (showVoidedInvoices) {
        setMessage("No se pudieron cargar facturas anuladas");
      }
    }

    if (currenciesResult.status === "fulfilled") {
      const options = (currenciesResult.value ?? []).map((row: CurrencyOption) => row.currency_code);
      const rates = Object.fromEntries((currenciesResult.value ?? []).map((row: CurrencyOption) => [row.currency_code, row.rate_to_usd]));
      setCurrencies(options.length ? options : ["USD"]);
      setCurrencyRates(Object.keys(rates).length ? rates : { USD: 1 });
    } else {
      setCurrencies(["USD"]);
      setCurrencyRates({ USD: 1 });
    }

    if (generalResult.status === "fulfilled") {
      setGeneralSettings({
        show_discount_in_invoice: generalResult.value?.show_discount_in_invoice ?? true,
      });
    }

    if (vendorsResult.status === "fulfilled") {
      setSellers(vendorsResult.value);
      if (!sellerUserId && vendorsResult.value.length > 0) {
        setSellerUserId(String(vendorsResult.value[0].id));
      }
    } else {
      setSellers([]);
    }

    if (meResult.status === "fulfilled") {
      setSellerRole(String(meResult.value?.role || "").toLowerCase());
      if (!sellerUserId && meResult.value?.id) {
        setSellerUserId(String(meResult.value.id));
      }
    }
  };

  useEffect(() => {
    load().catch(() => {
      setProducts([]);
      setSales([]);
      setCurrencies(["USD"]);
      setCurrencyRates({ USD: 1 });
      setSellers([]);
    });
  }, [showVoidedInvoices]);

  const addLine = (event: FormEvent) => {
    event.preventDefault();
    setSubmitAlert("");
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
          brand: selectedProduct.brand,
          quantity: qty,
          unit_price: selectedProduct.final_customer_price,
          wholesale_price: selectedProduct.wholesale_price,
          retail_price: selectedProduct.retail_price,
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

  const toggleInvoiceSelection = (invoiceCode: string) => {
    setSelectedInvoices((prev) => {
      if (prev.includes(invoiceCode)) {
        return prev.filter((code) => code !== invoiceCode);
      }
      return [...prev, invoiceCode];
    });
  };

  const toggleSelectAllInvoices = () => {
    if (selectedInvoices.length === invoiceSummaries.length) {
      setSelectedInvoices([]);
      return;
    }
    setSelectedInvoices(invoiceSummaries.map((invoice) => invoice.invoice_code));
  };

  const voidSelectedInvoices = async () => {
    if (!selectedInvoices.length) {
      setMessage("Selecciona al menos una factura para anular");
      return;
    }
    const preview = selectedInvoices.slice(0, 5).join(", ");
    const suffix = selectedInvoices.length > 5 ? "..." : "";
    const confirmed = window.confirm(
      `Se anularan ${selectedInvoices.length} facturas y se revertira inventario.\n${preview}${suffix}`,
    );
    if (!confirmed) {
      return;
    }

    try {
      const response = await apiPost("/sales/invoices/void", { invoice_codes: selectedInvoices });
      setMessage(`${response.message}: ${response.voided_invoices.join(", ")}`);
      setSelectedInvoices([]);
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudieron anular facturas");
    }
  };

  const exportVoidedInvoicesReport = async () => {
    try {
      const blob = await apiDownload("/sales/invoices/void/report?format=csv");
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `ridax-anulaciones-${new Date().toISOString().slice(0, 10)}.csv`;
      link.click();
      URL.revokeObjectURL(url);
      setMessage("Reporte de anulaciones exportado.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo exportar reporte de anulaciones");
    }
  };

  const startEditInvoice = async (invoiceCode: string) => {
    try {
      const detail = (await apiGet(`/sales/invoice/${invoiceCode}`)) as InvoiceDetail;
      setEditingInvoiceCode(detail.invoice_code);
      setEditCustomer(detail.customer?.name || "");
      setEditCustomerPhone(detail.customer?.phone || "");
      setEditCustomerAddress(detail.customer?.address || "");
      setEditCustomerRif(detail.customer?.rif || "");
      setEditSellerUserId(String(detail.sale?.seller_user_id || ""));
      setEditSaleDate(new Date(detail.sale?.sale_date || Date.now()).toISOString().slice(0, 16));
      setEditPaymentCurrencyCode(detail.payment?.currency_code || "USD");
      setEditPaymentAmount(String(detail.payment?.amount ?? ""));
      setEditManualInvoiceTotal(
        detail.manual_override?.enabled && detail.manual_override.manual_total_input_usd != null
          ? String(detail.manual_override.manual_total_input_usd)
          : "",
      );
      setEditLines(detail.items.map((item) => ({ product_id: item.product_id, quantity: item.quantity })));
      setEditProductId("");
      setEditQuantity("1");
      setMessage(`Editando factura ${detail.invoice_code}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo cargar factura para editar");
    }
  };

  const cancelEditInvoice = () => {
    setEditingInvoiceCode("");
    setEditLines([]);
    setEditManualInvoiceTotal("");
  };

  const updateEditLineQuantity = (productId: number, quantityValue: number) => {
    if (!canEditLines) {
      return;
    }
    setEditLines((prev) =>
      prev.map((line) => (line.product_id === productId ? { ...line, quantity: Math.max(1, quantityValue || 1) } : line)),
    );
  };

  const removeEditLine = (productId: number) => {
    if (!canEditLines) {
      return;
    }
    setEditLines((prev) => prev.filter((line) => line.product_id !== productId));
  };

  const addEditLine = () => {
    if (!canEditLines || !editProductId) {
      return;
    }
    const pid = Number(editProductId);
    const qty = Math.max(1, Number(editQuantity) || 1);
    setEditLines((prev) => {
      const existing = prev.find((line) => line.product_id === pid);
      if (existing) {
        return prev.map((line) => (line.product_id === pid ? { ...line, quantity: line.quantity + qty } : line));
      }
      return [...prev, { product_id: pid, quantity: qty }];
    });
    setEditProductId("");
    setEditQuantity("1");
  };

  const submitEditInvoice = async (event: FormEvent) => {
    event.preventDefault();
    if (!editingInvoiceCode) {
      return;
    }

    try {
      const payload: Record<string, unknown> = {
        customer_name: editCustomer,
        customer_phone: editCustomerPhone,
        customer_address: editCustomerAddress,
        customer_rif: editCustomerRif,
        seller_user_id: editSellerUserId ? Number(editSellerUserId) : undefined,
        sale_date: editSaleDate ? new Date(editSaleDate).toISOString() : undefined,
        payment_currency_code: editPaymentCurrencyCode,
        payment_amount: editPaymentAmount === "" ? undefined : Number(editPaymentAmount),
      };
      if (canEditLines) {
        payload.items = editLines;
        payload.manual_invoice_total = editManualInvoiceTotal === "" ? null : Number(editManualInvoiceTotal);
      }
      const response = await apiPatch(`/sales/invoice/${encodeURIComponent(editingInvoiceCode)}`, payload);
      setMessage(`${response.message}: ${response.invoice_code}`);
      await load();
      cancelEditInvoice();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo editar la factura");
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setMessage("");

    const playWarningTone = () => {
      try {
        const AudioCtx = window.AudioContext || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
        if (!AudioCtx) {
          return;
        }
        const ctx = new AudioCtx();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "square";
        osc.frequency.value = 880;
        gain.gain.setValueAtTime(0.0001, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.12, ctx.currentTime + 0.01);
        gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.18);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.2);
        osc.onended = () => {
          ctx.close().catch(() => null);
        };
      } catch {
        // Non-blocking feedback fallback
      }
    };

    if (!cart.length) {
      setSubmitAlert("Debes agregar al menos un articulo al carrito antes de registrar la factura.");
      setCartWarning(true);
      playWarningTone();
      window.setTimeout(() => setCartWarning(false), 1300);
      return;
    }

    const normalizedCustomer = customer.trim();
    if (!normalizedCustomer) {
      setSubmitAlert("Debes indicar el nombre del cliente para registrar la factura.");
      playWarningTone();
      return;
    }
    setSubmitAlert("");

    const requestPayload = {
      customer_name: normalizedCustomer,
      customer_phone: customerPhone,
      customer_address: customerAddress,
      customer_rif: customerRif,
      currency_code: currencyCode,
      discount_pct: effectiveDiscount,
      seller_user_id: sellerUserId ? Number(sellerUserId) : undefined,
      sale_date: saleDate ? new Date(saleDate).toISOString() : undefined,
      payment_currency_code: paymentCurrencyCode,
      payment_amount: effectivePaymentAmount,
      manual_invoice_total: isAdmin && manualInvoiceTotal !== "" ? Number(manualInvoiceTotal) : undefined,
      items: cart.map((line) => ({ product_id: line.product_id, quantity: line.quantity })),
    };

    const finishSuccess = async (response: { invoice_code: string; line_count: number }) => {
      setMessage(`Factura ${response.invoice_code} registrada con ${response.line_count} lineas.`);
      setCart([]);
      setCustomer("");
      setCustomerPhone("");
      setCustomerAddress("");
      setCustomerRif("");
      setDiscountPct("");
      setPaymentAmount("");
      setManualInvoiceTotal("");
      await load();
    };

    try {
      const response = await apiPost("/sales", requestPayload);
      await finishSuccess(response);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "No se pudo registrar la factura";
      if (errorMessage.includes("mismo monto")) {
        const confirmed = window.confirm(
          "Se detectaron facturas con el mismo monto en las ultimas 24 horas.\n\n¿Deseas continuar de todas formas?",
        );
        if (!confirmed) {
          setMessage("Registro cancelado por posible duplicado.");
          return;
        }
        try {
          const forcedResponse = await apiPost("/sales", {
            ...requestPayload,
            confirm_possible_duplicate: true,
          });
          await finishSuccess(forcedResponse);
          return;
        } catch (retryError) {
          setMessage(retryError instanceof Error ? retryError.message : "No se pudo registrar la factura");
          return;
        }
      }
      setMessage(errorMessage);
    }
  };

  return (
    <ProtectedShell title="Ventas" subtitle="Factura multi-articulo con moneda y descuento global">
      <section className="ventas-block">
        <h3>Agregar articulo</h3>
        <form className="inline-actions" onSubmit={addLine}>
          <select value={productId} onChange={(e) => setProductId(e.target.value)} required>
            <option value="">Producto</option>
            {products.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} | {item.product_type || "-"} | {item.brand || "-"} | {item.model || "-"} | Stock: {item.stock}
              </option>
            ))}
          </select>
          <input type="number" min="1" value={quantity} onChange={(e) => setQuantity(e.target.value)} required />
          <button type="submit">Agregar articulo</button>
        </form>
      </section>

      <section className="ventas-block">
        <h3>Datos de factura</h3>
        <form className="inline-actions" onSubmit={submit}>
          <select value={sellerUserId} onChange={(e) => setSellerUserId(e.target.value)} disabled={sellerRole === "vendedor"}>
            <option value="">Vendedor</option>
            {sellers.map((seller) => (
              <option key={seller.id} value={seller.id}>
                {seller.full_name} ({seller.email})
              </option>
            ))}
          </select>
          <input type="datetime-local" value={saleDate} onChange={(e) => setSaleDate(e.target.value)} />
          <input placeholder="Cliente" value={customer} onChange={(e) => setCustomer(e.target.value)} required />
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
          <select value={paymentCurrencyCode} onChange={(e) => setPaymentCurrencyCode(e.target.value)}>
            {currencies.map((code) => (
              <option key={`pay-${code}`} value={code}>
                Pago {code}
              </option>
            ))}
          </select>
          <input
            type="number"
            step="0.01"
            placeholder="Monto pagado"
            value={paymentAmount}
            onChange={(e) => setPaymentAmount(e.target.value)}
          />
          <input
            type="number"
            step="0.01"
            placeholder="Descuento factura %"
            value={discountPct}
            onChange={(e) => setDiscountPct(e.target.value)}
          />
          {isAdmin ? (
            <input
              type="number"
              step="0.01"
              min="0"
              placeholder="Total manual factura (USD)"
              value={manualInvoiceTotal}
              onChange={(e) => setManualInvoiceTotal(e.target.value)}
            />
          ) : null}
          <button type="submit">Registrar factura</button>
        </form>
      </section>

      <p className="muted">
        Moneda: {currencyCode} | Subtotal: {subtotal.toFixed(2)}
        {generalSettings.show_discount_in_invoice
          ? ` | Descuento: ${effectiveDiscount.toFixed(2)}% (${discountAmount.toFixed(2)})`
          : ""}
        {` | Total factura: ${finalTotal.toFixed(2)}`}
        {isAdmin && manualInvoiceTotal !== "" ? ` | Total manual: ${Number(manualInvoiceTotal).toFixed(2)}` : ""}
        {` | Pago: ${effectivePaymentAmount.toFixed(2)} ${paymentCurrencyCode}`}
        {` | Equivale USD: ${paymentAmountUsd.toFixed(2)}`}
        {` | Diferencia USD: ${paymentDifferenceUsd.toFixed(2)}`}
      </p>

      {submitAlert ? (
        <p className="alert-warning" role="alert" aria-live="assertive">
          {submitAlert}
        </p>
      ) : null}

      {message ? <p className="muted">{message}</p> : null}

      {isAdmin ? (
        <details className="ventas-admin-menu">
          <summary>Opciones admin</summary>
          <div className="inline-actions">
            <label className="field-label">
              <input
                type="checkbox"
                checked={showVoidedInvoices}
                onChange={(e) => {
                  setShowVoidedInvoices(e.target.checked);
                  setSelectedInvoices([]);
                }}
              />
              Ver facturas anuladas
            </label>
            <button type="button" onClick={exportVoidedInvoicesReport}>
              Exportar anulaciones CSV
            </button>
            {canVoidInvoices ? (
              <>
                <span className="muted">Facturas seleccionadas: {selectedInvoices.length}</span>
                <button type="button" onClick={voidSelectedInvoices} disabled={!selectedInvoices.length}>
                  Anular seleccionadas
                </button>
              </>
            ) : null}
          </div>
        </details>
      ) : null}

      <section className={cartWarning ? "ventas-block ventas-cart-warning" : "ventas-block"}>
        <h3>Lineas de factura</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>SKU</th>
                <th>Producto</th>
                <th>Marca</th>
                <th>Cantidad</th>
                <th>Mayor</th>
                <th>Detal</th>
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
                  <td>{line.brand || "-"}</td>
                  <td>{line.quantity}</td>
                  <td>
                    <span className="price-wholesale">{line.wholesale_price.toFixed(2)}</span>
                  </td>
                  <td>
                    <span className="price-retail">{line.retail_price.toFixed(2)}</span>
                  </td>
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
      </section>

      <h3>Resumen por factura</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {canVoidInvoices ? (
                <th>
                  <input
                    type="checkbox"
                    checked={invoiceSummaries.length > 0 && selectedInvoices.length === invoiceSummaries.length}
                    onChange={toggleSelectAllInvoices}
                  />
                </th>
              ) : null}
              <th>Factura</th>
              <th>Fecha</th>
              <th>Cliente</th>
              <th>Vendedor</th>
              <th>Moneda</th>
              <th>Monto pago</th>
              <th>Eq. USD</th>
              <th>Lineas</th>
              <th>Subtotal</th>
              {generalSettings.show_discount_in_invoice ? <th>Desc %</th> : null}
              {generalSettings.show_discount_in_invoice ? <th>Desc Monto</th> : null}
              <th>Total</th>
              <th>Comision</th>
              <th>Total manual</th>
              {showVoidedInvoices ? <th>Anulada por</th> : null}
              {showVoidedInvoices ? <th>Fecha anulacion</th> : null}
              {showVoidedInvoices ? <th>Motivo</th> : null}
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {invoiceSummaries.map((invoice) => (
              <tr key={invoice.invoice_code}>
                {canVoidInvoices ? (
                  <td>
                    <input
                      type="checkbox"
                      checked={selectedInvoiceSet.has(invoice.invoice_code)}
                      onChange={() => toggleInvoiceSelection(invoice.invoice_code)}
                    />
                  </td>
                ) : null}
                <td>{invoice.invoice_code}</td>
                <td>{new Date(invoice.sale_date || invoice.created_at).toLocaleString()}</td>
                <td>{invoice.customer_name || "-"}</td>
                <td>{invoice.seller_name || "-"}</td>
                <td>{invoice.currency_code}</td>
                <td>{invoice.payment_amount.toFixed(2)} {invoice.payment_currency_code}</td>
                <td>{invoice.payment_amount_usd.toFixed(2)}</td>
                <td>{invoice.line_count}</td>
                <td>{invoice.subtotal.toFixed(2)}</td>
                {generalSettings.show_discount_in_invoice ? <td>{invoice.discount_pct.toFixed(2)}</td> : null}
                {generalSettings.show_discount_in_invoice ? <td>{invoice.discount_amount.toFixed(2)}</td> : null}
                <td>{invoice.total.toFixed(2)}</td>
                <td>{invoice.commission_amount_usd.toFixed(2)}</td>
                <td>{invoice.manual_total_override ? "Si" : "No"}</td>
                {showVoidedInvoices ? <td>{invoice.voided_by_name || "-"}</td> : null}
                {showVoidedInvoices ? <td>{invoice.voided_at ? new Date(invoice.voided_at).toLocaleString() : "-"}</td> : null}
                {showVoidedInvoices ? <td>{invoice.void_reason || "-"}</td> : null}
                <td>
                  {showVoidedInvoices ? (
                    <span className="muted">Factura anulada</span>
                  ) : (
                    <>
                      <button type="button" onClick={() => startEditInvoice(invoice.invoice_code)}>
                        Editar
                      </button>
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
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editingInvoiceCode ? (
        <section className="ventas-block">
          <h3>Editar factura {editingInvoiceCode}</h3>
          <form className="article-form" onSubmit={submitEditInvoice}>
            <section className="article-form-section">
              <h3>Datos generales</h3>
              <div className="inline-actions">
                <select value={editSellerUserId} onChange={(e) => setEditSellerUserId(e.target.value)} disabled={sellerRole === "vendedor"}>
                  <option value="">Vendedor</option>
                  {sellers.map((seller) => (
                    <option key={`edit-${seller.id}`} value={seller.id}>
                      {seller.full_name} ({seller.email})
                    </option>
                  ))}
                </select>
                <input type="datetime-local" value={editSaleDate} onChange={(e) => setEditSaleDate(e.target.value)} />
                <input placeholder="Cliente" value={editCustomer} onChange={(e) => setEditCustomer(e.target.value)} />
                <input placeholder="Telefono" value={editCustomerPhone} onChange={(e) => setEditCustomerPhone(e.target.value)} />
                <input placeholder="Direccion" value={editCustomerAddress} onChange={(e) => setEditCustomerAddress(e.target.value)} />
                <input placeholder="RIF" value={editCustomerRif} onChange={(e) => setEditCustomerRif(e.target.value)} />
                <select value={editPaymentCurrencyCode} onChange={(e) => setEditPaymentCurrencyCode(e.target.value)}>
                  {currencies.map((code) => (
                    <option key={`edit-pay-${code}`} value={code}>
                      Pago {code}
                    </option>
                  ))}
                </select>
                <input
                  type="number"
                  step="0.01"
                  placeholder="Monto pagado"
                  value={editPaymentAmount}
                  onChange={(e) => setEditPaymentAmount(e.target.value)}
                />
                {canEditLines ? (
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    placeholder="Total manual factura (USD)"
                    value={editManualInvoiceTotal}
                    onChange={(e) => setEditManualInvoiceTotal(e.target.value)}
                  />
                ) : null}
              </div>
            </section>

            <section className="article-form-section">
              <h3>Lineas de factura</h3>
              {canEditLines ? (
                <div className="inline-actions">
                  <select value={editProductId} onChange={(e) => setEditProductId(e.target.value)}>
                    <option value="">Producto para agregar</option>
                    {products.map((item) => (
                      <option key={`line-${item.id}`} value={item.id}>
                        {item.name} | {item.product_type || "-"} | {item.brand || "-"} | {item.model || "-"} | Stock: {item.stock}
                      </option>
                    ))}
                  </select>
                  <input type="number" min="1" value={editQuantity} onChange={(e) => setEditQuantity(e.target.value)} />
                  <button type="button" onClick={addEditLine}>
                    Agregar linea
                  </button>
                </div>
              ) : (
                <p className="muted">Como vendedor puedes editar solo datos generales de la factura.</p>
              )}

              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Producto</th>
                      <th>Cantidad</th>
                      <th>Accion</th>
                    </tr>
                  </thead>
                  <tbody>
                    {editLines.map((line) => {
                      const product = products.find((item) => item.id === line.product_id);
                      const label = product
                        ? `${product.name} | ${product.product_type || "-"} | ${product.brand || "-"} | ${product.model || "-"}`
                        : `Producto #${line.product_id}`;
                      return (
                        <tr key={`edit-row-${line.product_id}`}>
                          <td>{label}</td>
                          <td>
                            {canEditLines ? (
                              <input
                                type="number"
                                min="1"
                                value={line.quantity}
                                onChange={(e) => updateEditLineQuantity(line.product_id, Number(e.target.value))}
                              />
                            ) : (
                              line.quantity
                            )}
                          </td>
                          <td>
                            {canEditLines ? (
                              <button type="button" onClick={() => removeEditLine(line.product_id)}>
                                Quitar
                              </button>
                            ) : (
                              <span className="muted">-</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>

            <div className="inline-actions">
              <button type="submit">Guardar cambios</button>
              <button type="button" onClick={cancelEditInvoice}>
                Cancelar
              </button>
            </div>
          </form>
        </section>
      ) : null}

      <div className="ventas-divider" />

      <h3>Ultimas lineas vendidas</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Factura</th>
              <th>ID</th>
              <th>Producto ID</th>
              <th>Producto</th>
              <th>Marca</th>
              <th>Cantidad</th>
              <th>Fecha venta</th>
              <th>Vendedor</th>
              <th>Moneda</th>
              <th>Monto pago</th>
              <th>Subtotal</th>
              {generalSettings.show_discount_in_invoice ? <th>Desc %</th> : null}
              {generalSettings.show_discount_in_invoice ? <th>Desc Monto</th> : null}
              <th>Total</th>
              <th>Comision</th>
              <th>Cliente</th>
              {showVoidedInvoices ? <th>Anulada por</th> : null}
              {showVoidedInvoices ? <th>Fecha anulacion</th> : null}
              {showVoidedInvoices ? <th>Motivo</th> : null}
            </tr>
          </thead>
          <tbody>
            {sales.map((sale) => (
              <tr key={sale.id}>
                <td>{sale.invoice_code}</td>
                <td>{sale.id}</td>
                <td>{sale.product_id}</td>
                <td>{sale.product_name || `#${sale.product_id}`}</td>
                <td>{sale.brand || "-"}</td>
                <td>{sale.quantity}</td>
                <td>{new Date(sale.sale_date || sale.created_at).toLocaleString()}</td>
                <td>{sale.seller_name || "-"}</td>
                <td>{sale.currency_code}</td>
                <td>{Number(sale.payment_amount ?? 0).toFixed(2)} {sale.payment_currency_code || "USD"}</td>
                <td>{sale.subtotal_usd.toFixed(2)}</td>
                {generalSettings.show_discount_in_invoice ? <td>{sale.discount_pct.toFixed(2)}</td> : null}
                {generalSettings.show_discount_in_invoice ? <td>{sale.discount_amount_usd.toFixed(2)}</td> : null}
                <td>{sale.total_usd.toFixed(2)}</td>
                <td>{Number(sale.commission_amount_usd ?? 0).toFixed(2)}</td>
                <td>{sale.customer_name || "-"}</td>
                {showVoidedInvoices ? <td>{sale.voided_by_name || "-"}</td> : null}
                {showVoidedInvoices ? <td>{sale.voided_at ? new Date(sale.voided_at).toLocaleString() : "-"}</td> : null}
                {showVoidedInvoices ? <td>{sale.void_reason || "-"}</td> : null}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ProtectedShell>
  );
}
