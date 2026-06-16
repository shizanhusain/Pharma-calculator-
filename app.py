import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup
import re

st.set_page_config(layout="wide")

st.title("💊 Pharma Adjustment Calculator (Final Stable Version)")

# ---------------- INPUT ----------------
tax = st.number_input("Tax %", value=5.0) / 100
margin = st.number_input("Margin %", value=10.0) / 100

cost_file = st.file_uploader("Upload Cost Excel", type=["xlsx"])
sales_file = st.file_uploader("Upload Sales HTML", type=["html"])


# ---------------- CLEAN FUNCTION ----------------
def clean(text):
    return str(text).lower().strip()


# ---------------- LOAD COST FILE ----------------
def load_cost(file):
    df = pd.read_excel(file)
    df.columns = df.columns.str.strip()

    if len(df.columns) < 2:
        st.error("❌ Cost file must have at least 2 columns")
        return None

    df = df.rename(columns={
        df.columns[0]: "Product",
        df.columns[1]: "Cost Price"
    })

    df["Product"] = df["Product"].apply(clean)
    df["Cost Price"] = pd.to_numeric(df["Cost Price"], errors="coerce")

    return df


# ---------------- PARSE HTML (FINAL LOGIC) ----------------
def parse_html(file):
    html = file.read().decode("utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")

    lines = [div.get_text(" ", strip=True) for div in soup.find_all("div")]

    data = []
    current_party = None

    for line in lines:

        # -------- DETECT PARTY --------
        if line.isupper() and len(line) > 5:
            if not any(x in line.lower() for x in ["report", "summary", "description", "company"]):
                current_party = line.strip()
            continue

        # -------- SKIP HEADERS --------
        if any(x in line.lower() for x in [
            "summary", "description", "qty", "rate",
            "amount", "page", "report", "company", "gstin"
        ]):
            continue

        # -------- EXTRACT NUMBERS --------
        numbers = re.findall(r"\d+\.\d+|\d+", line)

        # Must have at least 4 numbers → real product line
        if len(numbers) >= 4 and current_party:

            try:
                qty = float(numbers[0])      # FIRST number
                rate = float(numbers[2])     # THIRD number

                # Remove numbers to get product name
                product = re.sub(r"\d+\.\d+|\d+", "", line).strip()

                # Skip garbage
                if len(product) < 3:
                    continue

                data.append({
                    "Party": current_party,
                    "Product": clean(product),
                    "Qty": qty,
                    "Rate": rate
                })

            except:
                continue

    if len(data) == 0:
        st.error("❌ No valid product lines found in HTML")
        return None

    df = pd.DataFrame(data)

    st.subheader("✅ Extracted Sales Data")
    st.dataframe(df)

    return df


# ---------------- MAIN LOGIC ----------------
if cost_file and sales_file:

    cost_df = load_cost(cost_file)
    if cost_df is None:
        st.stop()

    sales_df = parse_html(sales_file)
    if sales_df is None:
        st.stop()

    # -------- MERGE --------
    df = pd.merge(sales_df, cost_df, on="Product", how="left")

    # -------- SHOW UNMATCHED --------
    unmatched = df[df["Cost Price"].isna()]
    if not unmatched.empty:
        st.warning("⚠ Some products not matched with cost file")
        st.dataframe(unmatched[["Product"]].drop_duplicates())

    df["Cost Price"] = df["Cost Price"].fillna(0)

    # -------- CALCULATIONS --------
    df["Cost After Tax"] = df["Cost Price"] * (1 + tax)
    df["Target Price"] = df["Cost After Tax"] * (1 + margin)

    df["Loss per Unit"] = df["Target Price"] - df["Rate"]
    df["Loss per Unit"] = df["Loss per Unit"].apply(lambda x: max(x, 0))

    df["Total Loss"] = df["Loss per Unit"] * df["Qty"]

    # Adjustment in goods
    df["Adjustment Qty"] = df.apply(
        lambda row: row["Total Loss"] / row["Cost Price"]
        if row["Cost Price"] > 0 else 0,
        axis=1
    )

    # Keep only loss rows
    df = df[df["Total Loss"] > 0]

    if df.empty:
        st.success("✅ No loss found")
        st.stop()

    # -------- OUTPUT --------
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
