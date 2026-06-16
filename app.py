import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup
import re

st.title("💊 Pharma Adjustment Calculator (Correct Format Version)")

# Inputs
tax = st.number_input("Tax %", value=5.0) / 100
margin = st.number_input("Margin %", value=10.0) / 100

cost_file = st.file_uploader("Upload Cost Excel", type=["xlsx"])
sales_file = st.file_uploader("Upload Sales HTML", type=["html"])


def clean(text):
    return str(text).lower().strip()


# ---------------- COST FILE ----------------
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


# ---------------- HTML PARSER (NEW LOGIC) ----------------
def parse_html(file):
    html = file.read().decode("utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")

    text = soup.get_text("\n")
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    data = []
    current_party = None
    current_product = None

    for i in range(len(lines)):
        line = lines[i]

        # ---- Detect PARTY ----
        if line.isupper() and len(line) > 5 and not any(x in line.lower() for x in ["report", "summary", "description"]):
            current_party = line
            continue

        # ---- Detect PRODUCT ----
        if not re.search(r"\d", line) and len(line) > 3:
            current_product = line
            continue

        # ---- Detect NUMERIC LINE ----
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
        st.error("❌ Still no data extracted — format mismatch")
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

    df = pd.merge(sales_df, cost_df, on="Product", how="left")

    # Unmatched
    unmatched = df[df["Cost Price"].isna()]
    if not unmatched.empty:
        st.warning("⚠ Some products not matched")
        st.dataframe(unmatched[["Product"]].drop_duplicates())

    df["Cost Price"] = df["Cost Price"].fillna(0)

    # Calculations
    df["Cost After Tax"] = df["Cost Price"] * (1 + tax)
    df["Target Price"] = df["Cost After Tax"] * (1 + margin)

    df["Loss per Unit"] = df["Target Price"] - df["Rate"]
    df["Loss per Unit"] = df["Loss per Unit"].apply(lambda x: max(x, 0))

    df["Total Loss"] = df["Loss per Unit"] * df["Qty"]

    df["Adjustment Qty"] = df.apply(
        lambda r: r["Total Loss"] / r["Cost Price"] if r["Cost Price"] > 0 else 0,
        axis=1
    )

    df = df[df["Total Loss"] > 0]

    if df.empty:
        st.success("✅ No loss found")
        st.stop()

    # Output
    st.subheader("📊 Detailed Loss")
    st.dataframe(df)

    party = df.groupby("Party")[["Total Loss", "Adjustment Qty"]].sum().reset_index()

    st.subheader("📊 Party-wise Loss")
    st.dataframe(party)

    st.success(f"💰 Total Loss: ₹{df['Total Loss'].sum():.2f}")
