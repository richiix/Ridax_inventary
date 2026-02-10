"use client";

import { FormEvent, Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

import { apiPost } from "@/lib/api";

function ResetPasswordContent() {
  const search = useSearchParams();
  const token = useMemo(() => search.get("token") ?? "", [search]);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setMessage("");
    if (!token) {
      setMessage("Token invalido o faltante");
      return;
    }
    if (password !== confirmPassword) {
      setMessage("Las contrasenas no coinciden");
      return;
    }

    setLoading(true);
    try {
      const response = await apiPost("/auth/reset-password", {
        token,
        new_password: password,
      });
      setMessage(response.message ?? "Contrasena actualizada");
      setPassword("");
      setConfirmPassword("");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo restablecer la contrasena");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="login-wrapper">
      <section className="login-card">
        <h1>Restablecer contrasena</h1>
        <p>Define tu nueva contrasena para acceder a RIDAX.</p>
        <form className="login-form" onSubmit={submit}>
          <label>
            Nueva contrasena
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>
          <label>
            Confirmar contrasena
            <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required />
          </label>
          <button type="submit" disabled={loading}>
            {loading ? "Guardando..." : "Guardar nueva contrasena"}
          </button>
        </form>
        {message ? <p className="muted">{message}</p> : null}
        <p className="muted" style={{ marginTop: 12 }}>
          <Link href="/login">Ir a login</Link>
        </p>
      </section>
    </main>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<main className="loading-screen">Cargando...</main>}>
      <ResetPasswordContent />
    </Suspense>
  );
}
