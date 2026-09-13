"""Fama and French's 48-industry classification.

Four of the 57 characteristics are industry-adjusted: a firm's value minus the
mean among firms in its industry that month. The industries are the 48 of Fama
and French (1997), defined as ranges of SIC codes.

The table below is generated from Ken French's own , so the
ranges are his rather than a transcription. Ranges are laid down in
order so an earlier industry keeps a code a later range would also claim.
Industry 48 has ranges of its own and is also the residual: a SIC code matching
nothing lands there, which is a little over half the 0-9999 space.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# (industry number, short name, [(low, high), ...])
FF48: list[tuple[int, str, list[tuple[int, int]]]] = [
    (1, "Agric", [(100, 199), (200, 299), (700, 799), (910, 919), (2048, 2048)]),
    (2, "Food", [(2000, 2009), (2010, 2019), (2020, 2029), (2030, 2039), (2040, 2046),
                 (2050, 2059), (2060, 2063), (2070, 2079), (2090, 2092),
                 (2095, 2095), (2098, 2099)]),
    (3, "Soda", [(2064, 2068), (2086, 2086), (2087, 2087), (2096, 2096), (2097, 2097)]),
    (4, "Beer", [(2080, 2080), (2082, 2082), (2083, 2083), (2084, 2084), (2085, 2085)]),
    (5, "Smoke", [(2100, 2199)]),
    (6, "Toys", [(920, 999), (3650, 3651), (3652, 3652), (3732, 3732), (3930, 3931), (3940,
                 3949)]),
    (7, "Fun", [(7800, 7829), (7830, 7833), (7840, 7841), (7900, 7900), (7910, 7911),
                 (7920, 7929), (7930, 7933), (7940, 7949), (7980, 7980),
                 (7990, 7999)]),
    (8, "Books", [(2700, 2709), (2710, 2719), (2720, 2729), (2730, 2739), (2740, 2749),
                 (2770, 2771), (2780, 2789), (2790, 2799)]),
    (9, "Hshld", [(2047, 2047), (2391, 2392), (2510, 2519), (2590, 2599), (2840, 2843),
                 (2844, 2844), (3160, 3161), (3170, 3171), (3172, 3172),
                 (3190, 3199), (3229, 3229), (3260, 3260), (3262, 3263),
                 (3269, 3269), (3230, 3231), (3630, 3639), (3750, 3751),
                 (3800, 3800), (3860, 3861), (3870, 3873), (3910, 3911),
                 (3914, 3914), (3915, 3915), (3960, 3962), (3991, 3991),
                 (3995, 3995)]),
    (10, "Clths", [(2300, 2390), (3020, 3021), (3100, 3111), (3130, 3131), (3140, 3149),
                 (3150, 3151), (3963, 3965)]),
    (11, "Hlth", [(8000, 8099)]),
    (12, "MedEq", [(3693, 3693), (3840, 3849), (3850, 3851)]),
    (13, "Drugs", [(2830, 2830), (2831, 2831), (2833, 2833), (2834, 2834), (2835, 2835),
                 (2836, 2836)]),
    (14, "Chems", [(2800, 2809), (2810, 2819), (2820, 2829), (2850, 2859), (2860, 2869),
                 (2870, 2879), (2890, 2899)]),
    (15, "Rubbr", [(3031, 3031), (3041, 3041), (3050, 3053), (3060, 3069), (3070, 3079),
                 (3080, 3089), (3090, 3099)]),
    (16, "Txtls", [(2200, 2269), (2270, 2279), (2280, 2284), (2290, 2295), (2297, 2297),
                 (2298, 2298), (2299, 2299), (2393, 2395), (2397, 2399)]),
    (17, "BldMt", [(800, 899), (2400, 2439), (2450, 2459), (2490, 2499), (2660, 2661), (2950,
                 2952), (3200, 3200), (3210, 3211), (3240, 3241), (3250,
                 3259), (3261, 3261), (3264, 3264), (3270, 3275), (3280,
                 3281), (3290, 3293), (3295, 3299), (3420, 3429), (3430,
                 3433), (3440, 3441), (3442, 3442), (3446, 3446), (3448,
                 3448), (3449, 3449), (3450, 3451), (3452, 3452), (3490,
                 3499), (3996, 3996)]),
    (18, "Cnstr", [(1500, 1511), (1520, 1529), (1530, 1539), (1540, 1549), (1600, 1699),
                 (1700, 1799)]),
    (19, "Steel", [(3300, 3300), (3310, 3317), (3320, 3325), (3330, 3339), (3340, 3341),
                 (3350, 3357), (3360, 3369), (3370, 3379), (3390, 3399)]),
    (20, "FabPr", [(3400, 3400), (3443, 3443), (3444, 3444), (3460, 3469), (3470, 3479)]),
    (21, "Mach", [(3510, 3519), (3520, 3529), (3530, 3530), (3531, 3531), (3532, 3532),
                 (3533, 3533), (3534, 3534), (3535, 3535), (3536, 3536),
                 (3538, 3538), (3540, 3549), (3550, 3559), (3560, 3569),
                 (3580, 3580), (3581, 3581), (3582, 3582), (3585, 3585),
                 (3586, 3586), (3589, 3589), (3590, 3599)]),
    (22, "ElcEq", [(3600, 3600), (3610, 3613), (3620, 3621), (3623, 3629), (3640, 3644),
                 (3645, 3645), (3646, 3646), (3648, 3649), (3660, 3660),
                 (3690, 3690), (3691, 3692), (3699, 3699)]),
    (23, "Autos", [(2296, 2296), (2396, 2396), (3010, 3011), (3537, 3537), (3647, 3647),
                 (3694, 3694), (3700, 3700), (3710, 3710), (3711, 3711),
                 (3713, 3713), (3714, 3714), (3715, 3715), (3716, 3716),
                 (3792, 3792), (3790, 3791), (3799, 3799)]),
    (24, "Aero", [(3720, 3720), (3721, 3721), (3723, 3724), (3725, 3725), (3728, 3729)]),
    (25, "Ships", [(3730, 3731), (3740, 3743)]),
    (26, "Guns", [(3760, 3769), (3795, 3795), (3480, 3489)]),
    (27, "Gold", [(1040, 1049)]),
    (28, "Mines", [(1000, 1009), (1010, 1019), (1020, 1029), (1030, 1039), (1050, 1059),
                 (1060, 1069), (1070, 1079), (1080, 1089), (1090, 1099),
                 (1100, 1119), (1400, 1499)]),
    (29, "Coal", [(1200, 1299)]),
    (30, "Oil", [(1300, 1300), (1310, 1319), (1320, 1329), (1330, 1339), (1370, 1379),
                 (1380, 1380), (1381, 1381), (1382, 1382), (1389, 1389),
                 (2900, 2912), (2990, 2999)]),
    (31, "Util", [(4900, 4900), (4910, 4911), (4920, 4922), (4923, 4923), (4924, 4925),
                 (4930, 4931), (4932, 4932), (4939, 4939), (4940, 4942)]),
    (32, "Telcm", [(4800, 4800), (4810, 4813), (4820, 4822), (4830, 4839), (4840, 4841),
                 (4880, 4889), (4890, 4890), (4891, 4891), (4892, 4892),
                 (4899, 4899)]),
    (33, "PerSv", [(7020, 7021), (7030, 7033), (7200, 7200), (7210, 7212), (7214, 7214),
                 (7215, 7216), (7217, 7217), (7219, 7219), (7220, 7221),
                 (7230, 7231), (7240, 7241), (7250, 7251), (7260, 7269),
                 (7270, 7290), (7291, 7291), (7292, 7299), (7395, 7395),
                 (7500, 7500), (7520, 7529), (7530, 7539), (7540, 7549),
                 (7600, 7600), (7620, 7620), (7622, 7622), (7623, 7623),
                 (7629, 7629), (7630, 7631), (7640, 7641), (7690, 7699),
                 (8100, 8199), (8200, 8299), (8300, 8399), (8400, 8499),
                 (8600, 8699), (8800, 8899), (7510, 7515)]),
    (34, "BusSv", [(2750, 2759), (3993, 3993), (7218, 7218), (7300, 7300), (7310, 7319),
                 (7320, 7329), (7330, 7339), (7340, 7342), (7349, 7349),
                 (7350, 7351), (7352, 7352), (7353, 7353), (7359, 7359),
                 (7360, 7369), (7370, 7372), (7374, 7374), (7375, 7375),
                 (7376, 7376), (7377, 7377), (7378, 7378), (7379, 7379),
                 (7380, 7380), (7381, 7382), (7383, 7383), (7384, 7384),
                 (7385, 7385), (7389, 7390), (7391, 7391), (7392, 7392),
                 (7393, 7393), (7394, 7394), (7396, 7396), (7397, 7397),
                 (7399, 7399), (7519, 7519), (8700, 8700), (8710, 8713),
                 (8720, 8721), (8730, 8734), (8740, 8748), (8900, 8910),
                 (8911, 8911), (8920, 8999), (4220, 4229)]),
    (35, "Comps", [(3570, 3579), (3680, 3680), (3681, 3681), (3682, 3682), (3683, 3683),
                 (3684, 3684), (3685, 3685), (3686, 3686), (3687, 3687),
                 (3688, 3688), (3689, 3689), (3695, 3695), (7373, 7373)]),
    (36, "Chips", [(3622, 3622), (3661, 3661), (3662, 3662), (3663, 3663), (3664, 3664),
                 (3665, 3665), (3666, 3666), (3669, 3669), (3670, 3679),
                 (3810, 3810), (3812, 3812)]),
    (37, "LabEq", [(3811, 3811), (3820, 3820), (3821, 3821), (3822, 3822), (3823, 3823),
                 (3824, 3824), (3825, 3825), (3826, 3826), (3827, 3827),
                 (3829, 3829), (3830, 3839)]),
    (38, "Paper", [(2520, 2549), (2600, 2639), (2670, 2699), (2760, 2761), (3950, 3955)]),
    (39, "Boxes", [(2440, 2449), (2640, 2659), (3220, 3221), (3410, 3412)]),
    (40, "Trans", [(4000, 4013), (4040, 4049), (4100, 4100), (4110, 4119), (4120, 4121),
                 (4130, 4131), (4140, 4142), (4150, 4151), (4170, 4173),
                 (4190, 4199), (4200, 4200), (4210, 4219), (4230, 4231),
                 (4240, 4249), (4400, 4499), (4500, 4599), (4600, 4699),
                 (4700, 4700), (4710, 4712), (4720, 4729), (4730, 4739),
                 (4740, 4749), (4780, 4780), (4782, 4782), (4783, 4783),
                 (4784, 4784), (4785, 4785), (4789, 4789)]),
    (41, "Whlsl", [(5000, 5000), (5010, 5015), (5020, 5023), (5030, 5039), (5040, 5042),
                 (5043, 5043), (5044, 5044), (5045, 5045), (5046, 5046),
                 (5047, 5047), (5048, 5048), (5049, 5049), (5050, 5059),
                 (5060, 5060), (5063, 5063), (5064, 5064), (5065, 5065),
                 (5070, 5078), (5080, 5080), (5081, 5081), (5082, 5082),
                 (5083, 5083), (5084, 5084), (5085, 5085), (5086, 5087),
                 (5088, 5088), (5090, 5090), (5091, 5092), (5093, 5093),
                 (5094, 5094), (5099, 5099), (5100, 5100), (5110, 5113),
                 (5120, 5122), (5130, 5139), (5140, 5149), (5150, 5159),
                 (5160, 5169), (5170, 5172), (5180, 5182), (5190, 5199)]),
    (42, "Rtail", [(5200, 5200), (5210, 5219), (5220, 5229), (5230, 5231), (5250, 5251),
                 (5260, 5261), (5270, 5271), (5300, 5300), (5310, 5311),
                 (5320, 5320), (5330, 5331), (5334, 5334), (5340, 5349),
                 (5390, 5399), (5400, 5400), (5410, 5411), (5412, 5412),
                 (5420, 5429), (5430, 5439), (5440, 5449), (5450, 5459),
                 (5460, 5469), (5490, 5499), (5500, 5500), (5510, 5529),
                 (5530, 5539), (5540, 5549), (5550, 5559), (5560, 5569),
                 (5570, 5579), (5590, 5599), (5600, 5699), (5700, 5700),
                 (5710, 5719), (5720, 5722), (5730, 5733), (5734, 5734),
                 (5735, 5735), (5736, 5736), (5750, 5799), (5900, 5900),
                 (5910, 5912), (5920, 5929), (5930, 5932), (5940, 5940),
                 (5941, 5941), (5942, 5942), (5943, 5943), (5944, 5944),
                 (5945, 5945), (5946, 5946), (5947, 5947), (5948, 5948),
                 (5949, 5949), (5950, 5959), (5960, 5969), (5970, 5979),
                 (5980, 5989), (5990, 5990), (5992, 5992), (5993, 5993),
                 (5994, 5994), (5995, 5995), (5999, 5999)]),
    (43, "Meals", [(5800, 5819), (5820, 5829), (5890, 5899), (7000, 7000), (7010, 7019),
                 (7040, 7049), (7213, 7213)]),
    (44, "Banks", [(6000, 6000), (6010, 6019), (6020, 6020), (6021, 6021), (6022, 6022),
                 (6023, 6024), (6025, 6025), (6026, 6026), (6027, 6027),
                 (6028, 6029), (6030, 6036), (6040, 6059), (6060, 6062),
                 (6080, 6082), (6090, 6099), (6100, 6100), (6110, 6111),
                 (6112, 6113), (6120, 6129), (6130, 6139), (6140, 6149),
                 (6150, 6159), (6160, 6169), (6170, 6179), (6190, 6199)]),
    (45, "Insur", [(6300, 6300), (6310, 6319), (6320, 6329), (6330, 6331), (6350, 6351),
                 (6360, 6361), (6370, 6379), (6390, 6399), (6400, 6411)]),
    (46, "RlEst", [(6500, 6500), (6510, 6510), (6512, 6512), (6513, 6513), (6514, 6514),
                 (6515, 6515), (6517, 6519), (6520, 6529), (6530, 6531),
                 (6532, 6532), (6540, 6541), (6550, 6553), (6590, 6599),
                 (6610, 6611)]),
    (47, "Fin", [(6200, 6299), (6700, 6700), (6710, 6719), (6720, 6722), (6723, 6723),
                 (6724, 6724), (6725, 6725), (6726, 6726), (6730, 6733),
                 (6740, 6779), (6790, 6791), (6792, 6792), (6793, 6793),
                 (6794, 6794), (6795, 6795), (6798, 6798), (6799, 6799)]),
    (48, "Other", [(4950, 4959), (4960, 4961), (4970, 4971), (4990, 4991)]),
]

OTHER = 48


def _lookup_table() -> np.ndarray:
    """Industry number for every SIC code 0-9999, resolved once.

    Ranges are laid down in order so that an earlier industry keeps a code an
    overlapping later range would also claim, which is how the published
    definition is meant to be read.
    """
    table = np.full(10000, OTHER, dtype=np.int16)
    for number, _, ranges in reversed(FF48):
        for low, high in ranges:
            table[low : high + 1] = number
    return table


_TABLE = _lookup_table()
NAMES = {number: name for number, name, _ in FF48} | {OTHER: "Other"}


def ff48(siccd: pd.Series | np.ndarray) -> np.ndarray:
    """Map SIC codes to Fama-French industry numbers, 1-48."""
    codes = pd.to_numeric(pd.Series(np.asarray(siccd).ravel()), errors="coerce")
    out = np.full(len(codes), OTHER, dtype=np.int16)
    valid = codes.notna() & codes.between(0, 9999)
    out[valid.to_numpy()] = _TABLE[codes[valid].astype(int).to_numpy()]
    return out


def industry_adjust(frame: pd.DataFrame, column: str, industry: str = "ff48",
                    month: str = "month") -> pd.Series:
    """A characteristic less the mean among firms in the same industry that month.

    The mean is equal-weighted over the firms that have the characteristic, so a
    firm is compared against its industry as observed, not against a
    capitalisation-weighted aggregate that a few large firms would dominate.
    """
    group = frame.groupby([month, industry])[column]
    return frame[column] - group.transform("mean")


# ---------------------------------------------------------------------------
# Which SIC code
# ---------------------------------------------------------------------------
# The paper's industry adjustment uses CRSP's historical SIC code from the
# name-history file (`crsp.msenames`, one spell per name change): checked
# against the paper's own stored `siccd` panel it agrees for 99.5% of
# firm-months, where the `siccd` column on CRSP's newer monthly table -- which
# turns out to be constant over a security's life, effectively a header code --
# agrees for 63.9%. The difference reaches the adjusted signals directly: their
# industry means are formed over the wrong firms one time in three.

def historical_sic(monthly: pd.DataFrame, spells: pd.DataFrame) -> pd.Series:
    """The name-history SIC in force for each (permno, month), by spell dates.

    `spells` has columns permno, start, end, siccd (as pulled from
    crsp.msenames). A month is assigned the spell containing its last calendar
    day; where none does, the value is missing and the caller falls back.
    """
    s = spells.dropna(subset=["siccd"]).copy()
    s["permno"] = s["permno"].astype("int64")
    s["end"] = pd.to_datetime(s["end"]).fillna(pd.Timestamp("2099-12-31"))
    s["start"] = pd.to_datetime(s["start"])
    m = monthly[["permno", "month"]].drop_duplicates().copy()
    m["permno"] = m["permno"].astype("int64")
    m["date"] = pd.to_datetime(m["month"].astype(str) + "01") + pd.offsets.MonthEnd(0)
    j = m.merge(s, on="permno", how="left")
    j = j[(j["date"] >= j["start"]) & (j["date"] <= j["end"])]
    j = j.sort_values(["permno", "month", "start"]).drop_duplicates(["permno", "month"], keep="last")
    out = monthly[["permno", "month"]].merge(j[["permno", "month", "siccd"]],
                                            on=["permno", "month"], how="left")
    return out["siccd"].to_numpy()


# ---------------------------------------------------------------------------
# The paper's own industry scheme
# ---------------------------------------------------------------------------
# Appendix Table A.1 says Fama-French 48. The paper's adjusted panels say
# otherwise: within a month every firm in an industry cell shares the same
# value of BEME - aBEME, so grouping SIC codes by that value recovers the cells
# the paper actually used, with no naming needed. Done over 216 months, no SIC
# code ever straddles two cells, so the scheme is a pure function of the code.
# It has 27 industries: Fama-French 48 with most industries intact and the
# consumer-goods and heavy-manufacturing industries merged into two large
# groups. Under it, agreement with the published decile weights for aBEME,
# aSAT and aSIZE goes from 0.51 / 0.45 / 0.86 to 0.92 / 0.91 / 0.99.
#
# The table is stored as data, not code, because it was learned rather than
# transcribed: raw/their_industry_table.json maps each SIC code seen in the
# paper's panels to an industry number.

LEARNED_TABLE = Path(__file__).resolve().parents[2] / "raw" / "their_industry_table.json"
RESIDUAL_INDUSTRY = 27   # the 27 learned groups are 0..26


def learned_industry(siccd: pd.Series | np.ndarray) -> np.ndarray:
    """Industry number under the paper's own scheme; -1 for a missing code.

    Codes the paper's panels never contained are assigned by the scheme's own
    contiguity: it is built from SIC ranges, so a code between two mapped
    codes of the same industry belongs to it. A valid code outside every range
    (1.8% of firm-months) goes to one residual group, RESIDUAL_INDUSTRY, since
    the paper's panels carry an adjusted value for every firm that has the
    underlying one; dropping those firms instead scores marginally worse.
    """
    import json
    table = {int(k): v for k, v in json.load(open(LEARNED_TABLE))["sic_to_industry"].items()}
    known = np.array(sorted(table)); labels = np.array([table[k] for k in known])
    codes = pd.to_numeric(pd.Series(np.asarray(siccd).ravel()), errors="coerce")
    out = np.full(len(codes), -1, dtype=np.int16)
    ok = codes.notna().to_numpy()
    c = codes[ok].astype(int).to_numpy()
    lo = np.searchsorted(known, c, side="right") - 1
    hi = np.clip(lo + 1, 0, len(known) - 1); lo = np.clip(lo, 0, len(known) - 1)
    exact = known[lo] == c
    between = (~exact) & (labels[lo] == labels[hi]) & (c > known[lo]) & (c < known[hi])
    valid = (c >= 100) & (c <= 9999)      # 0 is CRSP's "no code"
    lab = np.where(exact, labels[lo],
                   np.where(between, labels[lo], np.where(valid, RESIDUAL_INDUSTRY, -1)))
    out[ok] = lab
    return out


def adjust_learned(panel: pd.DataFrame, pairs: dict[str, str], ordinary: pd.Series) -> None:
    """Industry-adjust each `pairs` value in place: the value less its
    equal-weighted mean over ordinary common shares in the same learned
    industry that month. Firms outside the ordinary universe, or without a
    usable SIC, get no adjusted value."""
    panel["industry"] = learned_industry(panel["siccd_hist"])
    for name, source in pairs.items():
        x = panel[source].where(ordinary & (panel["industry"] >= 0))
        group = x.groupby([panel["month"], panel["industry"]])
        panel[name] = x - group.transform("mean")
