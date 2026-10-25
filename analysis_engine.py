
import re
from io import BytesIO
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


EXPECTED = {
    "Item_Master": [
        "SKU", "Item Name", "Category", "Master Pack Qty", "Unit Cost (Rs)",
        "Alternate Item (name)", "Alternate Flag", "Status"
    ],
    "Stock_Aging": [
        "SKU", "Qty 0-30 days", "Qty 31-60 days", "Qty 61-90 days",
        "Qty 91-180 days", "Qty 180+ days"
    ],
    "Sales_Lines": [
        "Month", "CustomerID", "CustomerName", "Industry", "SKU", "Qty", "Value (Rs)"
    ],
    "Customers": [
        "CustomerID", "CustomerName", "Industry", "Area"
    ],
}

STOCK_COLS = [
    "Qty 0-30 days", "Qty 31-60 days", "Qty 61-90 days",
    "Qty 91-180 days", "Qty 180+ days"
]


def normalize_sku(value):
    if pd.isna(value):
        return pd.NA
    return str(value).strip().upper()


def normalize_text(value):
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


def normalize_month(value):
    if pd.isna(value):
        return pd.NaT
    return pd.to_datetime(str(value).strip(), errors="coerce").to_period("M")


def _match_sheet(df: pd.DataFrame) -> str | None:
    cols = set(df.columns)
    matches = []
    for name, required in EXPECTED.items():
        if set(required).issubset(cols):
            matches.append(name)
    return matches[0] if len(matches) == 1 else None


def load_uploaded_files(uploaded_files) -> Tuple[Dict[str, pd.DataFrame], List[dict]]:
    """
    Accepts either:
      - one workbook containing all four sheets, or
      - four separate Excel files.
    Sheets/files are identified by their required column sets, not filenames.
    """
    found = {}
    ignored = []

    for uploaded in uploaded_files:
        raw = uploaded.getvalue()
        workbook = pd.ExcelFile(BytesIO(raw))

        for sheet_name in workbook.sheet_names:
            df = pd.read_excel(BytesIO(raw), sheet_name=sheet_name)
            kind = _match_sheet(df)
            if kind:
                if kind in found:
                    raise ValueError(f"More than one {kind} sheet/file was uploaded.")
                found[kind] = df.copy()
            else:
                ignored.append({
                    "Issue": "Unrecognized workbook sheet",
                    "Severity": "Info",
                    "Detail": f"{uploaded.name} → {sheet_name} was ignored because its columns did not match a required dataset.",
                    "Handling": "Ignored non-data sheet/file.",
                    "Source fix": "Keep explanatory sheets separate from the four data exports."
                })

    missing = [k for k in EXPECTED if k not in found]
    if missing:
        raise ValueError(
            "Missing required dataset(s): " + ", ".join(missing) +
            ". Upload the workbook containing all four sheets or the four separate Excel files."
        )

    return found, ignored


