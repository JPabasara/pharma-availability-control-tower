"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { buildQueryString } from "@/lib/format";
import { usePlannerRunContext } from "@/lib/run-context";

const NAV_ITEMS: Array<{
  href: string;
  label: string;
  useRunContext?: boolean;
}> = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/inputs", label: "Inputs" },
  { href: "/priorities", label: "M1 Priorities", useRunContext: true },
  { href: "/requests", label: "M2 Requests", useRunContext: true },
  { href: "/dispatch", label: "M3 Dispatch", useRunContext: true },
  { href: "/history", label: "History" },
  { href: "/demo-state", label: "Demo State" },
  { href: "/reports", label: "Reports" },
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { runContext } = usePlannerRunContext();

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="sidebar-eyebrow">Planner Console</span>
          <h1>Pharma Control Tower</h1>
          <p>On-demand dispatch planning with demo-state visibility.</p>
        </div>

        <nav className="nav-list" aria-label="Primary navigation">
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href;
            const href = item.useRunContext
              ? `${item.href}${buildQueryString(runContext)}`
              : item.href;
            return (
              <Link
                key={item.href}
                href={href}
                className={`nav-link${active ? " nav-link-active" : ""}`}
              >
                <span className="nav-link-label">{item.label}</span>
                {item.useRunContext && runContext?.m3RunId ? (
                  <span className="nav-link-meta">Linked to latest run</span>
                ) : null}
              </Link>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-chip">
            FastAPI at {process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"}
          </div>
          <p className="sidebar-note">
            Arrival simulation stays CLI-driven. This console visualizes the resulting
            state.
          </p>
        </div>
      </aside>

      <main className="content">{children}</main>
    </div>
  );
}
