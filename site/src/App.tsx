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
