
import io
import pandas as pd
import streamlit as st

from analysis_engine import load_uploaded_files, run_analysis, export_results


st.set_page_config(
    page_title="Company X | Slow Stock Action Tool",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Simple styling for a clean business dashboard.
st.markdown(
    """
    <style>
    .main-title {font-size: 2.0rem; font-weight: 700; margin-bottom: 0.2rem;}
    .sub-title {color: #666; margin-bottom: 1.2rem;}
    .small-note {color: #666; font-size: 0.85rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def money(value):
    if pd.isna(value):
        return "—"
    return f"₹{value:,.0f}"


def integer(value):
    if pd.isna(value):
        return "—"
    return f"{value:,.0f}"


def render_dashboard(results):
    summary = results["summary"]
    analysis = results["analysis"]

    st.markdown('<div class="main-title">Slow Stock Action Dashboard</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-title">Monthly review: identify slow stock and give sales a ranked customer call list.</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔴 Red List", summary["Red List"])
    c2.metric("🟢 No Action", summary["No Action"])
    c3.metric("🟠 Push", summary["Push"])
    c4.metric("Push Aged Value", money(summary["Push Aged Value"]))

    st.divider()

    st.subheader("Top 10 Push Items by Aged Value")
    top10 = (
        analysis[analysis["Class"].eq("Push")]
        .sort_values("Aged Value", ascending=False)
        .head(10)
        [[
            "SKU", "Item Name", "Category", "Total Stock",
            "Aged Qty", "Aged Value", "Avg Monthly Sales",
            "Months to Clear", "Source SKUs"
        ]]
        .copy()
    )
    if top10.empty:
        st.info("There are no Push items in this run.")
    else:
        st.dataframe(
            top10.style.format({
                "Total Stock": "{:,.0f}",
                "Aged Qty": "{:,.0f}",
                "Aged Value": "₹{:,.0f}",
                "Avg Monthly Sales": "{:,.1f}",
                "Months to Clear": "{:,.2f}",
            }),
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Class Distribution")
    class_counts = analysis["Class"].value_counts().reindex(
        ["Red List", "No Action", "Push"], fill_value=0
    )
    st.bar_chart(class_counts)


def render_quality(results):
    st.subheader("Data Quality & Handling")
    quality = results["quality"]

    if quality.empty:
        st.success("No data-quality issues were detected.")
        return

    st.caption(
        "The case expects the tool to identify data problems and explain how they are handled."
    )

    display = quality.copy()
    st.dataframe(display, use_container_width=True, hide_index=True)

    inactive = results["inactive_stock"]
    if not inactive.empty:
        st.warning(
            "Inactive stock warning: "
            + ", ".join(
                f"{r['SKU']} ({int(r['TotalStock']):,} units)"
                for _, r in inactive.iterrows()
            )
        )


def render_items(results):
    analysis = results["analysis"].copy()

    st.subheader("Item Analysis")

    col1, col2 = st.columns(2)
    classes = ["All"] + ["Red List", "No Action", "Push"]
    selected_class = col1.selectbox("Filter by class", classes)

    categories = ["All"] + sorted(analysis["Category"].dropna().unique().tolist())
    selected_category = col2.selectbox("Filter by category", categories)

    if selected_class != "All":
        analysis = analysis[analysis["Class"].eq(selected_class)]
    if selected_category != "All":
        analysis = analysis[analysis["Category"].eq(selected_category)]

    display_cols = [
        "SKU", "Item Name", "Category", "Source SKUs",
        "Total Stock", "Aged Qty", "Aged Value",
        "SalesQty", "Avg Monthly Sales", "Months to Clear",
        "Master Pack Qty", "Unit Cost (Rs)", "Class"
    ]

    st.caption(f"{len(analysis):,} item(s) shown.")
    st.dataframe(
        analysis[display_cols].style.format({
            "Total Stock": "{:,.0f}",
            "Aged Qty": "{:,.0f}",
            "Aged Value": "₹{:,.0f}",
            "SalesQty": "{:,.0f}",
            "Avg Monthly Sales": "{:,.1f}",
            "Months to Clear": "{:,.2f}",
            "Master Pack Qty": "{:,.0f}",
            "Unit Cost (Rs)": "₹{:,.2f}",
        }),
        use_container_width=True,
        hide_index=True,
    )


def render_targets(results):
    analysis = results["analysis"]
    targets = results["targets"]

    st.subheader("Customer Targets")
    st.caption(
        "Only Push items are shown. Customers must have more than ₹1,00,000 "
        "in six-month purchases and are placed into the first applicable bucket."
    )

    push = analysis[analysis["Class"].eq("Push")].sort_values("Aged Value", ascending=False)

    if push.empty:
        st.info("No Push items in this run.")
        return

    sku_options = push["SKU"].tolist()
    selected_sku = st.selectbox(
        "Select a Push item",
        sku_options,
        format_func=lambda x: (
            f"{x} — "
            f"{analysis.loc[analysis['SKU'].eq(x), 'Item Name'].iloc[0]}"
        ),
    )

    selected = targets[targets["SKU"].eq(selected_sku)].copy()

    if selected.empty:
        st.info("No eligible customer targets were found for this item.")
        return

    st.markdown(f"### Customers to call for **{selected_sku}**")

    b1 = int((selected["Bucket"] == 1).sum())
    b2 = int((selected["Bucket"] == 2).sum())
    b3 = int((selected["Bucket"] == 3).sum())
    a, b, c = st.columns(3)
    a.metric("Bucket 1 — Bought Before", b1)
    b.metric("Bucket 2 — Similar Business", b2)
    c.metric("Bucket 3 — Same Category", b3)

    st.dataframe(
        selected[
            [
                "CustomerID", "CustomerName", "Industry", "Area",
                "Bucket", "Bucket Label", "6M Purchase Value"
            ]
        ].style.format({"6M Purchase Value": "₹{:,.0f}"}),
        use_container_width=True,
        hide_index=True,
    )


def render_export(results):
    st.subheader("Export Results")
    st.write(
        "Download the cleaned analysis, Push items, Red List, customer targets, "
        "and data-quality findings as one Excel workbook."
    )

    data = export_results(results)
    st.download_button(
        label="⬇ Download Excel Results",
        data=data,
        file_name="company_x_slow_stock_results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=False,
    )


st.markdown('<div class="main-title">Company X — Slow Stock Action Tool</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Upload the monthly exports once. The tool cleans the data, applies the case rules, '
    'and produces a sales-ready action list.</div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("1. Upload monthly data")
    uploaded_files = st.file_uploader(
        "Upload either one workbook with all 4 sheets or the 4 separate Excel files.",
        type=["xlsx"],
        accept_multiple_files=True,
    )

    st.caption(
        "Required datasets: Item_Master, Stock_Aging, Sales_Lines and Customers."
    )

    run_button = st.button("▶ Run Analysis", type="primary", use_container_width=True)

    st.divider()
    st.markdown("**Business rules used**")
    st.markdown(
        """
        - SWITCH SKUs are combined under the new SKU.
        - Inactive items are excluded.
        - Aged stock = 91–180 + 180+ days.
        - Red List is checked before No Action and Push.
        - Push customers must exceed ₹1,00,000 in 6-month purchases.
        - Customer buckets are 1 → 2 → 3.
        """
    )

if run_button:
    if not uploaded_files:
        st.error("Please upload the data files first.")
        st.stop()

    try:
        with st.spinner("Loading, cleaning and analysing the data..."):
            datasets, ignored = load_uploaded_files(uploaded_files)
            results = run_analysis(datasets)

        st.session_state["results"] = results
        st.session_state["ignored"] = ignored
        st.success("Analysis completed successfully.")

    except Exception as exc:
        st.error(f"Could not run the analysis: {exc}")
        st.stop()

if "results" not in st.session_state:
    st.info(
        "Upload the case-study Excel data in the sidebar and click **Run Analysis** to begin."
    )

    st.markdown("### What this tool does")
    col1, col2, col3 = st.columns(3)
    col1.markdown("**1. Validate**\n\nChecks sheets, SKUs, months, duplicates and inactive stock.")
    col2.markdown("**2. Analyse**\n\nApplies the exact slow-stock and customer-target rules.")
    col3.markdown("**3. Action**\n\nShows Push items and a ranked customer call list.")
else:
    results = st.session_state["results"]

    ignored = st.session_state.get("ignored", [])
    if ignored:
        with st.expander("Ignored workbook sheets/files"):
            st.dataframe(pd.DataFrame(ignored), use_container_width=True, hide_index=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["📊 Dashboard", "🔎 Data Quality", "📦 Item Analysis", "📞 Customer Targets", "⬇ Export"]
    )

    with tab1:
        render_dashboard(results)

    with tab2:
        render_quality(results)

    with tab3:
        render_items(results)

    with tab4:
        render_targets(results)

    with tab5:
        render_export(results)
