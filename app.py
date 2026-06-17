"""
S.F. Medical Agency — Pharma Adjustment Calculator
====================================================
Calculates claim/adjustment for a pharma wholesaler based on
Effective Cost (EC) and Effective Selling Price (ESP).

Business Rule: Wholesaler must earn 10% margin on EFFECTIVE COST.
Adjustment is raised when Actual Selling Price < Required Selling Price.

v2: Fuzzy product name matching — auto-resolves minor typos/abbreviations
between Sales file and Cost file.
"""

import streamlit as st
import pandas as pd
import re
from difflib import get_close_matches

# ──────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="S.F. Medical Agency | Adjustment Calculator",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# CUSTOM CSS
# ──────────────────────────────────────────────
st.markdown("""
<style>
    :root {
        --bg:      #F0F4F8;
        --surface: #FFFFFF;
        --accent:  #1A5276;
        --accent2: #2E86C1;
        --danger:  #C0392B;
        --ok:      #1E8449;
        --text:    #1C2833;
        --muted:   #5D6D7E;
        --border:  #D5D8DC;
    }
    html, body, [data-testid="stAppViewContainer"] {
        background-color: var(--bg);
        font-family: 'Inter', 'Segoe UI', sans-serif;
        color: var(--text);
    }
    #MainMenu, footer, header { visibility: hidden; }

    [data-testid="stSidebar"] { background: var(--accent) !important; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    [data-testid="stSidebar"] p { color: #BDC3C7 !important; font-size: 0.82rem; }
    [data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.15) !important; }

    .app-header {
        background: linear-gradient(135deg, var(--accent) 0%, var(--accent2) 100%);
        border-radius: 12px;
        padding: 24px 32px;
        margin-bottom: 28px;
        display: flex;
        align-items: center;
        gap: 16px;
    }
    .app-header h1 { margin:0; font-size:1.55rem; font-weight:700; color:#FFF; }
    .app-header p  { margin:4px 0 0; color:rgba(255,255,255,0.75); font-size:0.85rem; }

    .card {
        background: var(--surface);
        border-radius: 10px;
        padding: 22px 26px;
        margin-bottom: 22px;
        border: 1px solid var(--border);
        box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    }
    .card-title {
        font-size: 0.78rem; font-weight: 700;
        text-transform: uppercase; letter-spacing: 1.2px;
        color: var(--muted); margin-bottom: 14px;
        padding-bottom: 10px; border-bottom: 1px solid var(--border);
    }

    .metric-row { display:flex; gap:14px; flex-wrap:wrap; margin-bottom:22px; }
    .metric-box {
        flex:1; min-width:150px;
        background:var(--surface); border:1px solid var(--border);
        border-radius:10px; padding:18px 20px; text-align:center;
    }
    .metric-box .label {
        font-size:0.72rem; font-weight:600; color:var(--muted);
        text-transform:uppercase; letter-spacing:0.9px; margin-bottom:6px;
    }
    .metric-box .value {
        font-size:1.55rem; font-weight:800;
        color:var(--accent); letter-spacing:-0.5px;
    }
    .metric-box.danger .value { color:var(--danger); }
    .metric-box.ok    .value  { color:var(--ok); }

    .step-row { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:20px; }
    .step-pill {
        background:#EBF5FB; border:1px solid #AED6F1;
        color:var(--accent2); padding:5px 14px;
        border-radius:20px; font-size:0.75rem; font-weight:600;
    }

    .fuzzy-table { width:100%; border-collapse:collapse; font-size:0.82rem; margin-top:8px; }
    .fuzzy-table th {
        background:#1A5276; color:#FFF;
        padding:8px 12px; text-align:left; font-size:0.73rem;
    }
    .fuzzy-table td { padding:7px 12px; border-bottom:1px solid #E8EDF2; }
    .fuzzy-table tr:nth-child(even) td { background:#F8FAFC; }
    .match-badge {
        display:inline-block; padding:2px 8px; border-radius:10px;
        font-size:0.7rem; font-weight:700;
        background:#D1E7DD; color:#0F5132;
    }
    .warn-badge {
        display:inline-block; padding:2px 8px; border-radius:10px;
        font-size:0.7rem; font-weight:700;
        background:#FFF3CD; color:#856404;
    }

    div[data-testid="metric-container"] {
        background:var(--surface); border:1px solid var(--border);
        border-radius:10px; padding:14px 18px;
    }
    .stDataFrame { border-radius:8px; overflow:hidden; }
    .stTabs [data-baseweb="tab-list"] { gap:6px; }
    .stTabs [data-baseweb="tab"] {
        border-radius:6px 6px 0 0; padding:8px 20px;
        font-size:0.82rem; font-weight:600;
    }
    .stTabs [aria-selected="true"] {
        background:var(--accent) !important; color:#FFF !important;
    }
    .stAlert { border-radius:8px; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════
# BUSINESS LOGIC FUNCTIONS
# ══════════════════════════════════════════════

def parse_deal(deal_str):
    """
    Parse purchase deal like '10+2' → (10, 2).
    Blank / invalid → (1, 0) = no deal.
    """
    if pd.isna(deal_str) or str(deal_str).strip() == "":
        return 1, 0
    deal_str = str(deal_str).strip()
    match = re.match(r"^(\d+)\+(\d+)$", deal_str)
    if match:
        pqty = int(match.group(1))
        fqty = int(match.group(2))
        return (pqty, fqty) if pqty > 0 else (1, 0)
    return 1, 0


def calculate_ec(purchase_price, purchase_qty, free_qty):
    """
    STEP 2 — Effective Cost.
    EC = (Purchase Price × PQty) / (PQty + FQty)
    """
    total = purchase_qty + free_qty
    return (purchase_price * purchase_qty) / total if total > 0 else purchase_price


def calculate_esp(selling_price, sale_qty, sale_free_qty):
    """
    STEP 3 — Effective Selling Price.
    NET sale  : ESP = Selling Price
    DEAL sale : ESP = (SP × Qty) / (Qty + FreeQty)
    """
    if sale_free_qty == 0 or sale_qty == 0:
        return selling_price
    return (selling_price * sale_qty) / (sale_qty + sale_free_qty)


def fuzzy_match_products(sales_names, cost_names, cutoff=0.75):
    """
    For each sales product name that does NOT exactly match a cost product name,
    attempt a fuzzy match using difflib.get_close_matches.

    Returns:
        name_map   : dict { sales_name → cost_name }  (only for fuzzy-matched ones)
        auto_fixed : list of dicts for display (sales_name, matched_cost_name, score)
        unmatched  : list of sales names that could not be matched at all
    """
    cost_set  = set(cost_names)
    sales_set = set(sales_names)

    exact_matches = sales_set & cost_set
    need_fuzzy    = sales_set - exact_matches

    name_map   = {}
    auto_fixed = []
    unmatched  = []

    for sname in sorted(need_fuzzy):
        matches = get_close_matches(sname, cost_names, n=1, cutoff=cutoff)
        if matches:
            best = matches[0]
            name_map[sname] = best
            # compute a rough similarity score for display
            from difflib import SequenceMatcher
            score = SequenceMatcher(None, sname, best).ratio()
            auto_fixed.append({
                "Sales File Name":      sname,
                "Matched Cost Name":    best,
                "Similarity":           f"{score:.0%}",
            })
        else:
            unmatched.append(sname)

    return name_map, auto_fixed, unmatched


def run_calculations(sales_df, cost_df):
    """
    Core engine:
      1. Normalise names
      2. Fuzzy-match products
      3. Apply remap, merge, calculate EC / ESP / Adj
    Returns: result_df, auto_fixed list, unmatched list
    """
    # ── Normalise columns & names ──────────────────────────────────────────
    sales_df.columns = [c.strip() for c in sales_df.columns]
    cost_df.columns  = [c.strip() for c in cost_df.columns]

    sales_df["Product Name"] = sales_df["Product Name"].astype(str).str.strip().str.upper()
    cost_df["Product Name"]  = cost_df["Product Name"].astype(str).str.strip().str.upper()

    # ── Safe numeric conversion ────────────────────────────────────────────
    sales_df["Quantity"]      = pd.to_numeric(sales_df["Quantity"],      errors="coerce").fillna(0)
    sales_df["Free Qty"]      = pd.to_numeric(sales_df["Free Qty"],      errors="coerce").fillna(0)
    sales_df["Selling Price"] = pd.to_numeric(sales_df["Selling Price"], errors="coerce").fillna(0)
    cost_df["Purchase Price"] = pd.to_numeric(cost_df["Purchase Price"], errors="coerce").fillna(0)

    if "Purchase Deal" not in cost_df.columns:
        cost_df["Purchase Deal"] = ""

    # ── Fuzzy match ────────────────────────────────────────────────────────
    cost_names = cost_df["Product Name"].tolist()
    name_map, auto_fixed, unmatched = fuzzy_match_products(
        sales_df["Product Name"].unique().tolist(),
        cost_names,
        cutoff=0.75,
    )

    # Apply remap: replace fuzzy-matched names in sales with the cost-file name
    sales_df["Product Name"] = sales_df["Product Name"].replace(name_map)

    # ── Merge ──────────────────────────────────────────────────────────────
    merged = sales_df.merge(cost_df, on="Product Name", how="left", indicator=True)
    merged.drop(columns=["_merge"], inplace=True)

    matched = merged[merged["Purchase Price"].notna()].copy()

    if matched.empty:
        return pd.DataFrame(), auto_fixed, unmatched

    # ── STEP 1+2: Parse deal → EC ──────────────────────────────────────────
    parsed = matched["Purchase Deal"].apply(parse_deal)
    matched["_pqty"] = parsed.apply(lambda x: x[0])
    matched["_fqty"] = parsed.apply(lambda x: x[1])

    matched["EC"] = matched.apply(
        lambda r: calculate_ec(r["Purchase Price"], r["_pqty"], r["_fqty"]), axis=1
    )

    # ── STEP 3: ESP ────────────────────────────────────────────────────────
    matched["ESP"] = matched.apply(
        lambda r: calculate_esp(r["Selling Price"], int(r["Quantity"]), r["Free Qty"]), axis=1
    )

    # ── STEP 4: Required SP ────────────────────────────────────────────────
    matched["Required SP"] = matched["EC"] * 1.10

    # ── STEP 5: Adjustment ─────────────────────────────────────────────────
    matched["Adj per Unit"]     = (matched["Required SP"] - matched["ESP"]).clip(lower=0)
    matched["Total Adjustment"] = matched["Adj per Unit"] * matched["Quantity"]

    # ── Output ─────────────────────────────────────────────────────────────
    result = matched[[
        "Party Name", "Product Name", "Quantity", "Free Qty",
        "Selling Price", "EC", "ESP", "Required SP",
        "Adj per Unit", "Total Adjustment",
    ]].copy()

    for col in ["EC", "ESP", "Required SP", "Adj per Unit", "Total Adjustment"]:
        result[col] = result[col].round(4)

    return result, auto_fixed, unmatched


# ══════════════════════════════════════════════
# DISPLAY HELPERS
# ══════════════════════════════════════════════

def style_result_table(df):
    currency_cols = ["Selling Price", "EC", "ESP", "Required SP", "Adj per Unit", "Total Adjustment"]

    def highlight(row):
        if row["Total Adjustment"] > 0:
            return ["background-color:#FEF9E7; font-weight:500;"] * len(row)
        return [""] * len(row)

    return (
        df.style
          .apply(highlight, axis=1)
          .format({c: "₹{:.4f}" for c in currency_cols if c in df.columns})
          .format({"Quantity": "{:.0f}", "Free Qty": "{:.0f}"})
    )


def metric_html(label, value, cls=""):
    return f"""
    <div class="metric-box {cls}">
        <div class="label">{label}</div>
        <div class="value">₹{value:,.2f}</div>
    </div>"""


def count_metric_html(label, value, color="var(--accent)"):
    return f"""
    <div class="metric-box">
        <div class="label">{label}</div>
        <div class="value" style="color:{color}">{value}</div>
    </div>"""


# ══════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════

with st.sidebar:
    st.markdown("## 💊 S.F. Medical Agency")
    st.markdown("**Pharma Adjustment Calculator**")
    st.markdown("---")

    st.markdown("### Upload Files")
    cost_file  = st.file_uploader("📋 Cost File (Excel)",  type=["xlsx", "xls"], key="cost")
    sales_file = st.file_uploader("📄 Sales File (Excel)", type=["xlsx", "xls"], key="sales")

    st.markdown("---")
    st.markdown("**Expected columns**")
    st.markdown("""
**Cost File:**
- Product Name
- Purchase Price
- Purchase Deal *(e.g. 10+2)*

**Sales File:**
- Party Name
- Product Name
- Quantity
- Free Qty
- Selling Price
""")
    st.markdown("---")
    st.markdown("**Formula Reference**")
    st.markdown("""
- **EC** = (Price × PQty) ÷ (PQty + FQty)
- **ESP** = (SP × Qty) ÷ (Qty + FreeQty)
- **Required SP** = EC × 1.10
- **Adj/unit** = max(Req SP − ESP, 0)
- **Total Adj** = Adj/unit × Qty
""")
    st.markdown("---")
    st.markdown("**v2 — Auto Fuzzy Match**")
    st.markdown("Minor name typos between files are auto-corrected at ≥75% similarity.")


# ══════════════════════════════════════════════
# MAIN CONTENT
# ══════════════════════════════════════════════

st.markdown("""
<div class="app-header">
    <div style="font-size:2.2rem">💊</div>
    <div>
        <h1>Pharma Adjustment Calculator</h1>
        <p>S.F. Medical Agency &nbsp;·&nbsp; 10% margin on Effective Cost &nbsp;·&nbsp; Auto name-matching enabled</p>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="step-row">
    <span class="step-pill">① Parse Deal</span>
    <span class="step-pill">② Effective Cost</span>
    <span class="step-pill">③ Effective SP</span>
    <span class="step-pill">④ Required SP = EC × 1.10</span>
    <span class="step-pill">⑤ Adjustment = Req SP − ESP</span>
    <span class="step-pill">🔁 Fuzzy Name Match</span>
</div>
""", unsafe_allow_html=True)

# ── Guard ─────────────────────────────────────
if not cost_file or not sales_file:
    st.info("⬆️  Upload both the **Cost File** and **Sales File** from the sidebar to begin.")
    st.markdown("""
<div class="card">
    <div class="card-title">How It Works</div>
    <table>
        <thead><tr><th>Step</th><th>Formula</th><th>Notes</th></tr></thead>
        <tbody>
            <tr><td>1 — Parse Deal</td><td>"10+2" → PQty=10, FQty=2</td><td>Blank/invalid → 1+0</td></tr>
            <tr><td>2 — Effective Cost</td><td>(Price × PQty) ÷ (PQty + FQty)</td><td>True per-unit cost</td></tr>
            <tr><td>3 — Effective SP</td><td>(SP × Qty) ÷ (Qty + SaleFree)</td><td>Net sale: ESP = SP</td></tr>
            <tr><td>4 — Required SP</td><td>EC × 1.10</td><td>10% margin on EC</td></tr>
            <tr><td>5 — Adjustment</td><td>max(Req SP − ESP, 0) × Qty</td><td>Claim amount</td></tr>
            <tr><td>🔁 Fuzzy Match</td><td>difflib ≥ 75% similarity</td><td>Auto-fixes name typos</td></tr>
        </tbody>
    </table>
</div>
""", unsafe_allow_html=True)
    st.stop()

# ── Load files ─────────────────────────────────
try:
    cost_df  = pd.read_excel(cost_file)
    sales_df = pd.read_excel(sales_file)
except Exception as e:
    st.error(f"❌ Could not read file: {e}")
    st.stop()

# ── Validate columns ───────────────────────────
required_cost  = {"Product Name", "Purchase Price"}
required_sales = {"Party Name", "Product Name", "Quantity", "Free Qty", "Selling Price"}

cost_cols  = set(c.strip() for c in cost_df.columns)
sales_cols = set(c.strip() for c in sales_df.columns)

if missing_c := required_cost - cost_cols:
    st.error(f"❌ Cost file missing columns: **{', '.join(missing_c)}**")
    st.stop()
if missing_s := required_sales - sales_cols:
    st.error(f"❌ Sales file missing columns: **{', '.join(missing_s)}**")
    st.stop()

# ── Run ────────────────────────────────────────
result_df, auto_fixed, unmatched = run_calculations(sales_df.copy(), cost_df.copy())

# ══════════════════════════════════════════════
# FUZZY MATCH REPORT
# ══════════════════════════════════════════════

if auto_fixed:
    rows_html = "".join(
        f"""<tr>
            <td>{r['Sales File Name']}</td>
            <td>→</td>
            <td>{r['Matched Cost Name']}</td>
            <td><span class="match-badge">{r['Similarity']}</span></td>
        </tr>"""
        for r in auto_fixed
    )
    st.markdown(f"""
<div class="card">
    <div class="card-title">🔁 Auto Name Corrections Applied — {len(auto_fixed)} product(s)</div>
    <p style="font-size:0.82rem; color:#5D6D7E; margin-bottom:10px;">
        These product names in your Sales file didn't exactly match the Cost file.
        They were automatically matched by similarity and included in calculations.
    </p>
    <table class="fuzzy-table">
        <thead><tr>
            <th>Sales File Name</th><th></th>
            <th>Matched to Cost File</th>
            <th>Similarity</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
    </table>
</div>
""", unsafe_allow_html=True)

if unmatched:
    rows_html = "".join(
        f'<tr><td>{p}</td><td><span class="warn-badge">NO MATCH FOUND</span></td></tr>'
        for p in unmatched
    )
    st.markdown(f"""
<div class="card" style="border-left:4px solid #E67E22;">
    <div class="card-title">⚠️ Products Still Unmatched — {len(unmatched)} product(s)</div>
    <p style="font-size:0.82rem; color:#5D6D7E; margin-bottom:10px;">
        These could not be matched even with fuzzy logic (similarity below 75%).
        Please add them to your Cost file manually.
    </p>
    <table class="fuzzy-table">
        <thead><tr><th>Product Name (from Sales File)</th><th>Status</th></tr></thead>
        <tbody>{rows_html}</tbody>
    </table>
</div>
""", unsafe_allow_html=True)

if result_df.empty:
    st.error("No matching products found. Please check both files.")
    st.stop()

# ══════════════════════════════════════════════
# METRICS
# ══════════════════════════════════════════════

total_adj       = result_df["Total Adjustment"].sum()
rows_with_adj   = (result_df["Total Adjustment"] > 0).sum()
total_rows      = len(result_df)
unique_parties  = result_df["Party Name"].nunique()
unique_products = result_df["Product Name"].nunique()

st.markdown(f"""
<div class="metric-row">
    {metric_html("Total Adjustment", total_adj, "danger" if total_adj > 0 else "ok")}
    {count_metric_html("Lines with Adj",
        f"{rows_with_adj} / {total_rows}",
        "var(--danger)" if rows_with_adj else "var(--ok)")}
    {count_metric_html("Parties",  unique_parties)}
    {count_metric_html("Products", unique_products)}
    {count_metric_html("Auto-Fixed Names", len(auto_fixed), "var(--ok)")}
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Detailed Results",
    "🏢 Party-wise Summary",
    "💊 Product-wise Summary",
    "🔍 Raw Data Preview",
])

