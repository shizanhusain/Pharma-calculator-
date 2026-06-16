import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup
import re

st.set_page_config(layout="wide")

st.title("💊 Pharma Adjustment Calculator (FINAL CORRECT VERSION)")

tax = st.number_input("Tax %", value=5.0) / 100
margin = st.number_input("Margin %", value=10.0) / 100

cost_file = st.file_uploader("Upload Cost Excel", type=["xlsx"])
sales_file = st.file_uploader("Upload Sales HTML", type=["html"])


# ---------------- CLEAN ----------------
def clean(text):
    return str(text).lower().strip()


# ---------------- LOAD COST ----------------
def load_cost(file):
    df = pd.read_excel(file)
    df.columns = df.columns.str.strip()

    # auto detect
    product_col = df.columns[0]
    cost_col = df.columns[1]

    df = df.rename(columns={
        product_col: "Product",
        cost_col: "Cost Price"
    })

    df["Product"] = df["Product"].apply(clean)
    df["Cost Price"] = pd.to_numeric(df["Cost Price"], errors="coerce")

    return df


# ---------------- PARSE HTML ----------------
def parse_html(file):
    html = file.read().decode("utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")

    lines = [div.get_text(" ", strip=True) for div in soup.find_all("div")]

    data = []
    current_party = None

    for line in lines:

        # Detect PARTY
        if line.isupper() and "TOTAL" not in line and len(line) > 5:
            current_party = line.strip()
            continue

        # Skip unwanted
        if "TOTAL" in line or "----" in line or "DESCRIPTION" in line:
            continue

        # Extract numbers from line
        numbers = re.findall(r"\d+\.\d+|\d+", line)

        if len(numbers) >= 4:

            try:
                qty = float(numbers[-4])   # qty
                rate = float(numbers[-2])  # rate

                # Remove numbers part to get product
                product = re.sub(r"\d+\.\d+|\d+", "", line)
                product = product.strip()

                data.append({
                    "Party": current_party,
                    "Product": clean(product),
                    "Qty": qty,
                    "Rate": rate
                })

            except:
                continue

    if len(data) == 0:
        st.error("❌ No data extracted — format mismatch")
        return None

    df = pd.DataFrame(data)

    st.subheader("✅ Extracted Sales Data")
    st.dataframe(df)

    return df


# ---------------- MAIN ----------------
if cost_file and sales_file:

    cost_df = load_cost(cost_file)
    sales_df = parse_html(sales_file)

    if sales_df is None:
        st.stop()

    # Merge
    df = pd.merge(sales_df, cost_df, on="Product", how="left")

    # Unmatched products
    unmatched = df[df["Cost Price"].isna()]
    if not unmatched.empty:
        st.warning("⚠ Unmatched products")
        st.dataframe(unmatched[["Product"]].drop_duplicates())

    df["Cost Price"] = df["Cost Price"].fillna(0)

    # Calculations
    df["Cost After Tax"] = df["Cost Price"] * (1 + tax)
    df["Target Price"] = df["Cost After Tax"] * (1 + margin)

    df["Loss per Unit"] = df["Target Price"] - df["Rate"]
    df["Loss per Unit"] = df["Loss per Unit"].apply(lambda x: max(x, 0))

    df["Total Loss"] = df["Loss per Unit"] * df["Qty"]

    df["Adjustment Qty"] = df.apply(
        lambda row: row["Total Loss"] / row["Cost Price"]
        if row["Cost Price"] > 0 else 0,
        axis=1
    )

    df = df[df["Total Loss"] > 0]

    if df.empty:
        st.success("✅ No loss found")
        st.stop()

    # Output
    st.subheader("📊 Detailed Adjustment")
    st.dataframe(df[[
        "Party", "Product", "Qty", "Rate",
        "Cost Price", "Loss per Unit",
        "Total Loss", "Adjustment Qty"
    ]])

    party = df.groupby("Party")[["Total Loss", "Adjustment Qty"]].sum().reset_index()

    st.subheader("📊 Party-wise Summary")
    st.dataframe(party)

    st.success(f"💰 Total Loss: ₹{df['Total Loss'].sum():.2f}")
