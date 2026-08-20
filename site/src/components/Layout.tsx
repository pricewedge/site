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

// Apple's own estimated price wedge, sampled to eleven months and fitted to the
// icon box: red where the stock was overpriced, blue where underpriced. Eleven
// points is about the most that survives being drawn at 24px — a finer sample
// blurs into a single thick line at header size.
const WEDGE_ZERO = 13.98;
const WEDGE_PATH =
  "M2.60 5.94 L5.08 7.78 L7.56 7.46 L10.04 10.71 L12.52 20.00 L15.00 12.05 " +
  "L17.48 13.13 L19.96 6.60 L22.44 4.00 L24.92 4.63 L27.40 9.70";
const WEDGE_OVER =
  "M2.60 13.98 L2.60 5.94 L5.08 7.78 L7.56 7.46 L10.04 10.71 L12.52 13.98 " +
  "L15.00 12.05 L17.48 13.13 L19.96 6.60 L22.44 4.00 L24.92 4.63 L27.40 9.70 L27.40 13.98 Z";
const WEDGE_UNDER = "M10.04 13.98 L12.52 20.00 L15.00 13.98 Z";

/** The mark is a real measurement: Apple's estimated price wedge, overpriced
 *  above the line and underpriced below it. */
function Wordmark() {
  return (
    <>
      <svg width="30" height="24" viewBox="0 0 30 24" aria-hidden="true" className={styles.mark}>
        <path d={WEDGE_OVER} fill="var(--pole-over)" opacity="0.9" />
        <path d={WEDGE_UNDER} fill="var(--pole-under)" opacity="0.9" />
        <line
          x1="2.6"
          y1={WEDGE_ZERO}
          x2="27.4"
          y2={WEDGE_ZERO}
          stroke="var(--rule-strong)"
          strokeWidth="1.1"
        />
        <path
          d={WEDGE_PATH}
          fill="none"
          stroke="var(--text-primary)"
          strokeWidth="1.9"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </svg>
      <span className={styles.brandText}>
        Price<span className={styles.brandAccent}>Wedge</span>
      </span>
    </>
  );
}
