import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")

st.title("💊 Pharma Adjustment Calculator (Excel Version)")

# ---------------- INPUT ----------------
tax = st.number_input("Tax %", value=5.0) / 100
margin = st.number_input("Margin %", value=10.0) / 100

cost_file = st.file_uploader("Upload Cost Excel", type=["xlsx"])
sales_file = st.file_uploader("Upload Sales Excel", type=["xlsx"])


# ---------------- CLEAN FUNCTION ----------------
def clean(text):
    return str(text).lower().strip()


# ---------------- MAIN ----------------
if cost_file and sales_file:

    try:
        # -------- LOAD COST FILE --------
        cost_df = pd.read_excel(cost_file)
        cost_df.columns = cost_df.columns.str.strip()

        cost_df = cost_df.rename(columns={
            cost_df.columns[0]: "Product",
            cost_df.columns[1]: "Cost Price"
        })

        cost_df["Product"] = cost_df["Product"].apply(clean)
        cost_df["Cost Price"] = pd.to_numeric(cost_df["Cost Price"], errors="coerce")

        # -------- LOAD SALES FILE --------
        sales_df = pd.read_excel(sales_file)
        sales_df.columns = sales_df.columns.str.strip()

        required_cols = ["Party", "Product", "Qty", "Rate"]

        for col in required_cols:
            if col not in sales_df.columns:
                st.error(f"❌ Sales file must contain column: {col}")
                st.stop()

        sales_df["Product"] = sales_df["Product"].apply(clean)
        sales_df["Qty"] = pd.to_numeric(sales_df["Qty"], errors="coerce")
        sales_df["Rate"] = pd.to_numeric(sales_df["Rate"], errors="coerce")

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

        # -------- ADJUSTMENT (GOODS FORM) --------
        df["Adjustment Qty"] = df.apply(
            lambda row: row["Total Loss"] / row["Cost Price"]
            if row["Cost Price"] > 0 else 0,
            axis=1
        )

        # -------- FILTER ONLY LOSS --------
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

        # -------- PARTY SUMMARY --------
        party = df.groupby("Party")[["Total Loss", "Adjustment Qty"]].sum().reset_index()

        st.subheader("📊 Party-wise Summary")
        st.dataframe(party)

        st.success(f"💰 Total Loss: ₹{df['Total Loss'].sum():.2f}")

    except Exception as e:
        st.error(f"❌ Error: {e}")
