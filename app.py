import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup
import re
from io import BytesIO

# ─────────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Pharma Adjustment Calculator",
    page_icon="💊",
    layout="wide",
)

st.markdown("""
<style>
    .main-title {
        font-size: 2rem;
        font-weight: 700;
        color: #1a3c5e;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 0.95rem;
        color: #6b7280;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #1a3c5e 0%, #2563eb 100%);
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        color: white;
        text-align: center;
    }
    .metric-label {
        font-size: 0.8rem;
        opacity: 0.85;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        margin-top: 0.2rem;
    }
    .section-header {
        font-size: 1.05rem;
        font-weight: 600;
        color: #1a3c5e;
        border-left: 4px solid #2563eb;
        padding-left: 0.6rem;
        margin: 1.5rem 0 0.8rem 0;
    }
    .stAlert > div {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">💊 Pharma Adjustment Calculator</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">S.F. Medical Agency — Party & Item Wise Loss Analysis</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  SIDEBAR — INPUTS
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    tax = st.number_input("Tax %", min_value=0.0, max_value=50.0, value=5.0, step=0.5) / 100
    margin = st.number_input("Margin %", min_value=0.0, max_value=100.0, value=10.0, step=0.5) / 100
    st.markdown("---")
    st.header("📂 Upload Files")
    cost_file = st.file_uploader("Cost Excel (.xlsx)", type=["xlsx"])
    sales_file = st.file_uploader("Sales HTML Report (.html)", type=["html"])
    st.markdown("---")
    st.caption("Tip: Cost Excel should have Product in col A and Cost Price in col B.")

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def clean(text):
    """Lowercase and strip a string."""
    return str(text).lower().strip()


# ─────────────────────────────────────────────
#  COST FILE LOADER
# ─────────────────────────────────────────────
def load_cost(file):
    df = pd.read_excel(file)
    df.columns = df.columns.str.strip()
    df = df.rename(columns={
        df.columns[0]: "Product",
        df.columns[1]: "Cost Price"
    })
    df["Product"] = df["Product"].apply(clean)
    df["Cost Price"] = pd.to_numeric(df["Cost Price"], errors="coerce")
    return df


# ─────────────────────────────────────────────
#  HTML PARSER  (fixed for absolute-position layout)
# ─────────────────────────────────────────────
def parse_html(file):
    """
    The HTML from Tally/FoxPro reports uses position:absolute divs.
    BeautifulSoup's get_text() loses layout order.
    Instead we:
      1. Read every <DIV class="font1"> individually.
      2. Use CSS width to tell party-name divs (narrow) from data-row divs (wide ~723px).
      3. Parse the all-in-one data row:
            PRODUCT NAME   SIZE   QTY   FREE/-   RATE   AMOUNT   %
         by picking numbers from the end of the string.
    """
    html = file.read().decode("utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")

    data = []
    current_party = None

    # Lines/words we want to skip
    SKIP_FRAGMENTS = [
        "D E S C R I P T I O N", "QTY.", "FREE", "RATE", "AMOUNT",
        "GRAND TOTAL", "End of Report", "Continued",
        "Page No", "PARTY / ITEM", "SALES SUMMARY",
        "S.F.MEDICAL", "GARHI", "Phone", "GSTIN",
        "Report For", "Company :", "SALE-S/R", "SPECIALITY",
    ]

    divs = soup.find_all("div", class_="font1")

    for div in divs:
        # Get clean text; replace Tally's non-breaking hyphen (U+2011) with normal '-'
        raw = div.get_text(" ")
        text = raw.replace("\u2011", "-").replace("\xa0", " ").strip()
        text = re.sub(r"\s+", " ", text)

        if not text:
            continue

        # Skip separator lines (all dashes)
        if re.fullmatch(r"[-\s]+", text):
            continue

        # Skip known header / footer fragments
        if any(frag.lower() in text.lower() for frag in SKIP_FRAGMENTS):
            continue

        # Skip TOTAL lines
        if re.match(r"^\s*TOTAL\s*:", text, re.IGNORECASE):
            continue

        # ── Get div pixel width from inline style ──────────────────────
        style = div.get("style", "")
        width_match = re.search(r"width:\s*(\d+)px", style)
        div_width = int(width_match.group(1)) if width_match else 0

        # ── PARTY NAME: narrow div, no leading space, no digits at start ─
        #    Typical party div width is 80–250 px
        if div_width < 500 and not text.startswith(" "):
            # Confirm it looks like a name (letters + spaces + common punct)
            if re.search(r"[A-Za-z]", text) and not re.match(r"^\d", text):
                current_party = text
            continue

        # ── DATA ROW: wide div (≥ 600 px) with leading space ─────────────
        #    Format: " PRODUCT NAME  SIZE  QTY  FREE/-  RATE  AMOUNT  %"
        if div_width >= 600 and text.startswith(" ") and current_party:

            # Extract every number in the line
            numbers = re.findall(r"\d+\.?\d*", text)

            # We need at least 4 numbers: qty, free(or 0), rate, amount
            if len(numbers) < 3:
                continue

            try:
                # Column positions from end (right-anchored):
                #   [-1] = percentage
                #   [-2] = amount
                #   [-3] = rate
                #   [-4] = free qty (0 or a number)
                #   [-5] = sold qty
                # But when free = '-' (dash) it doesn't appear as a number,
                # so we handle both cases:
                #   5+ numbers  →  QTY is numbers[-5], RATE is numbers[-3]
                #   4   numbers →  QTY is numbers[-4], RATE is numbers[-3]  (no free)
                #   3   numbers →  QTY is numbers[-3], RATE is numbers[-2]  (minimal)

                if len(numbers) >= 5:
                    qty  = float(numbers[-5])
                    rate = float(numbers[-3])
                elif len(numbers) == 4:
                    qty  = float(numbers[-4])
                    rate = float(numbers[-3])
                else:
                    qty  = float(numbers[-3])
                    rate = float(numbers[-2])

                # Product name = text before the block of numbers begins
                # Strategy: split at 2+ spaces followed by a digit
                product_part = re.split(r"\s{2,}(?=\d)", text.lstrip())[0].strip()

                # Clean up trailing size tokens like "1X10", "100ML", "2ML" etc.
                # (keep them — they're part of the product identity)

                data.append({
                    "Party":   current_party,
                    "Product": clean(product_part),
                    "Qty":     qty,
                    "Rate":    rate,
                })

            except (IndexError, ValueError):
                continue

    if not data:
        st.error("❌ No data extracted from the HTML. Check that you uploaded the correct Tally/FoxPro sales report.")
        return None

    df = pd.DataFrame(data)
    return df


# ─────────────────────────────────────────────
#  EXCEL EXPORT HELPER
# ─────────────────────────────────────────────
def to_excel(df_dict: dict) -> bytes:
    """Write multiple DataFrames to an Excel workbook and return bytes."""
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for sheet_name, df in df_dict.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    return buf.getvalue()


# ─────────────────────────────────────────────
#  MAIN LOGIC
# ─────────────────────────────────────────────
if not cost_file or not sales_file:
    st.info("👈 Upload both files in the sidebar to begin.")
    st.stop()

# ── Load data ──────────────────────────────────────────────────────────
with st.spinner("Reading Cost Excel..."):
    cost_df = load_cost(cost_file)

with st.spinner("Parsing Sales HTML..."):
    sales_df = parse_html(sales_file)

if sales_df is None:
    st.stop()

# ── Show raw extracted data ────────────────────────────────────────────
with st.expander("📋 Extracted Sales Data (raw)", expanded=False):
    st.dataframe(sales_df, use_container_width=True)
    st.caption(f"{len(sales_df)} rows extracted from HTML")

with st.expander("📋 Cost Price Data (raw)", expanded=False):
    st.dataframe(cost_df, use_container_width=True)
    st.caption(f"{len(cost_df)} products in cost sheet")

# ── Merge ──────────────────────────────────────────────────────────────
df = pd.merge(sales_df, cost_df, on="Product", how="left")

# ── Unmatched products ─────────────────────────────────────────────────
unmatched = df[df["Cost Price"].isna()]["Product"].drop_duplicates().reset_index(drop=True)
if not unmatched.empty:
    with st.expander(f"⚠️ {len(unmatched)} products not matched in Cost Sheet", expanded=True):
        st.dataframe(
            unmatched.rename("Unmatched Products").to_frame(),
            use_container_width=True
        )
        st.caption("These products have no cost price — they are excluded from loss calculations.")

df["Cost Price"] = df["Cost Price"].fillna(0)

# ── Calculations ───────────────────────────────────────────────────────
df["Cost After Tax"]  = df["Cost Price"] * (1 + tax)
df["Target Price"]    = df["Cost After Tax"] * (1 + margin)
df["Loss per Unit"]   = (df["Target Price"] - df["Rate"]).clip(lower=0)
df["Total Loss"]      = df["Loss per Unit"] * df["Qty"]
df["Adjustment Qty"]  = df.apply(
    lambda r: round(r["Total Loss"] / r["Cost Price"], 2) if r["Cost Price"] > 0 else 0,
    axis=1
)

# Keep only rows where there's actual loss
loss_df = df[df["Total Loss"] > 0].copy()

# ── Summary metrics ────────────────────────────────────────────────────
total_loss       = loss_df["Total Loss"].sum()
total_adj_qty    = loss_df["Adjustment Qty"].sum()
affected_parties = loss_df["Party"].nunique()
affected_products= loss_df["Product"].nunique()

st.markdown("---")
st.markdown('<div class="section-header">📊 Summary</div>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Total Loss</div>
        <div class="metric-value">₹{total_loss:,.2f}</div>
    </div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Adjustment Qty</div>
        <div class="metric-value">{total_adj_qty:.1f}</div>
    </div>""", unsafe_allow_html=True)
