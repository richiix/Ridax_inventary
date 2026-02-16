"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { apiPost } from "@/lib/api";
import { setToken } from "@/lib/session";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@ridax.local");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const response = await apiPost("/auth/login", { email, password });
      setToken(response.access_token);
      router.push("/panel");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar sesion");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="login-wrapper">
      <section className="login-card">
        <h1>RIDAX Platform</h1>
        <p>Panel operativo con control por rol, inventario y ventas en tiempo real.</p>
        <form className="login-form" onSubmit={submit}>
          <label>
            Correo
            <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
          </label>
          <label>
            Contrasena
            <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" required />
          </label>
          {error ? <p className="error-message">{error}</p> : null}
          <button type="submit" disabled={loading}>
            {loading ? "Ingresando..." : "Ingresar"}
          </button>
        </form>

        <p className="muted" style={{ marginTop: 12 }}>
          <Link href="/forgot-password">Olvide mi contrasena</Link>
        </p>
      </section>
    </main>
  );
}
