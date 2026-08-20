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

/** The mark is the object itself: two paths leaving a common point — the market
 *  price and the efficient value — with the widening gap between them filled.
 *  That gap is the price wedge. */
function Wordmark() {
  return (
    <>
      <svg width="30" height="24" viewBox="0 0 30 24" aria-hidden="true" className={styles.mark}>
        <path
          d="M3.6 19.4 C 11 19 17 15.5 26.4 5.6 L26.4 15.6 C 17 18.2 11 19.1 3.6 19.4 Z"
          className={styles.markFill}
        />
        <path
          d="M3.6 19.4 C 11 19 17 15.5 26.4 5.6"
          fill="none"
          stroke="var(--pole-over)"
          strokeWidth="2.1"
          strokeLinecap="round"
        />
        <path
          d="M3.6 19.4 C 11 19.1 17 18.2 26.4 15.6"
          fill="none"
          stroke="var(--pole-under)"
          strokeWidth="2.1"
          strokeLinecap="round"
        />
        <circle cx="3.6" cy="19.4" r="1.7" className={styles.markPivot} />
      </svg>
      <span className={styles.brandText}>
        Price<span className={styles.brandAccent}>Wedge</span>
      </span>
    </>
  );
}
