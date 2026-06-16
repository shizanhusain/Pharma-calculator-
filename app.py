import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup

st.set_page_config(page_title="Pharma Adjustment Calculator", layout="wide")

st.title("💊 Pharma Adjustment Calculator (Safe Version)")

# -------------------------
# USER INPUTS
# -------------------------
tax = st.number_input("Tax %", value=5.0)
margin = st.number_input("Margin %", value=10.0)

cost_file = st.file_uploader("Upload Cost Excel", type=["xlsx"])
sales_file = st.file_uploader("Upload Sales HTML", type=["html"])

# -------------------------
# SAFE COST FILE READER
# -------------------------
def read_cost_file(file):
    try:
        df = pd.read_excel(file)

        st.subheader("📄 Cost File Preview")
        st.dataframe(df)

        # Normalize column names
        df.columns = df.columns.str.strip()

        # Flexible column detection
        product_col = [c for c in df.columns if "product" in c.lower()]
        cost_col = [c for c in df.columns if "cost" in c.lower()]

        if not product_col or not cost_col:
            st.error("❌ Cost file must have columns like 'Product' and 'Cost Price'")
            return None

        df = df.rename(columns={
            product_col[0]: "Product",
            cost_col[0]: "Cost Price"
        })

        df["Product"] = df["Product"].astype(str).str.lower().str.strip()
        df["Cost Price"] = pd.to_numeric(df["Cost Price"], errors="coerce")

        return df[["Product", "Cost Price"]]

    except Exception as e:
        st.error(f"❌ Error reading cost file: {e}")
        return None

# -------------------------
# SAFE HTML PARSER (TABLE BASED)
# -------------------------
def parse_html(file):
    try:
        soup = BeautifulSoup(file.read(), "html.parser")

        tables = pd.read_html(str(soup))

        if len(tables) == 0:
            st.error("❌ No tables found in HTML")
            return None

        # Take largest table
        df = max(tables, key=len)

        st.subheader("🔍 Raw Sales Data (Extracted)")
        st.dataframe(df)

        df.columns = df.columns.astype(str)

        # Detect columns automatically
        desc_col = [c for c in df.columns if "desc" in c.lower()]
        qty_col = [c for c in df.columns if "qty" in c.lower()]
        rate_col = [c for c in df.columns if "rate" in c.lower()]

        if not desc_col or not qty_col or not rate_col:
            st.error("❌ Could not detect DESCRIPTION / QTY / RATE columns")
            return None

        df = df.rename(columns={
            desc_col[0]: "Product",
            qty_col[0]: "Qty",
            rate_col[0]: "Rate"
        })

        df["Product"] = df["Product"].astype(str).str.lower().str.strip()
        df["Qty"] = pd.to_numeric(df["Qty"], errors="coerce")
        df["Rate"] = pd.to_numeric(df["Rate"], errors="coerce")

        df = df.dropna(subset=["Qty", "Rate"])

        # Temporary Party (will improve later)
        df["Party"] = "Unknown"

        return df[["Party", "Product", "Qty", "Rate"]]

    except Exception as e:
        st.error(f"❌ Error parsing HTML: {e}")
        return None

# -------------------------
# MAIN LOGIC
# -------------------------
if cost_file and sales_file:

    cost_df = read_cost_file(cost_file)
    sales_df = parse_html(sales_file)

    if cost_df is not None and sales_df is not None:

        # Merge safely
        merged = pd.merge(sales_df, cost_df, on="Product", how="left")

        if merged["Cost Price"].isna().all():
            st.warning("⚠ No products matched between cost & sales")

        # Calculations
        merged["Cost After Tax"] = merged["Cost Price"] * (1 + tax/100)
        merged["Target Price"] = merged["Cost After Tax"] * (1 + margin/100)

        merged["Loss per Unit"] = merged["Target Price"] - merged["Rate"]
        merged["Loss per Unit"] = merged["Loss per Unit"].apply(lambda x: max(x, 0))

        merged["Total Loss"] = merged["Loss per Unit"] * merged["Qty"]

        # Adjustment quantity (how much company should give)
        merged["Adjustment Qty"] = merged["Total Loss"] / merged["Cost Price"]

        # -------------------------
        # SHOW RESULT
        # -------------------------
        st.subheader("📊 Detailed Result")
        st.dataframe(merged)

        # Party-wise summary
        party_summary = merged.groupby("Party")["Total Loss"].sum().reset_index()

        st.subheader("📊 Party-wise Loss")
        st.dataframe(party_summary)

        st.success(f"💰 Total Loss: ₹{merged['Total Loss'].sum():.2f}")
