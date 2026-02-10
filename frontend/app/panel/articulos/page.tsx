"use client";

import { FormEvent, useEffect, useState } from "react";

import { ProtectedShell } from "@/components/protected-shell";
import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from "@/lib/api";

type Product = {
  id: number;
  sku: string;
  name: string;
  product_type: string;
  brand: string;
  model: string;
  measure_quantity: number;
  measure_unit: string;
  description: string;
  invoice_note: string;
  cost_amount: number;
  base_price_amount: number;
  final_customer_price: number;
  wholesale_price: number;
  retail_price: number;
  currency_code: string;
  stock: number;
  is_active: boolean;
};

type ProductForm = {
  name: string;
  product_type: string;
  brand: string;
  model: string;
  measure_quantity: string;
  measure_unit: string;
  description: string;
  invoice_note: string;
  cost_amount: string;
  final_customer_price: string;
  wholesale_price: string;
  retail_price: string;
  currency_code: string;
  stock: string;
  is_active: boolean;
};

const DEFAULT_CURRENCIES = ["USD", "EUR", "VES"];

const emptyForm: ProductForm = {
  name: "",
  product_type: "",
  brand: "",
  model: "",
  measure_quantity: "1",
  measure_unit: "unidad",
  description: "",
  invoice_note: "",
  cost_amount: "0",
  final_customer_price: "0",
  wholesale_price: "0",
  retail_price: "0",
  currency_code: "USD",
  stock: "0",
  is_active: true,
};

