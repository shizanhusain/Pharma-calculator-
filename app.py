import streamlit as st
import pandas as pd
import re
from bs4 import BeautifulSoup

st.set_page_config(layout="wide")
st.title("💊 Pharma Adjustment Calculator (Safe Version)")

# ---------------- INPUT ----------------
tax = st.number_input("Tax %", value=5.0)
margin = st.number_input("Margin %", value=10.0)

cost_file = st.file_uploader("Upload Cost Excel", type=["xlsx"])
sales_file = st.file_uploader("Upload Sales HTML", type=["html"])


# ---------------- CLEAN ----------------
def clean(text):
    return str(text).lower().strip()


# ---------------- LOAD COST FILE ----------------
def load_cost(file):
    try:
        df = pd.read_excel(file)
        df.columns = df.columns.str.strip()

        if len(df.columns) < 2:
            st.error("❌ Cost file must have at least 2 columns")
            return None

        # Force columns
        df = df.rename(columns={
            df.columns[0]: "Product",
            df.columns[1]: "Cost Price"
        })

        df["Product"] = df["Product"].astype(str).apply(clean)
        df["Cost Price"] = pd.to_numeric(df["Cost Price"], errors="coerce").fillna(0)

        return df

    except Exception as e:
        st.error(f"❌ Error reading cost file: {e}")
        return None


# ---------------- PARSE HTML ----------------
def parse_html(file):
    try:
        soup = BeautifulSoup(file.read(), "html.parser")
        text = soup.get_text("\n")

        lines = text.split("\n")

        data = []
        current_party = None

        for line in lines:
            line = line.strip()

            if not line:
                continue

            # Detect PARTY NAME
            if line.isupper() and "TOTAL" not in line and len(line) > 5:
                current_party = line
                continue

            # Skip totals
            if "TOTAL" in line:
                continue

            # Extract product line
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

        df = pd.DataFrame(data)

        if df.empty:
            st.warning("⚠ No data extracted from HTML")
            return None

        return df

    except Exception as e:
        st.error(f"❌ Error reading HTML file: {e}")
        return None


# ---------------- MAIN ----------------
if cost_file and sales_file:

    cost_df = load_cost(cost_file)
    sales_df = parse_html(sales_file)

    if cost_df is None or sales_df is None:
        st.stop()

    st.subheader("🔍 Debug Columns")
    st.write("Cost Columns:", cost_df.columns)
    st.write("Sales Columns:", sales_df.columns)

    # ---------------- MERGE ----------------
    df = pd.merge(sales_df, cost_df, on="Product", how="left")

    # ---------------- HANDLE MISSING ----------------
    missing = df[df["Cost Price"].isna()]

    if not missing.empty:
        st.warning("⚠ Some products not matched with cost file")
        st.dataframe(missing[["Product"]].drop_duplicates())

    df["Cost Price"] = df["Cost Price"].fillna(0)

    # ---------------- CALCULATIONS ----------------
    df["Cost After Tax"] = df["Cost Price"] * (1 + tax / 100)
    df["Target Price"] = df["Cost After Tax"] * (1 + margin / 100)

    df["Loss per Unit"] = df["Target Price"] - df["Rate"]
    df["Loss per Unit"] = df["Loss per Unit"].apply(lambda x: max(x, 0))

    df["Total Loss"] = df["Loss per Unit"] * df["Qty"]

    # Adjustment quantity (goods)
    df["Adjustment Qty"] = df.apply(
        lambda row: (row["Total Loss"] / row["Cost Price"])
        if row["Cost Price"] > 0 else 0,
        axis=1
    )

    # Only show loss rows
    df = df[df["Total Loss"] > 0]

    if df.empty:
        st.success("✅ No loss found. Everything is profitable!")
        st.stop()

    # ---------------- OUTPUT ----------------
    st.subheader("📊 Detailed Adjustment")
    st.dataframe(df[[
        "Party", "Product", "Qty", "Rate",
        "Cost Price", "Loss per Unit",
        "Total Loss", "Adjustment Qty"
    ]])

    # Party-wise
    party = df.groupby("Party")["Total Loss"].sum().reset_index()

    st.subheader("📊 Party-wise Loss")
    st.dataframe(party)

    st.success(f"💰 Total Loss: ₹{df['Total Loss'].sum():.2f}")
