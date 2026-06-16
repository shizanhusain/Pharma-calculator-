import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup
import re

st.set_page_config(page_title="Pharma Calculator", layout="wide")

st.title("💊 Pharma Adjustment Calculator")

# ---------------- INPUTS ----------------
tax = st.number_input("Tax %", value=5.0)
margin = st.number_input("Margin %", value=10.0)

cost_file = st.file_uploader("Upload Cost Excel", type=["xlsx"])
html_file = st.file_uploader("Upload Sales HTML", type=["html"])

# ---------------- CLEAN FUNCTION ----------------
def clean(text):
    return text.lower().strip()

# ---------------- PARSE HTML ----------------
def parse_html(file):
    html = file.read().decode("utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")

    text = soup.get_text("\n")
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    data = []
    current_party = None
    current_product = None

    for line in lines:

        # ---- PARTY ----
        if line.isupper() and len(line) > 5:
            if not any(x in line for x in ["REPORT", "SUMMARY", "DESCRIPTION", "GSTIN", "PHONE"]):
                current_party = line
            continue

        # ---- PRODUCT ----
        if not re.search(r"\d", line) and len(line) > 3:
            current_product = line
            continue

        # ---- NUMBERS ----
        numbers = re.findall(r"\d+\.\d+|\d+", line)

        if len(numbers) >= 3 and current_product and current_party:
            try:
                qty = float(numbers[0])
                rate = float(numbers[1])

                data.append({
                    "Party": current_party,
                    "Product": clean(current_product),
                    "Qty": qty,
                    "Rate": rate
                })

                current_product = None

            except:
                continue

    if not data:
        st.error("❌ No data extracted from HTML")
        st.write(lines[:50])  # debug preview
        return None

    df = pd.DataFrame(data)
    st.subheader("✅ Extracted Sales Data")
    st.dataframe(df)

    return df

# ---------------- MAIN LOGIC ----------------
if cost_file and html_file:

    # Load cost file
    cost_df = pd.read_excel(cost_file)

    # ---- SAFETY FIX ----
    if "Product" not in cost_df.columns:
        st.error("❌ Cost file must have 'Product' column")
        st.stop()

    if "Cost Price" not in cost_df.columns:
        st.error("❌ Cost file must have 'Cost Price' column")
        st.stop()

    cost_df["Product"] = cost_df["Product"].apply(clean)

    # Cost after tax
    cost_df["Cost After Tax"] = cost_df["Cost Price"] * (1 + tax/100)

    # Parse HTML
    sales_df = parse_html(html_file)

    if sales_df is not None:

        # Merge
        df = pd.merge(sales_df, cost_df, on="Product", how="left")

        # Show unmatched products
        missing = df[df["Cost Price"].isna()]
        if not missing.empty:
            st.warning("⚠️ Some products not matched with cost file")
            st.dataframe(missing[["Product"]])

        # Remove unmatched
        df = df.dropna()

        if df.empty:
            st.error("❌ No matching products found")
            st.stop()

        # ---- CALCULATIONS ----
        df["Target Price"] = df["Cost After Tax"] * (1 + margin/100)
        df["Loss per Unit"] = df["Target Price"] - df["Rate"]

        df["Loss per Unit"] = df["Loss per Unit"].apply(lambda x: max(x, 0))

        df["Total Loss"] = df["Loss per Unit"] * df["Qty"]

        # ---- PARTY SUMMARY ----
        party_summary = df.groupby("Party")["Total Loss"].sum().reset_index()

        # ---- OUTPUT ----
        st.subheader("📊 Detailed Data")
        st.dataframe(df)

        st.subheader("📊 Party-wise Loss")
        st.dataframe(party_summary)

        st.success(f"💰 Total Loss: ₹{df['Total Loss'].sum():.2f}")
