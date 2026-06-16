import streamlit as st
import pandas as pd
import re
from bs4 import BeautifulSoup

st.set_page_config(layout="wide")
st.title("💊 Pharma Adjustment Calculator")

# Inputs
tax = st.number_input("Tax %", value=5.0)
margin = st.number_input("Margin %", value=10.0)

cost_file = st.file_uploader("Upload Cost File (Excel)", type=["xlsx"])
sales_file = st.file_uploader("Upload Sales HTML", type=["html"])


# -------- CLEAN TEXT --------
def clean(text):
    return str(text).lower().strip()


# -------- LOAD COST FILE --------
def load_cost(file):
    df = pd.read_excel(file)
    df.columns = df.columns.str.strip()

    # AUTO detect columns
    product_col = None
    cost_col = None

    for col in df.columns:
        if "product" in col.lower():
            product_col = col
        if "cost" in col.lower():
            cost_col = col

    if product_col is None or cost_col is None:
        st.error("❌ Cost file must have Product & Cost columns")
        st.stop()

    df = df.rename(columns={
        product_col: "Product",
        cost_col: "Cost Price"
    })

    df["Product"] = df["Product"].apply(clean)

    return df


# -------- PARSE YOUR HTML FORMAT --------
def parse_html(file):
    soup = BeautifulSoup(file.read(), "html.parser")
    text = soup.get_text("\n")

    lines = text.split("\n")

    data = []
    current_party = None

    for line in lines:
        line = line.strip()

        if not line:
            continue

        # PARTY NAME (ALL CAPS)
        if line.isupper() and "TOTAL" not in line and len(line) > 5:
            current_party = line
            continue

        # SKIP TOTAL LINES
        if "TOTAL" in line:
            continue

        # MATCH PRODUCT LINE
        # pattern based on your file
        match = re.search(r"(.+?)\s+(\d+)\s+[-]?\s+([\d.]+)\s+([\d.]+)", line)

        if match:
            product = match.group(1)
            qty = int(match.group(2))
            rate = float(match.group(3))

            data.append({
                "Party": current_party,
                "Product": clean(product),
                "Qty": qty,
                "Rate": rate
            })

    return pd.DataFrame(data)


# -------- MAIN LOGIC --------
if cost_file and sales_file:

    cost_df = load_cost(cost_file)
    sales_df = parse_html(sales_file)

    # MERGE
    df = pd.merge(sales_df, cost_df, on="Product", how="left")

    # Fill missing cost
    df["Cost Price"] = df["Cost Price"].fillna(0)

    # CALCULATIONS
    df["Cost After Tax"] = df["Cost Price"] * (1 + tax/100)
    df["Target Price"] = df["Cost After Tax"] * (1 + margin/100)

    df["Loss per Unit"] = df["Target Price"] - df["Rate"]
    df["Loss per Unit"] = df["Loss per Unit"].apply(lambda x: max(x, 0))

    df["Total Loss"] = df["Loss per Unit"] * df["Qty"]

    # ADJUSTMENT QTY (VERY IMPORTANT)
    df["Adjustment Qty"] = df.apply(
        lambda row: row["Total Loss"] / row["Cost Price"]
        if row["Cost Price"] > 0 else 0,
        axis=1
    )

    # SHOW ONLY WHERE LOSS EXISTS
    df = df[df["Total Loss"] > 0]

    # DISPLAY
    st.subheader("📊 Detailed Adjustment")
    st.dataframe(df[[
        "Party", "Product", "Qty", "Rate",
        "Cost Price", "Loss per Unit",
        "Total Loss", "Adjustment Qty"
    ]])

    # PARTY SUMMARY
    party = df.groupby("Party")["Total Loss"].sum().reset_index()

    st.subheader("📊 Party-wise Loss")
    st.dataframe(party)

    st.success(f"💰 Total Loss: ₹{df['Total Loss'].sum():.2f}")
