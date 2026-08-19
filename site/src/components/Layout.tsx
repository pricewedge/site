import { useEffect, useState, type ReactNode } from "react";
import type { Route } from "../App";
import type { Manifest } from "../lib/types";
import styles from "./Layout.module.css";

const NAV: { to: Route; label: string }[] = [
  { to: "/", label: "Explorer" },
  { to: "/data", label: "Data" },
  { to: "/methodology", label: "Methodology" },
  { to: "/about", label: "About" },
];

type Theme = "light" | "dark" | "system";

export function Layout({
  route,
  navigate,
  manifest,
  children,
}: {
  route: Route;
  navigate: (to: Route) => void;
  manifest: Manifest | null;
  children: ReactNode;
}) {
  const [theme, setTheme] = useState<Theme>(
    () => (localStorage.getItem("pw-theme") as Theme) ?? "system",
  );

  useEffect(() => {
    if (theme === "system") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("pw-theme", theme);
  }, [theme]);

  return (
    <>
      <a href="#main" className="visually-hidden">
        Skip to content
      </a>
      <header className={styles.header}>
        <div className={`page ${styles.headerInner}`}>
          <a
            href="/"
            className={styles.brand}
            onClick={(e) => {
              e.preventDefault();
              navigate("/");
            }}
          >
            <Wordmark />
          </a>
          <nav className={styles.nav} aria-label="Main">
            {NAV.map((item) => (
              <a
                key={item.to}
                href={item.to}
                aria-current={route === item.to ? "page" : undefined}
                className={styles.navLink}
                onClick={(e) => {
                  e.preventDefault();
                  navigate(item.to);
                }}
              >
                {item.label}
              </a>
            ))}
            <button
              type="button"
              className={styles.theme}
              onClick={() =>
                setTheme(theme === "light" ? "dark" : theme === "dark" ? "system" : "light")
              }
              aria-label={`Colour theme: ${theme}. Click to change.`}
              title={`Theme: ${theme}`}
            >
              {theme === "light" ? "☀" : theme === "dark" ? "☾" : "◐"}
            </button>
          </nav>
        </div>
      </header>

      <main id="main">{children}</main>

      <footer className={styles.footer}>
        <div className={`page ${styles.footerInner}`}>
          <div>
            <p className={styles.footerCite}>
              Jules H. van Binsbergen, Martijn Boons, Christian C. Opp and Andrea Tamoni,
              “Dynamic Asset (Mis)Pricing: Build-up versus Resolution Anomalies,”{" "}
              <em>Journal of Financial Economics</em>.
            </p>
            <p className={styles.footerMeta}>
              {manifest
                ? `Estimates vintage ${manifest.vintage} · data version ${manifest.dataVersion}`
                : " "}
            </p>
          </div>
          <nav className={styles.footerNav} aria-label="Footer">
            {NAV.map((item) => (
              <a
                key={item.to}
                href={item.to}
                onClick={(e) => {
                  e.preventDefault();
                  navigate(item.to);
                }}
              >
                {item.label}
              </a>
            ))}
          </nav>
        </div>
      </footer>
    </>
  );
}

/** A wedge: the gap between the observed price and the efficient one. */
function Wordmark() {
  return (
    <>
      <svg width="26" height="20" viewBox="0 0 26 20" aria-hidden="true" className={styles.mark}>
        <path d="M1 18 L25 4" fill="none" stroke="var(--pole-over)" strokeWidth="2.2" strokeLinecap="round" />
        <path d="M1 18 L25 16" fill="none" stroke="var(--pole-under)" strokeWidth="2.2" strokeLinecap="round" />
      </svg>
      <span className={styles.brandText}>
        Price<span className={styles.brandAccent}>Wedge</span>
      </span>
    </>
  );
}