export default function ArticulosPage() {
  const [items, setItems] = useState<Product[]>([]);
  const [message, setMessage] = useState("");
  const [form, setForm] = useState<ProductForm>(emptyForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [currencyOptions, setCurrencyOptions] = useState<string[]>(DEFAULT_CURRENCIES);

  const load = async () => {
    const [articleRows, currencyRows] = await Promise.all([apiGet("/articles"), apiGet("/settings/currencies")]);
    setItems(articleRows);
    const apiCurrencies = (currencyRows?.rates ?? []).map((row: { currency_code: string }) => row.currency_code);
    const merged = [...new Set([...DEFAULT_CURRENCIES, ...apiCurrencies])];
    setCurrencyOptions(merged);
  };

  useEffect(() => {
    load().catch(() => {
      setItems([]);
      setCurrencyOptions(DEFAULT_CURRENCIES);
    });
  }, []);

  const handleChange = (key: keyof ProductForm, value: string | boolean) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage("");
    const payload = {
      ...form,
      measure_quantity: Number(form.measure_quantity),
      cost_amount: Number(form.cost_amount),
      base_price_amount: Number(form.final_customer_price),
      final_customer_price: Number(form.final_customer_price),
      wholesale_price: Number(form.wholesale_price),
      retail_price: Number(form.retail_price),
      stock: Number(form.stock),
    };

    try {
      if (editingId) {
        await apiPut(`/articles/${editingId}`, { ...payload, change_reason: "Edicion desde panel" });
        setMessage("Articulo actualizado.");
      } else {
        const created = await apiPost("/articles", payload);
        setMessage(`Articulo creado con SKU ${created.sku}.`);
      }
      setEditingId(null);
      setForm(emptyForm);
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo guardar el articulo");
    }
  };

  const editItem = (item: Product) => {
    setEditingId(item.id);
    setForm({
      name: item.name,
      product_type: item.product_type,
      brand: item.brand,
      model: item.model,
      measure_quantity: String(item.measure_quantity),
      measure_unit: item.measure_unit,
      description: item.description,
      invoice_note: item.invoice_note,
      cost_amount: String(item.cost_amount),
      final_customer_price: String(item.final_customer_price),
      wholesale_price: String(item.wholesale_price),
      retail_price: String(item.retail_price),
      currency_code: item.currency_code,
      stock: String(item.stock),
      is_active: item.is_active,
    });
  };

  return (
    <ProtectedShell title="Articulos" subtitle="Catalogo comercial organizado por secciones">
      <div className="stat-item">
        <p>
          <strong>Guia rapida:</strong> Producto (nombre), Tipo (categoria), Marca, Modelo, Medida (cantidad + unidad), Costo, Precio final cliente, Precio mayor, Precio detal, Moneda, Stock, Nota factura y Observacion interna.
        </p>
      </div>

      <form className="article-form" onSubmit={submit}>
        <section className="article-form-section">
          <h3>Identificacion</h3>
          <div className="inline-actions">
            <label className="field-label">Producto
              <input placeholder="Nombre del producto" value={form.name} onChange={(e) => handleChange("name", e.target.value)} required />
            </label>
            <label className="field-label">Tipo
              <input placeholder="Categoria" value={form.product_type} onChange={(e) => handleChange("product_type", e.target.value)} />
            </label>
            <label className="field-label">Marca
              <input placeholder="Marca comercial" value={form.brand} onChange={(e) => handleChange("brand", e.target.value)} />
            </label>
            <label className="field-label">Modelo
              <input placeholder="Modelo o referencia" value={form.model} onChange={(e) => handleChange("model", e.target.value)} />
            </label>
            <label className="field-label">Cantidad medida
              <input type="number" step="0.01" placeholder="Ej. 1" value={form.measure_quantity} onChange={(e) => handleChange("measure_quantity", e.target.value)} />
            </label>
            <label className="field-label">Unidad medida
              <input placeholder="Ej. L, UN, ML" value={form.measure_unit} onChange={(e) => handleChange("measure_unit", e.target.value)} />
            </label>
          </div>
        </section>

        <section className="article-form-section">
          <h3>Informacion de ventas</h3>
          <div className="inline-actions">
            <label className="field-label">Costo
              <input type="number" step="0.01" placeholder="Costo de compra" value={form.cost_amount} onChange={(e) => handleChange("cost_amount", e.target.value)} />
            </label>
            <label className="field-label">Precio final cliente
              <input type="number" step="0.01" placeholder="Precio aplicado en venta" value={form.final_customer_price} onChange={(e) => handleChange("final_customer_price", e.target.value)} required />
            </label>
            <label className="field-label">Precio mayor
              <input type="number" step="0.01" placeholder="Precio mayorista" value={form.wholesale_price} onChange={(e) => handleChange("wholesale_price", e.target.value)} />
            </label>
            <label className="field-label">Precio detal
              <input type="number" step="0.01" placeholder="Precio detal" value={form.retail_price} onChange={(e) => handleChange("retail_price", e.target.value)} />
            </label>
            <label className="field-label">Moneda
              <select value={form.currency_code} onChange={(e) => handleChange("currency_code", e.target.value)}>
                {currencyOptions.map((currency) => (
                  <option key={currency} value={currency}>
                    {currency}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </section>

        <section className="article-form-section">
          <h3>Operacion</h3>
          <div className="inline-actions">
            <label className="field-label">Stock
              <input type="number" placeholder="Cantidad en almacen" value={form.stock} onChange={(e) => handleChange("stock", e.target.value)} />
            </label>
            <label className="field-label">Nota para factura
              <input placeholder="Texto visible en recibo" value={form.invoice_note} onChange={(e) => handleChange("invoice_note", e.target.value)} />
            </label>
            <label className="field-label">Observacion interna
              <input placeholder="Uso interno" value={form.description} onChange={(e) => handleChange("description", e.target.value)} />
            </label>
          </div>
        </section>

        <div className="inline-actions">
          <button type="submit">{editingId ? "Actualizar" : "Crear"}</button>
        </div>
      </form>

      {message ? <p className="muted">{message}</p> : null}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>SKU</th>
              <th>Producto</th>
              <th>Tipo/Marca/Modelo</th>
              <th>Medida</th>
              <th>Final</th>
              <th>Moneda</th>
              <th>Nota factura</th>
              <th>Stock</th>
              <th>Accion</th>
              <th>Catalogo</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td>{item.sku}</td>
                <td>{item.name}</td>
                <td>{`${item.product_type} / ${item.brand} / ${item.model}`}</td>
                <td>{`${item.measure_quantity} ${item.measure_unit}`}</td>
                <td>{item.final_customer_price.toFixed(2)}</td>
                <td>{item.currency_code}</td>
                <td>{item.invoice_note || "-"}</td>
                <td>{item.stock}</td>
                <td>
                  <button type="button" onClick={() => editItem(item)}>
                    Editar
                  </button>
                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        await apiPatch(`/articles/${item.id}/visibility?visible=${item.is_active ? "false" : "true"}`);
                        await load();
                      } catch (err) {
                        setMessage(err instanceof Error ? err.message : "No se pudo actualizar visible");
                      }
                    }}
                  >
                    Visible
                  </button>
                  <button
                    type="button"
                    onClick={async () => {
                      const confirmed = window.confirm(`Borrar logicamente ${item.name}?`);
                      if (!confirmed) {
                        return;
                      }
                      try {
                        await apiDelete(`/articles/${item.id}`);
                        await load();
                        setMessage("Articulo borrado logicamente.");
                      } catch (err) {
                        setMessage(err instanceof Error ? err.message : "No se pudo borrar articulo");
                      }
                    }}
                  >
                    Borrar
                  </button>
                </td>
                <td>{item.is_active ? "Visible" : "Oculto"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ProtectedShell>
  );
}
