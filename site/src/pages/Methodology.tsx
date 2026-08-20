import type { PageProps } from "../App";
import styles from "./Content.module.css";

export function Methodology({ manifest }: PageProps) {
  return (
    <div className={`page ${styles.root}`}>
      <p className="eyebrow">Methodology</p>
      <h1>How a price wedge is estimated</h1>
      <p className="lede">
        A short guide to what the numbers on this site are, in the order the paper builds
        them. The full derivations are in the article.
      </p>

      <div className="prose">
        <h2>The object</h2>
        <p>
          The price wedge of a security is the log deviation of its market value from its
          informationally efficient value — the price that would prevail if cash flows were
          discounted with the correct stochastic discount factor. A wedge of −0.20 means the
          security is about 20% underpriced; +0.20 means about 20% overpriced.
        </p>
        <p>
          Unlike an alpha, a price wedge is a statement about the <em>level</em> of prices
          rather than the direction of returns. The paper's central finding is that the two
          need not agree: roughly a third of well-known return anomalies push prices further
          from fundamental value rather than correcting an existing gap.
        </p>

        <h2>What else this is called</h2>
        <p>
          The same object goes by different names depending on which literature you come
          from. A price wedge is a <em>price dislocation</em>, a <em>mispricing</em>, a{" "}
          <em>pricing error</em>, a <em>valuation gap</em>, or the deviation of price from{" "}
          <em>fundamental</em> or <em>intrinsic value</em>. A positive wedge means the stock
          is overpriced — overvalued relative to what its own cash flows justify. A negative
          wedge means it is underpriced, or undervalued. Sorting firms by their wedge at a
          given date ranks them from the most overpriced to the most underpriced stocks in
          the cross-section.
        </p>
        <p>
          What distinguishes these estimates from a valuation model is that nothing here is
          forecast from fundamentals. The wedge is identified from realised post-formation
          cash flows discounted at a stochastic discount factor calibrated so that the
          aggregate market is priced correctly by construction.
        </p>

        <h2>Step 1 — portfolio wedges</h2>
        <p>
          Stocks are sorted into deciles on each of 57 characteristics, and each decile
          portfolio is held for fifteen years. The wedge is the negative log of the expected
          present value of that portfolio's dividends plus its terminal value, per dollar of
          price at formation, discounted with an exponentially affine CAPM stochastic
          discount factor whose price of risk is set so that the aggregate market has a wedge
          of exactly zero. Two bias adjustments correct the estimated mean excess return at
          long horizons.
        </p>

        <h2>Step 2 — from portfolios to firms</h2>
        <p>
          Portfolio wedges are then projected on rank-normalised portfolio characteristics.
          Evaluating that mapping at an individual firm's own characteristic percentiles
          gives a firm-level wedge that moves month by month, because the firm's
          characteristics do. This is what the explorer plots.
        </p>

        <h2>The eight specifications</h2>
        <p>Three binary choices, each of which the explorer exposes as a toggle.</p>

        <h3>Mapping: three principal components, or FF5 + momentum</h3>
        <p>{manifest?.firm.mappingNotes.pc3}</p>
        <p>{manifest?.firm.mappingNotes.ff5}</p>

        <h3>Level: equity, or firm value</h3>
        <p>{manifest?.firm.levelNotes.equity}</p>
        <p>{manifest?.firm.levelNotes.firm}</p>

        <h3>Sample: full, or out of sample</h3>
        <p>{manifest?.firm.sampleNotes.full}</p>
        <p>{manifest?.firm.sampleNotes.oos}</p>

        <h2>Reading the charts</h2>
        <ul>
          <li>
            <strong>One security</strong> is drawn as a filled area against zero, because a
            lone wedge is fundamentally a signed quantity: red above the line is overpriced,
            blue below is underpriced.
          </li>
          <li>
            <strong>Two or more</strong> are drawn as plain lines in a fixed colour order.
            Each security keeps its colour for as long as it is on the chart, so removing one
            never repaints the others.
          </li>
          <li>
            Shaded vertical bands are NBER recessions.
          </li>
        </ul>

        <h2>Timing</h2>
        <p>{manifest?.firm.timing}</p>

        <h2>What this site does not do</h2>
        <ul>
          <li>
            It does not estimate anything. Every number is precomputed from the replication
            package and served as a static file.
          </li>
          <li>
            It does not give portfolio wedges as calendar time series. A portfolio wedge needs
            fifteen years of post-formation cash flows, so it is a property of a formation
            cohort rather than of a month. Portfolio estimates are available on the{" "}
            <a href="/data">data page</a> as point estimates and by horizon after formation.
          </li>
          <li>
            It does not carry CRSP company names or tickers, which are licensed.
          </li>
        </ul>
      </div>
    </div>
  );
}