# ── TAB 1 ─────────────────────────────────────
with tab1:
    st.markdown('<div class="card-title">LINE-WISE ADJUSTMENT DETAILS</div>', unsafe_allow_html=True)

    col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
    with col_f1:
        party_filter = st.multiselect(
            "Filter by Party",
            options=sorted(result_df["Party Name"].unique()),
            placeholder="All parties",
        )
    with col_f2:
        product_filter = st.multiselect(
            "Filter by Product",
            options=sorted(result_df["Product Name"].unique()),
            placeholder="All products",
        )
    with col_f3:
        adj_only = st.checkbox("Adj > 0 only", value=False)

    display_df = result_df.copy()
    if party_filter:
        display_df = display_df[display_df["Party Name"].isin(party_filter)]
    if product_filter:
        display_df = display_df[display_df["Product Name"].isin(product_filter)]
    if adj_only:
        display_df = display_df[display_df["Total Adjustment"] > 0]

    st.dataframe(
        style_result_table(display_df),
        use_container_width=True,
        hide_index=True,
        height=460,
    )
    st.caption(
        f"Showing {len(display_df)} of {total_rows} rows  ·  "
        f"Filtered Total Adjustment: ₹{display_df['Total Adjustment'].sum():,.2f}"
    )

# ── TAB 2 ─────────────────────────────────────
with tab2:
    st.markdown('<div class="card-title">PARTY-WISE ADJUSTMENT SUMMARY</div>', unsafe_allow_html=True)

    party_summary = (
        result_df
        .groupby("Party Name", as_index=False)
        .agg(
            Lines            = ("Product Name",    "count"),
            Lines_With_Adj   = ("Total Adjustment", lambda x: (x > 0).sum()),
            Total_Qty        = ("Quantity",         "sum"),
            Total_Adjustment = ("Total Adjustment", "sum"),
        )
        .sort_values("Total_Adjustment", ascending=False)
    )

    def style_party(df):
        def hl(row):
            return (
                ["background-color:#FEF9E7; font-weight:500;"] * len(row)
                if row["Total_Adjustment"] > 0 else [""] * len(row)
            )
        return (
            df.style.apply(hl, axis=1)
              .format({"Total_Adjustment": "₹{:,.2f}", "Total_Qty": "{:.0f}"})
              .bar(subset=["Total_Adjustment"], color="#AED6F1", vmin=0)
        )

    st.dataframe(style_party(party_summary), use_container_width=True, hide_index=True)
    st.metric("Grand Total", f"₹{party_summary['Total_Adjustment'].sum():,.2f}")

