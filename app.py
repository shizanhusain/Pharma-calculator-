import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup

st.title("💊 Pharma Margin Analyzer (HTML Supported)")

cost_file = st.file_uploader("Upload Product Cost File", type=["xlsx"])
html_file = st.file_uploader("Upload Sale Report (HTML)", type=["html"])

tax = st.number_input("Tax %", value=5.0)/100
margin = st.number_input("Margin %", value=10.0)/100

def extract_html_data(html):
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n")
    lines = text.split("\n")

    data = []
    current_party = None

    for line in lines:
        line = line.strip()

        # Detect PARTY (ALL CAPS)
        if line.isupper() and "TOTAL" not in line and len(line) > 5:
            current_party = line

        parts = line.split()

        # Detect product rows
        if len(parts) >= 3:
            try:
                qty = int(parts[-4])
                rate = float(parts[-2])

                product = " ".join(parts[:-4])

                data.append({
                    "Party": current_party,
                    "Product": product,
                    "Quantity": qty,
                    "Selling Price": rate
                })
            except:
                continue

    return pd.DataFrame(data)

if cost_file and html_file:

    cost_df = pd.read_excel(cost_file)
    # Automatically detect correct column
cost_df.columns = cost_df.columns.str.strip()

if "Product" not in cost_df.columns:
    # Try to find similar column
    for col in cost_df.columns:
        if "product" in col.lower() or "item" in col.lower() or "name" in col.lower():
            cost_df.rename(columns={col: "Product"}, inplace=True)
            break

cost_df["Product"] = cost_df["Product"].astype(str).str.lower().str.strip()

    html_data = html_file.read()
    bill_df = extract_html_data(html_data)
    bill_df["Product"] = bill_df["Product"].str.lower().str.strip()

    data = bill_df.merge(cost_df, on="Product", how="left")

    data["Cost After Tax"] = data["Cost Price"]*(1+tax)
    data["Min Selling"] = data["Cost After Tax"]*(1+margin)

    data["Loss per unit"] = data["Min Selling"] - data["Selling Price"]
    data["Loss per unit"] = data["Loss per unit"].apply(lambda x: x if x>0 else 0)

    data["Total Loss"] = data["Loss per unit"] * data["Quantity"]
    data["Adjustment Units"] = data["Total Loss"] / data["Cost Price"]

    data = data[data["Total Loss"] > 0]

    st.subheader("📋 Detailed Loss")
    st.dataframe(data)

    st.subheader("📊 Party-wise Loss")
    party = data.groupby("Party")[["Total Loss","Adjustment Units"]].sum().reset_index()
    st.dataframe(party)

    st.success(f"💰 Total Loss: ₹{data['Total Loss'].sum():.2f}")
