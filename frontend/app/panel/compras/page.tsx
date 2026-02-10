"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { ProtectedShell } from "@/components/protected-shell";
import { apiGet, apiPost } from "@/lib/api";

type ProductOption = {
  product_id: number;
  sku: string;
  name: string;
};

type Purchase = {
  id: number;
  product_id: number;
  quantity: number;
  unit_cost_usd: number;
  total_usd: number;
  supplier_name: string;
  purchase_note: string;
};

export default function ComprasPage() {
  const [products, setProducts] = useState<ProductOption[]>([]);
  const [purchases, setPurchases] = useState<Purchase[]>([]);
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [unitCost, setUnitCost] = useState("1");
  const [supplier, setSupplier] = useState("");
  const [purchaseNote, setPurchaseNote] = useState("");
  const [message, setMessage] = useState("");

  const purchaseTotal = useMemo(() => {
    const qty = Number(quantity || 0);
    const cost = Number(unitCost || 0);
    return qty > 0 && cost >= 0 ? qty * cost : 0;
  }, [quantity, unitCost]);

  const load = async () => {
    const [productList, purchaseList] = await Promise.all([
      apiGet("/inventory"),
      apiGet("/purchases"),
    ]);
    setProducts(productList);
    setPurchases(purchaseList);
  };

  useEffect(() => {
    load().catch(() => {
      setProducts([]);
      setPurchases([]);
    });
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setMessage("");
    try {
      await apiPost("/purchases", {
        product_id: Number(productId),
        quantity: Number(quantity),
        unit_cost_usd: Number(unitCost),
        supplier_name: supplier,
        purchase_note: purchaseNote,
      });
      setMessage("Compra registrada.");
      setQuantity("1");
      setUnitCost("1");
      setSupplier("");
      setPurchaseNote("");
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo registrar la compra");
    }
  };

  return (
    <ProtectedShell title="Compras" subtitle="Entradas de mercancia con total calculado y nota de compra">
      <div className="stat-item">
        <p>
          <strong>Guia rapida:</strong> Producto (articulo a ingresar), Cantidad (unidades), Costo unitario (precio por unidad), Proveedor (quien vende), Nota de compra (referencia/factura), Total (cantidad x costo).
        </p>
      </div>

      <form className="article-form" onSubmit={submit}>
        <section className="article-form-section">
          <h3>Datos de compra</h3>
          <div className="inline-actions">
            <label className="field-label">Producto
              <select value={productId} onChange={(e) => setProductId(e.target.value)} required>
                <option value="">Selecciona producto</option>
                {products.map((item) => (
                  <option key={item.product_id} value={item.product_id}>
                    {item.sku} - {item.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="field-label">Cantidad
              <input
                type="number"
                min="1"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                required
              />
            </label>

            <label className="field-label">Costo unitario
              <input
                type="number"
                min="0"
                step="0.01"
                value={unitCost}
                onChange={(e) => setUnitCost(e.target.value)}
                required
              />
            </label>

            <label className="field-label">Proveedor
              <input
                placeholder="Nombre del proveedor"
                value={supplier}
                onChange={(e) => setSupplier(e.target.value)}
              />
            </label>

            <label className="field-label">Nota de compra
              <input
                placeholder="Ej. Factura proveedor #123"
                value={purchaseNote}
                onChange={(e) => setPurchaseNote(e.target.value)}
              />
            </label>
          </div>
        </section>

        <div className="stats-grid">
          <article className="stat-item">
            <p>Total calculado</p>
            <strong>{purchaseTotal.toFixed(2)} USD</strong>
          </article>
        </div>

        <div className="inline-actions">
          <button type="submit" disabled={Number(quantity) <= 0 || Number(unitCost) < 0}>Registrar compra</button>
        </div>
      </form>

      {message ? <p className="muted">{message}</p> : null}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Producto ID</th>
              <th>Cantidad</th>
              <th>Costo unitario</th>
              <th>Total USD</th>
              <th>Proveedor</th>
              <th>Nota</th>
            </tr>
          </thead>
          <tbody>
            {purchases.map((purchase) => (
              <tr key={purchase.id}>
                <td>{purchase.id}</td>
                <td>{purchase.product_id}</td>
                <td>{purchase.quantity}</td>
                <td>{purchase.unit_cost_usd.toFixed(2)}</td>
                <td>{purchase.total_usd.toFixed(2)}</td>
                <td>{purchase.supplier_name || "-"}</td>
                <td>{purchase.purchase_note || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ProtectedShell>
  );
}
