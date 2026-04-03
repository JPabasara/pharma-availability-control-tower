"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { 
  Activity, 
  BarChart3, 
  ClipboardList, 
  Clock, 
  Database, 
  FileText, 
  LayoutDashboard, 
  Menu,
  Moon, 
  Sun,
  Truck,
  X
} from "lucide-react";

import { buildQueryString } from "@/lib/format";
import { usePlannerRunContext } from "@/lib/run-context";
import { useTheme } from "@/lib/theme-context";

import { AlertCircle } from "lucide-react";

type NavItem = {
  href: string;
  label: string;
  icon: any;
  useRunContext?: boolean;
};

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/inputs", label: "Inputs", icon: Database },
  { href: "/priorities", label: "M1 Priorities", useRunContext: true, icon: AlertCircle },
  { href: "/requests", label: "M2 Requests", useRunContext: true, icon: ClipboardList },
  { href: "/dispatch", label: "M3 Dispatch", useRunContext: true, icon: Truck },
  { href: "/history", label: "History", icon: Clock },
  { href: "/demo-state", label: "Demo Operations", icon: Activity },
  { href: "/reports", label: "Reports", icon: FileText },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { runContext } = usePlannerRunContext();
  const { theme, toggleTheme } = useTheme();
  
  const [time, setTime] = useState("");
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    setTime(new Date().toLocaleTimeString());
    const timer = setInterval(() => {
      setTime(new Date().toLocaleTimeString());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Close mobile menu when route changes
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [pathname]);

  return (
    <div className="shell">
      {/* Mobile backdrop overlay */}
      <div
        className={`sidebar-overlay${isMobileMenuOpen ? " active" : ""}`}
        onClick={() => setIsMobileMenuOpen(false)}
        aria-hidden="true"
      />

      <aside className={`sidebar${isMobileMenuOpen ? " open" : ""}`}>
        <div className="sidebar-brand">
          <div className="brand-icon">
            <Activity size={20} />
          </div>
          <div className="brand-text-wrapper">
            <span className="sidebar-eyebrow">Planner Console</span>
            <h1>Pharma Tower</h1>
          </div>
          {/* Close button — visible only on mobile */}
          <button
            className="mobile-close"
            onClick={() => setIsMobileMenuOpen(false)}
            aria-label="Close navigation"
          >
            <X size={20} />
          </button>
        </div>

        <div className="nav-section-title">Menu</div>
        <nav className="nav-list" aria-label="Primary navigation">
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href;
            const href = item.useRunContext
              ? `${item.href}${buildQueryString(runContext)}`
              : item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={href}
                className={`nav-link${active ? " nav-link-active" : ""}`}
              >
                <Icon size={18} />
                <span className="nav-link-label">{item.label}</span>
                {item.useRunContext && runContext?.m3RunId ? (
                  <span className="nav-link-meta">M3 Linked</span>
                ) : null}
              </Link>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <Database size={14} className="subtle-text" />
          <span>API: {process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"}</span>
        </div>
      </aside>

      <div className="main-wrapper">
        <header className="top-header">
          {/* Hamburger — visible only on mobile */}
          <button
            className="mobile-toggle"
            onClick={() => setIsMobileMenuOpen(true)}
            aria-label="Open navigation menu"
          >
            <Menu size={22} />
          </button>

          <div className="live-clock">
            <Clock size={16} />
            {time || "--:--:--"}
          </div>
          <div className="live-indicator">
            <span className="live-dot" />
            SYSTEM ONLINE
          </div>
          <button 
            className="theme-toggle" 
            onClick={toggleTheme}
            aria-label="Toggle theme"
          >
            {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </header>

        <main className="content">{children}</main>
      </div>
    </div>
  );
}