# ── TAB 3 ─────────────────────────────────────
with tab3:
    st.markdown('<div class="card-title">PRODUCT-WISE ADJUSTMENT SUMMARY</div>', unsafe_allow_html=True)

    product_summary = (
        result_df
        .groupby("Product Name", as_index=False)
        .agg(
            Parties          = ("Party Name",       "count"),
            Total_Qty        = ("Quantity",          "sum"),
            Avg_EC           = ("EC",                "mean"),
            Avg_ESP          = ("ESP",               "mean"),
            Avg_Required_SP  = ("Required SP",       "mean"),
            Total_Adjustment = ("Total Adjustment",  "sum"),
        )
        .sort_values("Total_Adjustment", ascending=False)
    )

    def style_product(df):
        currency = ["Avg_EC", "Avg_ESP", "Avg_Required_SP", "Total_Adjustment"]
        def hl(row):
            return (
                ["background-color:#FEF9E7; font-weight:500;"] * len(row)
                if row["Total_Adjustment"] > 0 else [""] * len(row)
            )
        return (
            df.style.apply(hl, axis=1)
              .format({c: "₹{:,.4f}" for c in currency})
              .format({"Total_Qty": "{:.0f}"})
              .bar(subset=["Total_Adjustment"], color="#A9DFBF", vmin=0)
        )

    st.dataframe(style_product(product_summary), use_container_width=True, hide_index=True)
    st.metric("Grand Total", f"₹{product_summary['Total_Adjustment'].sum():,.2f}")