with c3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Affected Parties</div>
        <div class="metric-value">{affected_parties}</div>
    </div>""", unsafe_allow_html=True)
with c4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Affected Products</div>
        <div class="metric-value">{affected_products}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("")

if loss_df.empty:
    st.success("✅ No loss found! All products are selling above target price.")
    st.stop()

# ── Detailed loss table ────────────────────────────────────────────────
st.markdown('<div class="section-header">🔍 Detailed Loss (Product-wise)</div>', unsafe_allow_html=True)

detail_cols = ["Party", "Product", "Qty", "Rate", "Cost Price",
               "Cost After Tax", "Target Price", "Loss per Unit",
               "Total Loss", "Adjustment Qty"]

display_df = loss_df[detail_cols].copy()
for col in ["Cost Price", "Cost After Tax", "Target Price", "Rate",
            "Loss per Unit", "Total Loss"]:
    display_df[col] = display_df[col].map("₹{:,.2f}".format)

st.dataframe(display_df, use_container_width=True, height=350)

# ── Party-wise summary ─────────────────────────────────────────────────
st.markdown('<div class="section-header">🏪 Party-wise Loss Summary</div>', unsafe_allow_html=True)

party_df = (
    loss_df.groupby("Party")[["Total Loss", "Adjustment Qty"]]
    .sum()
    .sort_values("Total Loss", ascending=False)
    .reset_index()
)
party_df["Total Loss"]     = party_df["Total Loss"].map("₹{:,.2f}".format)
party_df["Adjustment Qty"] = party_df["Adjustment Qty"].map("{:.2f}".format)

st.dataframe(party_df, use_container_width=True)

# ── Product-wise summary ───────────────────────────────────────────────
st.markdown('<div class="section-header">💊 Product-wise Loss Summary</div>', unsafe_allow_html=True)

product_df = (
    loss_df.groupby("Product")[["Total Loss", "Adjustment Qty"]]
    .sum()
    .sort_values("Total Loss", ascending=False)
    .reset_index()
)
product_df["Total Loss"]     = product_df["Total Loss"].map("₹{:,.2f}".format)
product_df["Adjustment Qty"] = product_df["Adjustment Qty"].map("{:.2f}".format)

st.dataframe(product_df, use_container_width=True)

# ── Export to Excel ────────────────────────────────────────────────────
st.markdown("---")
st.markdown('<div class="section-header">⬇️ Export Results</div>', unsafe_allow_html=True)

export_detail = loss_df[detail_cols].copy()
export_party  = (
    loss_df.groupby("Party")[["Total Loss", "Adjustment Qty"]]
    .sum()
    .sort_values("Total Loss", ascending=False)
    .reset_index()
)
export_product = (
    loss_df.groupby("Product")[["Total Loss", "Adjustment Qty"]]
    .sum()
    .sort_values("Total Loss", ascending=False)
    .reset_index()
)

excel_bytes = to_excel({
    "Detailed Loss":  export_detail,
    "Party-wise":     export_party,
    "Product-wise":   export_product,
})

st.download_button(
    label="📥 Download Full Report (.xlsx)",
    data=excel_bytes,
    file_name="adjustment_report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