def _clean_item_master(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ["SKU", "Item Name", "Category", "Alternate Item (name)", "Alternate Flag", "Status"]:
        df[col] = df[col].map(normalize_text)
    df["SKU"] = df["SKU"].map(normalize_sku)
    df["Alternate Flag"] = df["Alternate Flag"].str.upper()
    df["Status"] = df["Status"].str.upper()
    df["AltNameNorm"] = df["Alternate Item (name)"].str.replace(r"\s+", " ", regex=True).str.lower().str.strip()
    df["ItemNameNorm"] = df["Item Name"].str.replace(r"\s+", " ", regex=True).str.lower().str.strip()
    df["Master Pack Qty"] = pd.to_numeric(df["Master Pack Qty"], errors="coerce")
    df["Unit Cost (Rs)"] = pd.to_numeric(df["Unit Cost (Rs)"], errors="coerce")
    return df


def _clean_stock(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["SKU"] = df["SKU"].map(normalize_sku)
    for col in STOCK_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def _clean_sales(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    df = df.copy()
    raw_sku = df["SKU"].astype(str)
    sku_changed_rows = int(
        ((raw_sku != raw_sku.str.strip()) | (raw_sku != raw_sku.str.upper())).sum()
    )

    raw_month = df["Month"].astype(str).str.strip()
    normalized_month = raw_month.map(normalize_month)
    month_changed_rows = int(
        (raw_month.str.lower() != normalized_month.astype("string").str.lower()).sum()
    )

    for col in ["CustomerID", "CustomerName", "Industry"]:
        df[col] = df[col].map(normalize_text)
    df["SKU"] = df["SKU"].map(normalize_sku)
    df["Month"] = normalized_month
    df["Qty"] = pd.to_numeric(df["Qty"], errors="coerce")
    df["Value (Rs)"] = pd.to_numeric(df["Value (Rs)"], errors="coerce")

    key_cols = ["Month", "CustomerID", "CustomerName", "Industry", "SKU", "Qty", "Value (Rs)"]
    before = len(df)
    duplicate_mask = df.duplicated(subset=key_cols, keep=False)
    duplicate_groups = int(df.loc[duplicate_mask].groupby(key_cols, dropna=False).ngroups)
    df = df.drop_duplicates(subset=key_cols, keep="first").copy()
    duplicate_rows_removed = before - len(df)

    return df, {
        "sku_changed_rows": sku_changed_rows,
        "month_changed_rows": month_changed_rows,
        "duplicate_groups": duplicate_groups,
        "duplicate_rows_removed": duplicate_rows_removed,
    }


def _clean_customers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ["CustomerID", "CustomerName", "Industry", "Area"]:
        df[col] = df[col].map(normalize_text)
    return df


def _build_switch_map(item: pd.DataFrame) -> Tuple[dict, List[dict]]:
    name_to_sku = dict(zip(item["ItemNameNorm"], item["SKU"]))
    switch_map = {}
    issues = []

    for _, row in item.iterrows():
        flag = row["Alternate Flag"]
        alt_name = row["AltNameNorm"]

        if flag == "SWITCH":
            new_sku = name_to_sku.get(alt_name)
            if new_sku:
                switch_map[row["SKU"]] = new_sku
            else:
                issues.append({
                    "Issue": "Unresolved SWITCH relationship",
                    "Severity": "High",
                    "Detail": f"{row['SKU']} is marked SWITCH but alternate item '{row['Alternate Item (name)']}' does not map to an Item_Master SKU.",
                    "Handling": "Did not merge the unresolved relationship.",
                    "Source fix": "Use the exact replacement item name/SKU in Item_Master."
                })
        elif alt_name:
            issues.append({
                "Issue": "Alternate item present without SWITCH flag",
                "Severity": "Medium",
                "Detail": f"{row['SKU']} has alternate item '{row['Alternate Item (name)']}' but flag is '{flag or 'blank'}'.",
                "Handling": "No merge performed because the case rules only require merging when Alternate Flag = SWITCH.",
                "Source fix": "Confirm whether the relationship is a true pack-size switch and populate the correct flag."
            })

    return switch_map, issues


def _canonical_mapper(switch_map: dict):
    def canonical(sku):
        if pd.isna(sku):
            return pd.NA
        current = sku
        seen = set()
        while current in switch_map and current not in seen:
            seen.add(current)
            current = switch_map[current]
        return current
    return canonical


def run_analysis(datasets: Dict[str, pd.DataFrame]):
    item_raw = datasets["Item_Master"].copy()
    stock_raw = datasets["Stock_Aging"].copy()
    sales_raw = datasets["Sales_Lines"].copy()
    customers_raw = datasets["Customers"].copy()

    item = _clean_item_master(item_raw)
    stock = _clean_stock(stock_raw)
    sales, sales_meta = _clean_sales(sales_raw)
    customers = _clean_customers(customers_raw)

    quality = []

    if sales_meta["sku_changed_rows"]:
        quality.append({
            "Issue": "Inconsistent SKU case/spacing in sales",
            "Severity": "Medium",
            "Detail": f"{sales_meta['sku_changed_rows']} sales rows required SKU normalization.",
            "Handling": "Trimmed whitespace and converted SKUs to uppercase before joins.",
            "Source fix": "Export a consistent uppercase/trimmed SKU key from the source system."
        })

    if sales_meta["month_changed_rows"]:
        quality.append({
            "Issue": "Inconsistent month format in sales",
            "Severity": "Low",
            "Detail": f"{sales_meta['month_changed_rows']} sales rows required month-format normalization.",
            "Handling": "Converted all month values to YYYY-MM internally.",
            "Source fix": "Export one consistent month/date format."
        })

    if sales_meta["duplicate_rows_removed"]:
        quality.append({
            "Issue": "Duplicate sales transactions",
            "Severity": "High",
            "Detail": f"{sales_meta['duplicate_groups']} duplicate groups found; {sales_meta['duplicate_rows_removed']} extra rows removed.",
            "Handling": "Kept one copy of each exact normalized transaction.",
            "Source fix": "Remove duplicate transaction exports at source or provide a unique transaction ID."
        })

    missing_industry = customers.loc[customers["Industry"].eq(""), "CustomerID"].tolist()
    if missing_industry:
        quality.append({
            "Issue": "Missing customer industry",
            "Severity": "Medium",
            "Detail": f"{len(missing_industry)} customer(s) have no industry recorded: {', '.join(missing_industry)}.",
            "Handling": "Customers with no industry are not eligible for Bucket 2, per the case rule.",
            "Source fix": "Make Industry mandatory in the customer master."
        })

    # Check for customer industry mismatches between Sales_Lines and Customers.
    sales_customer_check = sales.merge(
        customers[["CustomerID", "Industry"]].rename(columns={"Industry": "MasterIndustry"}),
        on="CustomerID", how="left"
    )
    mismatch = sales_customer_check[
        sales_customer_check["Industry"].fillna("").str.strip()
        != sales_customer_check["MasterIndustry"].fillna("").str.strip()
    ]
    if not mismatch.empty:
        quality.append({
            "Issue": "Customer industry mismatch between sales and master",
            "Severity": "High",
            "Detail": f"{len(mismatch)} sales rows have an industry different from the customer master.",
            "Handling": "Customer master is used as the authoritative industry for targeting.",
            "Source fix": "Use one customer master key and synchronize industry values across exports."
        })

    switch_map, switch_issues = _build_switch_map(item)
    quality.extend(switch_issues)

    canonical = _canonical_mapper(switch_map)
    item["CanonicalSKU"] = item["SKU"].map(canonical)
    stock["CanonicalSKU"] = stock["SKU"].map(canonical)
    sales["CanonicalSKU"] = sales["SKU"].map(canonical)

    # Inactive stock warning.
    inactive_skus = set(item.loc[item["Status"].eq("INACTIVE"), "SKU"])
    inactive_stock = stock[stock["SKU"].isin(inactive_skus)].copy()
    if not inactive_stock.empty:
        inactive_stock["TotalStock"] = inactive_stock[STOCK_COLS].sum(axis=1)
        inactive_stock = inactive_stock[inactive_stock["TotalStock"] > 0]
    if not inactive_stock.empty:
        for _, r in inactive_stock.iterrows():
            quality.append({
                "Issue": "Inactive SKU still holds stock",
                "Severity": "High",
                "Detail": f"{r['SKU']} is inactive but has {int(r['TotalStock']):,} units in stock.",
                "Handling": "Excluded inactive SKU from the main analysis and retained this warning.",
                "Source fix": "Clear inactive inventory or correct the item status in the source master."
            })

    # Active item metadata: report switched pairs under the new SKU.
    active = item[item["Status"].eq("ACTIVE")].copy()
    canonical_rows = active[active["SKU"].eq(active["CanonicalSKU"])].copy()
    canonical_rows = canonical_rows.drop_duplicates("CanonicalSKU")

    # Track source SKUs for switch groups.
    source_groups = (
        active.groupby("CanonicalSKU")["SKU"]
        .apply(lambda s: ", ".join(sorted(set(s))))
        .rename("Source SKUs")
        .reset_index()
    )

    stock_agg = stock.groupby("CanonicalSKU", as_index=False)[STOCK_COLS].sum()
    stock_agg["Total Stock"] = stock_agg[STOCK_COLS].sum(axis=1)
    stock_agg["Aged Qty"] = stock_agg["Qty 91-180 days"] + stock_agg["Qty 180+ days"]

    sales_agg = sales.groupby("CanonicalSKU", as_index=False).agg(
        SalesQty=("Qty", "sum"),
        SalesValue=("Value (Rs)", "sum"),
    )

    analysis = (
        canonical_rows[
            ["CanonicalSKU", "SKU", "Item Name", "Category", "Master Pack Qty", "Unit Cost (Rs)"]
        ]
        .merge(source_groups, on="CanonicalSKU", how="left")
        .merge(stock_agg, on="CanonicalSKU", how="left")
        .merge(sales_agg, on="CanonicalSKU", how="left")
    )

    for col in ["Total Stock", "Aged Qty", "SalesQty", "SalesValue"] + STOCK_COLS:
        if col in analysis.columns:
            analysis[col] = pd.to_numeric(analysis[col], errors="coerce").fillna(0)

    analysis["Avg Monthly Sales"] = analysis["SalesQty"] / 6
    analysis["Months to Clear"] = np.where(
        analysis["Avg Monthly Sales"] > 0,
        analysis["Total Stock"] / analysis["Avg Monthly Sales"],
        np.inf,
    )
    analysis["Aged Value"] = analysis["Aged Qty"] * analysis["Unit Cost (Rs)"]

    def classify(row):
        # R5 ordering is intentional.
        if row["SalesQty"] < row["Master Pack Qty"]:
            return "Red List"
        if row["Aged Qty"] == 0 or row["Months to Clear"] < 3:
            return "No Action"
        return "Push"

    analysis["Class"] = analysis.apply(classify, axis=1)

    # Customer eligibility.
    customer_totals = sales.groupby("CustomerID", as_index=False)["Value (Rs)"].sum()
    customer_totals = customer_totals.rename(columns={"Value (Rs)": "6M Purchase Value"})
    customers_enriched = customers.merge(customer_totals, on="CustomerID", how="left")
    customers_enriched["6M Purchase Value"] = customers_enriched["6M Purchase Value"].fillna(0)
    eligible = customers_enriched[customers_enriched["6M Purchase Value"] > 100000].copy()

    # Industry from customer master is used for targeting.
    sales_with_customer = sales.merge(
        customers[["CustomerID", "Industry"]].rename(columns={"Industry": "CustomerMasterIndustry"}),
        on="CustomerID", how="left"
    )
    sales_with_customer["CustomerMasterIndustry"] = sales_with_customer["CustomerMasterIndustry"].fillna("")

    def make_targets(canonical_sku):
        item_row = analysis.loc[analysis["CanonicalSKU"].eq(canonical_sku)].iloc[0]
        category = item_row["Category"]

        category_skus = set(analysis.loc[analysis["Category"].eq(category), "CanonicalSKU"])

        item_sales = sales_with_customer[sales_with_customer["CanonicalSKU"].eq(canonical_sku)]
        buyer_ids = set(item_sales["CustomerID"].dropna())
        buyer_industries = {
            x for x in item_sales["CustomerMasterIndustry"].astype(str).str.strip()
            if x
        }

        targets = []
        for _, customer in eligible.iterrows():
            cid = customer["CustomerID"]
            industry = str(customer["Industry"]).strip()

            if cid in buyer_ids:
                bucket = 1
                bucket_label = "Bought Before"
            elif industry and industry in buyer_industries:
                bucket = 2
                bucket_label = "Similar Business"
            else:
                bought_same_category = not sales[
                    (sales["CustomerID"].eq(cid))
                    & (sales["CanonicalSKU"].isin(category_skus))
                ].empty
                if not bought_same_category:
                    continue
                bucket = 3
                bucket_label = "Same Category"

            targets.append({
                "SKU": item_row["SKU"],
                "CustomerID": cid,
                "CustomerName": customer["CustomerName"],
                "Industry": customer["Industry"],
                "Area": customer["Area"],
                "Bucket": bucket,
                "Bucket Label": bucket_label,
                "6M Purchase Value": customer["6M Purchase Value"],
            })

        if not targets:
            return pd.DataFrame(columns=[
                "SKU", "CustomerID", "CustomerName", "Industry", "Area",
                "Bucket", "Bucket Label", "6M Purchase Value"
            ])

        return pd.DataFrame(targets).sort_values(
            ["Bucket", "6M Purchase Value", "CustomerID"],
            ascending=[True, False, True]
        ).reset_index(drop=True)

    push_skus = analysis.loc[analysis["Class"].eq("Push"), "CanonicalSKU"].tolist()
    target_frames = [make_targets(sku) for sku in push_skus]
    target_frames = [x for x in target_frames if not x.empty]
    targets = pd.concat(target_frames, ignore_index=True) if target_frames else pd.DataFrame()

    # Friendly display names and rounding.
    analysis["Months to Clear"] = analysis["Months to Clear"].replace(np.inf, np.nan)
    analysis = analysis.sort_values(["Class", "Aged Value"], ascending=[True, False]).reset_index(drop=True)

    summary = {
        "Red List": int((analysis["Class"] == "Red List").sum()),
        "No Action": int((analysis["Class"] == "No Action").sum()),
        "Push": int((analysis["Class"] == "Push").sum()),
        "Push Aged Value": float(analysis.loc[analysis["Class"] == "Push", "Aged Value"].sum()),
    }

    return {
        "analysis": analysis,
        "targets": targets,
        "quality": pd.DataFrame(quality),
        "summary": summary,
        "inactive_stock": inactive_stock,
        "cleaned_sales": sales,
        "customers": customers,
        "item_master": item,
        "switch_map": switch_map,
    }


def export_results(results) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        analysis = results["analysis"].copy()
        analysis.to_excel(writer, sheet_name="Item Analysis", index=False)

        push = analysis[analysis["Class"].eq("Push")].copy()
        push = push.sort_values("Aged Value", ascending=False)
        push.to_excel(writer, sheet_name="Push Items", index=False)

        red = analysis[analysis["Class"].eq("Red List")].copy()
        red.to_excel(writer, sheet_name="Red List", index=False)

        targets = results["targets"].copy()
        targets.to_excel(writer, sheet_name="Customer Targets", index=False)

        quality = results["quality"].copy()
        quality.to_excel(writer, sheet_name="Data Quality", index=False)

    output.seek(0)
    return output.getvalue()
