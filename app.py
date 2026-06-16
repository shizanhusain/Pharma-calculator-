import streamlit as st
import pandas as pd

st.title("💊 Pharma Adjustment Calculator")

tax = st.number_input("Tax %", value=5.0)
margin = st.number_input("Margin %", value=10.0)

bill_file = st.file_uploader("Upload Sales Excel", type=["xlsx"])
cost_file = st.file_uploader("Upload Cost Excel", type=["xlsx"])

if bill_file and cost_file:

    bill_df = pd.read_excel(bill_file)
    cost_df = pd.read_excel(cost_file)

    # 🔍 SHOW columns (for debugging)
    st.write("📄 Bill Columns:", list(bill_df.columns))
    st.write("📄 Cost Columns:", list(cost_df.columns))

    # 🔧 AUTO DETECT FUNCTION
    def find_col(df, keywords):
        for col in df.columns:
            for key in keywords:
                if key.lower() in col.lower():
                    return col
        return None

    # Detect columns
    bill_product = find_col(bill_df, ["product", "item", "description"])
    bill_qty = find_col(bill_df, ["qty", "quantity"])
    bill_rate = find_col(bill_df, ["rate", "price"])

    cost_product = find_col(cost_df, ["product", "item", "description"])
    cost_price = find_col(cost_df, ["cost", "price", "rate"])

    # ❌ If anything missing → stop safely
    if not bill_product or not cost_product or not cost_price:
        st.error("❌ Required columns not found")
        st.stop()

    # ✅ Rename safely
    bill_df = bill_df.rename(columns={
        bill_product: "Product",
        bill_qty: "Qty" if bill_qty else None,
        bill_rate: "Rate" if bill_rate else None
    })

    cost_df = cost_df.rename(columns={
        cost_product: "Product",
        cost_price: "Cost Price"
    })

    # Clean text
    bill_df["Product"] = bill_df["Product"].astype(str).str.strip().str.lower()
    cost_df["Product"] = cost_df["Product"].astype(str).str.strip().str.lower()

    # Merge
    df = pd.merge(bill_df, cost_df, on="Product", how="left")

    st.subheader("📊 Merged Data")
    st.dataframe(df)

    # ⚠️ Missing matches
    if "Cost Price" in df.columns:
        missing = df[df["Cost Price"].isna()]
        if not missing.empty:
            st.warning("⚠️ Some products not matched")
            st.dataframe(missing)
    else:
        st.error("❌ Cost Price column missing after merge")
        st.stop()

    # ✅ Calculate safely
    df["Cost Price"] = pd.to_numeric(df["Cost Price"], errors="coerce")
    df["Final Price"] = df["Cost Price"] * (1 + tax/100) * (1 + margin/100)

    st.subheader("✅ Final Output")
    st.dataframe(df)
