import { useEffect, useState } from "react";
import { Layout } from "./components/Layout";
import { Explorer } from "./pages/Explorer";
import { DataPage } from "./pages/DataPage";
import { Methodology } from "./pages/Methodology";
import { About } from "./pages/About";
import type { Manifest } from "./lib/types";
import { loadManifest } from "./lib/store";

const ROUTES = {
  "/": Explorer,
  "/data": DataPage,
  "/methodology": Methodology,
  "/about": About,
} as const;

/** Client-side routes need their own titles and canonicals; a single-page app
 *  otherwise reports every page as the home page to search engines and to
 *  anything that unfurls a link. The canonical always names the apex, since
 *  www.pricewedge.com serves the same content. */
const META: Record<keyof typeof ROUTES, { title: string; description: string }> = {
  "/": {
    title: "Price Wedges — stock mispricing estimates for US equities",
    description:
      "How overpriced or underpriced is a stock? Explore the price wedge of any of 19,476 US stocks, 1964–2017: the gap between market value and informationally efficient value.",
  },
  "/data": {
    title: "Download stock mispricing data — PriceWedge",
    description:
      "Firm-level and portfolio-level price wedge estimates for US stocks as Parquet and CSV, versioned by vintage with permanent URLs.",
  },
  "/methodology": {
    title: "How stock mispricing is estimated — PriceWedge",
    description:
      "How price wedges — price dislocations, pricing errors, valuation gaps — are estimated from fifteen years of post-formation cash flows and mapped to individual firms.",
  },
  "/about": {
    title: "About — PriceWedge",
    description:
      "Price wedge estimates from Binsbergen, Boons, Opp and Tamoni, Journal of Financial Economics.",
  },
};

const SITE = "https://pricewedge.com";

function applyMeta(route: keyof typeof ROUTES) {
  const meta = META[route];
  document.title = meta.title;

  const set = (selector: string, attr: string, value: string) => {
    const el = document.head.querySelector(selector);
    if (el) el.setAttribute(attr, value);
  };
  set('link[rel="canonical"]', "href", `${SITE}${route === "/" ? "/" : route}`);
  set('meta[name="description"]', "content", meta.description);
  set('meta[property="og:url"]', "content", `${SITE}${route === "/" ? "/" : route}`);
}

export type Route = keyof typeof ROUTES;

function currentRoute(): Route {
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  return (path in ROUTES ? path : "/") as Route;
}

export function App() {
  const [route, setRoute] = useState<Route>(currentRoute);
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    applyMeta(route);
  }, [route]);

  useEffect(() => {
    const onPop = () => setRoute(currentRoute());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  useEffect(() => {
    loadManifest().then(setManifest, (e: Error) => setError(e.message));
  }, []);

  const navigate = (to: Route) => {
    if (to === route) return;
    window.history.pushState({}, "", to);
    setRoute(to);
    window.scrollTo({ top: 0 });
  };

  const Page = ROUTES[route];

  return (
    <Layout route={route} navigate={navigate} manifest={manifest}>
      {error ? (
        <div className="page" style={{ padding: "4rem 0" }}>
          <h1>Estimates unavailable</h1>
          <p className="lede">{error}</p>
          <p>
            The site could not read its data directory. If you are running it locally, build
            the estimates first with <code>python pipeline/build.py</code>.
          </p>
        </div>
      ) : (
        <Page manifest={manifest} navigate={navigate} />
      )}
    </Layout>
  );
}

export interface PageProps {
  manifest: Manifest | null;
  navigate: (to: Route) => void;
}
