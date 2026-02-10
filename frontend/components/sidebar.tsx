"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { clearToken } from "@/lib/session";

const links = [
  { href: "/panel", label: "Dashboard", permission: "dashboard:view", module: "dashboard" },
  { href: "/panel/articulos", label: "Articulos", permission: "articles:view", module: "articles" },
  { href: "/panel/inventario", label: "Inventario", permission: "inventory:view", module: "inventory" },
  { href: "/panel/ventas", label: "Ventas", permission: "sales:view", module: "sales" },
  { href: "/panel/compras", label: "Compras", permission: "purchases:view", module: "purchases" },
  { href: "/panel/informes", label: "Informes", permission: "reports:view", module: "reports" },
  { href: "/panel/configuracion", label: "Configuracion", permission: "settings:view", module: "settings" },
];

type SidebarProps = {
  permissions: string[];
  enabledModules: string[];
};

export function Sidebar({ permissions, enabledModules }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();

  const allowedLinks = links.filter(
    (link) => permissions.includes(link.permission) && enabledModules.includes(link.module),
  );

  const logout = () => {
    clearToken();
    router.push("/login");
  };

  return (
    <aside className="sidebar">
      <div className="brand-box">
        <p className="brand-label">RIDAX</p>
        <h1>Control Center</h1>
        <span>MVP v0.1</span>
      </div>

      <nav className="nav-links">
        {allowedLinks.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={pathname === link.href ? "active" : ""}
          >
            {link.label}
          </Link>
        ))}
      </nav>

      <button className="logout-btn" onClick={logout} type="button">
        Cerrar sesion
      </button>
    </aside>
  );
}