# ── TAB 4 ─────────────────────────────────────
with tab4:
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.markdown('<div class="card-title">COST FILE PREVIEW</div>', unsafe_allow_html=True)
        st.dataframe(cost_df.head(60), use_container_width=True, hide_index=True)
        st.caption(f"{len(cost_df)} rows")
    with col_r2:
        st.markdown('<div class="card-title">SALES FILE PREVIEW</div>', unsafe_allow_html=True)
        st.dataframe(sales_df.head(60), use_container_width=True, hide_index=True)
        st.caption(f"{len(sales_df)} rows")

# ══════════════════════════════════════════════
# EXCEL EXPORT
# ══════════════════════════════════════════════

st.markdown("---")
st.markdown("### 📥 Export Results")

from io import BytesIO

def to_excel_bytes(df_detail, df_party, df_product, df_fuzzy, df_unmatched):
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_detail.to_excel(writer,   sheet_name="Detailed Results",    index=False)
        df_party.to_excel(writer,    sheet_name="Party-wise Summary",  index=False)
        df_product.to_excel(writer,  sheet_name="Product-wise Summary", index=False)
        if df_fuzzy is not None and not df_fuzzy.empty:
            df_fuzzy.to_excel(writer, sheet_name="Auto Name Fixes",    index=False)
        if df_unmatched:
            pd.DataFrame({"Unmatched Products": df_unmatched}).to_excel(
                writer, sheet_name="Unmatched Products", index=False
            )
    return buf.getvalue()

fuzzy_df     = pd.DataFrame(auto_fixed) if auto_fixed else pd.DataFrame()
export_bytes = to_excel_bytes(result_df, party_summary, product_summary, fuzzy_df, unmatched)

col_e1, col_e2 = st.columns([1, 3])
with col_e1:
    st.download_button(
        label="⬇️ Download Excel Report",
        data=export_bytes,
        file_name="SFMedical_Adjustment_Report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
with col_e2:
    st.caption(
        "Sheets: **Detailed Results** · **Party-wise** · **Product-wise** · "
        "**Auto Name Fixes** · **Unmatched Products**"
    )

# ── Footer ─────────────────────────────────────
st.markdown("""
<div style="text-align:center; color:#95A5A6; font-size:0.75rem;
            margin-top:40px; padding-top:20px; border-top:1px solid #D5D8DC;">
    S.F. Medical Agency &nbsp;·&nbsp; Pharma Adjustment Calculator v2 &nbsp;·&nbsp;
    Margin on Effective Cost · Fuzzy Name Matching Enabled
</div>
""", unsafe_allow_html=True)
