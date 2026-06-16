import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup

st.set_page_config(page_title="Pharma Calculator", layout="wide")

st.title("💊 Pharma Margin & Adjustment Calculator")

# ---------------- INPUT ----------------
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

    # Auto detect columns
    product_col = None
    cost_col = None

    for col in df.columns:
        if "product" in col.lower() or "item" in col.lower():
            product_col = col
        if "cost" in col.lower() or "price" in col.lower():
            cost_col = col

    if product_col is None or cost_col is None:
        st.error("❌ Cost file must have Product & Cost columns")
        return None

    df = df.rename(columns={
        product_col: "Product",
        cost_col: "Cost Price"
    })

    df["Product"] = df["Product"].apply(clean)
    df["Cost Price"] = pd.to_numeric(df["Cost Price"], errors="coerce")

    return df


# ---------------- PARSE HTML (FINAL FIX) ----------------
def parse_html(file):
    try:
        html = file.read().decode("utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")

        lines = [div.get_text(strip=True) for div in soup.find_all("div")]

        data = []
        current_party = None
        current_product = None

        for line in lines:

            # PARTY NAME
            if line.isupper() and len(line) > 5 and "TOTAL" not in line:
                current_party = line
                continue

            # Skip junk lines
            if any(x in line for x in ["TOTAL", "----", "DESCRIPTION"]):
                continue

            # PRODUCT LINE (no numbers)
            if not any(char.isdigit() for char in line):
                if len(line) > 3:
                    current_product = clean(line)
                continue

            # NUMERIC LINE (contains qty & rate)
            parts = line.split()

            numbers = []
            for p in parts:
                try:
                    numbers.append(float(p))
                except:
                    pass

            if len(numbers) >= 2 and current_product:

                qty = numbers[0]
                rate = numbers[1]

                data.append({
                    "Party": current_party,
                    "Product": current_product,
                    "Qty": qty,
                    "Rate": rate
                })

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


# ---------------- MAIN ----------------
if cost_file and sales_file:

    cost_df = load_cost(cost_file)
    sales_df = parse_html(sales_file)

    if cost_df is None or sales_df is None:
        st.stop()

    # Merge
    df = pd.merge(sales_df, cost_df, on="Product", how="left")

    # Show unmatched products
    unmatched = df[df["Cost Price"].isna()]
    if not unmatched.empty:
        st.warning("⚠ Some products not matched with cost file")
        st.dataframe(unmatched[["Product"]].drop_duplicates())

    df["Cost Price"] = df["Cost Price"].fillna(0)

    # Calculations
    df["Cost After Tax"] = df["Cost Price"] * (1 + tax)
    df["Target Price"] = df["Cost After Tax"] * (1 + margin)

    df["Loss per Unit"] = df["Target Price"] - df["Rate"]
    df["Loss per Unit"] = df["Loss per Unit"].apply(lambda x: max(x, 0))

    df["Total Loss"] = df["Loss per Unit"] * df["Qty"]

    # Adjustment (GOODS FORM)
    df["Adjustment Qty"] = df.apply(
        lambda row: (row["Total Loss"] / row["Cost Price"])
        if row["Cost Price"] > 0 else 0,
        axis=1
    )

    # Show only loss entries
    df = df[df["Total Loss"] > 0]

    if df.empty:
        st.success("✅ No loss found")
        st.stop()

    # OUTPUT
    st.subheader("📊 Detailed Adjustment")
    st.dataframe(df[[
        "Party", "Product", "Qty", "Rate",
        "Cost Price", "Loss per Unit",
        "Total Loss", "Adjustment Qty"
    ]])

    # Party-wise summary
    party = df.groupby("Party")[["Total Loss", "Adjustment Qty"]].sum().reset_index()

    st.subheader("📊 Party-wise Summary")
    st.dataframe(party)

    st.success(f"💰 Total Loss: ₹{df['Total Loss'].sum():.2f}")
