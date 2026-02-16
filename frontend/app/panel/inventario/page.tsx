"use client";

import { FormEvent, useEffect, useState } from "react";

import { ProtectedShell } from "@/components/protected-shell";
import { apiGet, apiPost } from "@/lib/api";

type InventoryRow = {
  product_id: number;
  sku: string;
  name: string;
  product_type: string;
  brand: string;
  model: string;
  wholesale_price: number;
  retail_price: number;
  currency_code: string;
  stock: number;
  status: string;
  created_at: string;
};

type InventoryMovement = {
  id: number;
  product_id: number;
  movement_type: string;
  quantity: number;
  note: string;
  created_by: number;
  created_at: string;
};

export default function InventarioPage() {
  const [rows, setRows] = useState<InventoryRow[]>([]);
  const [movements, setMovements] = useState<InventoryMovement[]>([]);
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [adjustType, setAdjustType] = useState("entry");
  const [message, setMessage] = useState("");
  const [showMovements, setShowMovements] = useState(false);

  const load = async () => {
    const [inventoryRows, movementRows] = await Promise.all([
      apiGet("/inventory"),
      apiGet("/inventory/movements"),
    ]);
    setRows(inventoryRows);
    setMovements(movementRows);
  };

  useEffect(() => {
    load().catch(() => {
      setRows([]);
      setMovements([]);
    });
  }, []);

  const adjust = async (event: FormEvent) => {
    event.preventDefault();
    setMessage("");
    try {
      await apiPost("/inventory/adjust", {
        product_id: Number(productId),
        quantity: Number(quantity),
        adjust_type: adjustType,
        note: "Ajuste manual desde panel",
      });
      setMessage("Inventario actualizado.");
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo ajustar");
    }
  };

  return (
    <ProtectedShell title="Inventario" subtitle="Control de existencias y ajustes">
      <form className="inline-actions" onSubmit={adjust}>
        <select
          value={productId}
          onChange={(e) => setProductId(e.target.value)}
          required
        >
          <option value="">Producto</option>
          {rows.map((row) => (
            <option key={row.product_id} value={row.product_id}>
              {row.sku} - {row.name}
            </option>
          ))}
        </select>
        <input
          type="number"
          min="1"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          required
        />
        <select value={adjustType} onChange={(e) => setAdjustType(e.target.value)}>
          <option value="entry">Entrada</option>
          <option value="exit">Salida</option>
        </select>
        <button type="submit">Ajustar stock</button>
      </form>
      {message ? <p className="muted">{message}</p> : null}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>SKU</th>
              <th>Nombre</th>
              <th>Tipo</th>
              <th>Marca</th>
              <th>Modelo</th>
              <th>Precio mayor</th>
              <th>Precio detal</th>
              <th>Moneda</th>
              <th>Stock</th>
              <th>Estado</th>
              <th>Fecha creacion</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.product_id}>
                <td>{row.sku}</td>
                <td>{row.name}</td>
                <td>{row.product_type || "-"}</td>
                <td>{row.brand || "-"}</td>
                <td>{row.model || "-"}</td>
                <td>
                  <span className="price-wholesale">{Number(row.wholesale_price ?? 0).toFixed(2)}</span>
                </td>
                <td>
                  <span className="price-retail">{Number(row.retail_price ?? 0).toFixed(2)}</span>
                </td>
                <td>{row.currency_code || "-"}</td>
                <td>{row.stock}</td>
                <td className={row.status === "BAJO" ? "badge-warn" : "badge-ok"}>{row.status}</td>
                <td>{new Date(row.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button type="button" className="header-btn" onClick={() => setShowMovements((prev) => !prev)}>
        {showMovements ? "Ocultar ultimos movimientos" : "Mostrar ultimos movimientos"}
      </button>
      {showMovements ? (
        <div>
          <h3>Ultimos movimientos</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Producto ID</th>
                  <th>Tipo</th>
                  <th>Cantidad</th>
                  <th>Usuario</th>
                  <th>Nota</th>
                </tr>
              </thead>
              <tbody>
                {movements.map((movement) => (
                  <tr key={movement.id}>
                    <td>{new Date(movement.created_at).toLocaleString()}</td>
                    <td>{movement.product_id}</td>
                    <td>{movement.movement_type === "adjustment_in" ? "Entrada" : "Salida"}</td>
                    <td>{movement.quantity}</td>
                    <td>{movement.created_by}</td>
                    <td>{movement.note || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </ProtectedShell>
  );
}
