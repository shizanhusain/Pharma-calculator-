import streamlit as st
import pandas as pd
import re
from bs4 import BeautifulSoup

st.set_page_config(page_title="Pharma Margin Calculator", layout="wide")

st.title("💊 Pharma Margin & Adjustment Calculator")

# Inputs
tax = st.number_input("Tax %", value=5.0)
margin = st.number_input("Margin %", value=10.0)

# Upload files
cost_file = st.file_uploader("Upload Cost File (Excel)", type=["xlsx"])
sales_file = st.file_uploader("Upload Sales Report (HTML)", type=["html"])


# ---------- FUNCTION: CLEAN TEXT ----------
def clean_text(text):
    return str(text).lower().strip()


# ---------- FUNCTION: LOAD COST FILE ----------
def load_cost_file(file):
    df = pd.read_excel(file)
    df.columns = df.columns.str.strip()

    # Auto-detect columns
    product_col = None
    cost_col = None

    for col in df.columns:
        if "product" in col.lower():
            product_col = col
        if "cost" in col.lower():
            cost_col = col

    if product_col is None or cost_col is None:
        st.error("❌ Could not detect Product / Cost column")
        st.stop()

    df = df.rename(columns={
        product_col: "Product",
        cost_col: "Cost Price"
    })

    df["Product"] = df["Product"].apply(clean_text)

    return df


# ---------- FUNCTION: PARSE HTML SALES ----------
def parse_html(file):
    soup = BeautifulSoup(file.read(), "html.parser")
    text = soup.get_text("\n")

    lines = text.split("\n")

    data = []
    current_party = None

    for line in lines:
        line = line.strip()

        # Detect PARTY (all caps line)
        if line.isupper() and len(line) > 5:
            current_party = line

        # Detect product line (has numbers)
        match = re.search(r"(.+?)\s+(\d+)\s+-?\s+([\d.]+)\s+([\d.]+)", line)

        if match:
            product = match.group(1)
            qty = int(match.group(2))
            rate = float(match.group(3))

            data.append({
                "Party": current_party,
                "Product": clean_text(product),
                "Qty": qty,
                "Rate": rate
            })

    return pd.DataFrame(data)


# ---------- MAIN ----------
if cost_file and sales_file:

    cost_df = load_cost_file(cost_file)
    sales_df = parse_html(sales_file)

    # Merge
    merged = pd.merge(sales_df, cost_df, on="Product", how="left")

    # Handle unmatched products
    merged["Cost Price"].fillna(0, inplace=True)

    # Calculate
    merged["Cost After Tax"] = merged["Cost Price"] * (1 + tax / 100)
    merged["Target Price"] = merged["Cost After Tax"] * (1 + margin / 100)

    merged["Loss per Unit"] = merged["Target Price"] - merged["Rate"]
    merged["Loss per Unit"] = merged["Loss per Unit"].apply(lambda x: max(x, 0))

    merged["Total Loss"] = merged["Loss per Unit"] * merged["Qty"]

    # Adjustment Qty (VERY IMPORTANT)
    merged["Adjustment Qty"] = merged.apply(
        lambda row: (row["Total Loss"] / row["Cost Price"]) if row["Cost Price"] > 0 else 0,
        axis=1
    )

    st.subheader("📊 Detailed Data")
    st.dataframe(merged)

    # Party-wise
    party_loss = merged.groupby("Party")["Total Loss"].sum().reset_index()

    st.subheader("📊 Party-wise Loss")
    st.dataframe(party_loss)

    st.success(f"💰 Total Loss: ₹{merged['Total Loss'].sum():.2f}")

    # Adjustment table
    st.subheader("📦 Adjustment Details")
    st.dataframe(merged[[
        "Party", "Product", "Qty", "Rate",
        "Cost Price", "Loss per Unit",
        "Total Loss", "Adjustment Qty"
    ]])
