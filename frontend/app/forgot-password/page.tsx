"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";

import { apiPost } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    try {
      const response = await apiPost("/auth/forgot-password", { email });
      setMessage(response.message ?? "Si existe la cuenta, se enviaron instrucciones.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo procesar la solicitud");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="login-wrapper">
      <section className="login-card">
        <h1>Recuperar contrasena</h1>
        <p>Ingresa tu correo y enviaremos un enlace por Telegram.</p>
        <form className="login-form" onSubmit={submit}>
          <label>
            Correo
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <button type="submit" disabled={loading}>
            {loading ? "Enviando..." : "Enviar enlace"}
          </button>
        </form>
        {message ? <p className="muted">{message}</p> : null}
        <p className="muted" style={{ marginTop: 12 }}>
          <Link href="/login">Volver a login</Link>
        </p>
      </section>
    </main>
  );
}
