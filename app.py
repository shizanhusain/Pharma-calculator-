import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup

st.set_page_config(page_title="Pharma Adjustment Calculator", layout="wide")

st.title("💊 Pharma Adjustment Calculator (FINAL FIXED VERSION)")

# Inputs
tax = st.number_input("Tax %", value=5.0) / 100
margin = st.number_input("Margin %", value=10.0) / 100

# Upload files
cost_file = st.file_uploader("Upload Cost Excel", type=["xlsx"])
sales_file = st.file_uploader("Upload Sales HTML", type=["html"])

# -------------------------------
# SAFE COLUMN FINDER
# -------------------------------
def find_column(df, keywords):
    for col in df.columns:
        col_lower = col.lower().strip()
        for key in keywords:
            if key in col_lower:
                return col
    return None

# -------------------------------
# HTML PARSER (FOR YOUR FORMAT)
# -------------------------------
def parse_html(file):
    try:
        html = file.read().decode("utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")

        lines = [div.get_text(strip=True) for div in soup.find_all("div")]

        data = []
        current_party = None

        for line in lines:

            # PARTY NAME
            if line.isupper() and len(line) > 5 and "TOTAL" not in line:
                current_party = line
                continue

            # Skip unwanted lines
            if "TOTAL" in line or "----" in line or "DESCRIPTION" in line:
                continue

            parts = line.split()

            if len(parts) < 5:
                continue

            try:
                qty = float(parts[-5])
                rate = float(parts[-3])
                product = " ".join(parts[:-5])

                data.append({
                    "Party": current_party,
                    "Product": product.lower().strip(),
                    "Qty": qty,
                    "Rate": rate
                })

            except:
                continue

        if len(data) == 0:
            st.error("❌ No data extracted from HTML")
            return None

        df = pd.DataFrame(data)

        st.subheader("📄 Extracted Sales Data")
        st.dataframe(df)

        return df

    except Exception as e:
        st.error(f"❌ HTML Parsing Failed: {e}")
        return None


# -------------------------------
# MAIN LOGIC
# -------------------------------
if cost_file and sales_file:

    try:
        cost_df = pd.read_excel(cost_file)

        # Detect columns safely
        product_col = find_column(cost_df, ["product", "item", "name"])
        cost_col = find_column(cost_df, ["cost", "price"])

        if product_col is None or cost_col is None:
            st.error("❌ Cost file must contain Product and Cost columns")
            st.stop()

        cost_df = cost_df.rename(columns={
            product_col: "Product",
            cost_col: "Cost Price"
        })

        # Clean data
        cost_df["Product"] = cost_df["Product"].astype(str).str.lower().str.strip()
        cost_df["Cost Price"] = pd.to_numeric(cost_df["Cost Price"], errors="coerce")

        # Calculate cost after tax
        cost_df["Cost After Tax"] = cost_df["Cost Price"] * (1 + tax)

        # Parse sales
        sales_df = parse_html(sales_file)

        if sales_df is None:
            st.stop()

        # Merge
        merged = pd.merge(
            sales_df,
            cost_df,
            on="Product",
            how="left"
        )

        # Show unmatched products
        unmatched = merged[merged["Cost Price"].isna()]

        if not unmatched.empty:
            st.warning("⚠️ Some products not matched with cost file")
            st.dataframe(unmatched[["Product"]])

        # Calculate profit/loss
        merged["Expected Selling Price"] = merged["Cost After Tax"] * (1 + margin)
        merged["Loss"] = (merged["Expected Selling Price"] - merged["Rate"]) * merged["Qty"]

        # Replace NaN losses with 0
        merged["Loss"] = merged["Loss"].fillna(0)

        st.subheader("📊 Detailed Calculation")
        st.dataframe(merged)

        # Party-wise loss
        party_loss = merged.groupby("Party")["Loss"].sum().reset_index()

        st.subheader("📉 Party-wise Loss")
        st.dataframe(party_loss)

        # Total loss
        total_loss = party_loss["Loss"].sum()

        st.success(f"💰 Total Loss: ₹{round(total_loss, 2)}")

    except Exception as e:
        st.error(f"❌ Error: {e}")
