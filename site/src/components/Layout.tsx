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

// A sawtooth market price crossing a dashed fair value, with the gap between
// them filled. Eleven segments is about the most that survives being drawn at
// 24px — past that the zigzag turns to mush at header size.
const PRICE_PATH =
  "M2.6 20 L5.08 14.67 L7.56 18.22 L10.04 12.69 L12.52 15.85 L15 9.53 " +
  "L17.48 13.09 L19.96 6.77 L22.44 10.12 L24.92 4 L27.4 7.16";
const VALUE_PATH =
  "M2.6 19.01 L5.08 17.67 L7.56 16.33 L10.04 14.98 L12.52 13.64 L15 12.3 " +
  "L17.48 10.95 L19.96 9.61 L22.44 8.27 L24.92 6.92 L27.4 5.58";

/** The mark is the object itself: an irregular market price wandering around a
 *  smooth fair value, with the wedge between them shaded. */
function Wordmark() {
  return (
    <>
      <svg width="30" height="24" viewBox="0 0 30 24" aria-hidden="true" className={styles.mark}>
        <path d={`${PRICE_PATH} L27.4 5.58 ${VALUE_PATH.replace("M", "L")} Z`} className={styles.markFill} />
        <path
          d={VALUE_PATH}
          fill="none"
          stroke="var(--pole-under)"
          strokeWidth="1.6"
          strokeDasharray="2.4 1.8"
          strokeLinecap="round"
        />
        <path
          d={PRICE_PATH}
          fill="none"
          stroke="var(--pole-over)"
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
