"""
tools.py — CRUD operations on the two Excel datasets.

This layer handles pure Python/Pandas logic and enforces strict Tool-Level safety 
guardrails independently of the LLM.

Supported Datasets: "real_estate" | "marketing"
"""

import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

FILES = {
    "real_estate": DATA_DIR / "real_estate_listings.xlsx",
    "marketing":   DATA_DIR / "marketing_campaigns.xlsx",
}

ID_COLUMNS = {
    "real_estate": "Listing ID",
    "marketing":   "Campaign ID",
}

# Required fields for Tool-Level validation during inserts
REQUIRED_FIELDS = {
    "real_estate": ["Property Type", "City", "State", "List Price"],
    "marketing":   ["Campaign Name", "Channel", "Budget Allocated"],
}

# ── helpers ──────────────────────────────────────────────────────────────────

def _load(dataset: str) -> pd.DataFrame:
    return pd.read_excel(FILES[dataset])

def _save(dataset: str, df: pd.DataFrame) -> None:
    df.to_excel(FILES[dataset], index=False)

def _cast_value(col_series: pd.Series, val: any) -> any:
    """Casts a string value to match the pandas column's dtype."""
    if pd.isna(val):
        return val
    if pd.api.types.is_datetime64_any_dtype(col_series):
        return pd.to_datetime(val)
    if pd.api.types.is_numeric_dtype(col_series):
        try:
            f_val = float(val)
            if pd.api.types.is_integer_dtype(col_series) and f_val.is_integer():
                return int(f_val)
            return f_val
        except (ValueError, TypeError):
            pass
    return val

def _apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    for col, val in filters.items():
        if col not in df.columns:
            raise ValueError(f"Column '{col}' does not exist in dataset. Available columns: {list(df.columns)}")

        # Comparison operators (>, <, >=, <=, !=)
        if isinstance(val, str):
            if val[:2] in (">=", "<=", "!="):
                op, val_str = val[:2], val[2:]
                parsed_val = _cast_value(df[col], val_str)
                ops = {">=": "__ge__", "<=": "__le__", "!=": "__ne__"}
                df = df[getattr(df[col], ops[op])(parsed_val)]
                continue
            elif val[0] in (">", "<"):
                op, val_str = val[0], val[1:]
                parsed_val = _cast_value(df[col], val_str)
                df = df[df[col] > parsed_val] if op == ">" else df[df[col] < parsed_val]
                continue

        # Exact match or Contains
        parsed_val = _cast_value(df[col], val)
        if pd.api.types.is_datetime64_any_dtype(df[col]) or pd.api.types.is_numeric_dtype(df[col]):
            df = df[df[col] == parsed_val]
        else:
            # String columns: case-insensitive partial match
            df = df[df[col].astype(str).str.contains(str(val), case=False, na=False)]
    return df

# ── tools ─────────────────────────────────────────────────────────────────────

def query_data(dataset: str, filters: dict | None = None, limit: int = 20) -> dict:
    """
    Search and retrieve rows from a dataset.
    
    Args:
        dataset (str): "real_estate" or "marketing".
        filters (dict, optional): {column_name: value}. Supports operators like ">500", "<=10".
        limit (int): Max rows to return to avoid context overflow (default 20).
        
    Returns:
        dict: Total matching count, returned count, and the row data.
    """
    df = _load(dataset)

    if filters:
        # Validate columns first
        for col in filters.keys():
            if col not in df.columns:
                return {"error": f"Column '{col}' not found. Available: {list(df.columns)}"}
        df = _apply_filters(df, filters)

    total = len(df)
    return {
        "total_matching": total,
        "returned": min(limit, total),
        "columns": list(df.columns),
        "rows": df.head(limit).to_dict(orient="records"),
    }


def get_summary(dataset: str, filters: dict | None = None, group_by: str | None = None, metric: str = "mean") -> dict:
    """
    Return aggregate statistics for a dataset.
    
    Args:
        dataset (str): "real_estate" or "marketing".
        filters (dict, optional): {column_name: value}. Used to filter data BEFORE summarizing.
        group_by (str, optional): Column name to group results by (e.g., 'Channel').
        metric (str): Aggregation type: "count", "mean", "sum", "min", "max", "median".
        
    Returns:
        dict: The aggregated statistics.
    """
    df = _load(dataset)

    if filters:
        for col in filters.keys():
            if col not in df.columns:
                return {"error": f"Filter column '{col}' not found. Available: {list(df.columns)}"}
        df = _apply_filters(df, filters)

    numeric_cols = df.select_dtypes(include="number").columns.tolist()

    if group_by:
        if group_by not in df.columns:
            return {"error": f"Column '{group_by}' not found."}
        
        agg_cols = [c for c in numeric_cols if c != group_by]
        grp = df.groupby(group_by)[agg_cols]
        ops = {"count": grp.count, "mean": grp.mean, "sum": grp.sum,
               "min": grp.min, "max": grp.max, "median": grp.median}
        
        if metric not in ops:
            return {"error": f"Invalid metric '{metric}'. Use count, mean, sum, min, max, or median."}
            
        result = ops[metric]().reset_index()
        return {"group_by": group_by, "metric": metric,
                "rows": result.to_dict(orient="records")}

    summary_dict = df[numeric_cols].describe().round(2).to_dict()
    
    return {
        "dataset_name": dataset,
        "total_rows": len(df),
        "numeric_summary": summary_dict,
        "sample": df.head(10).to_dict(orient="records")
    }


def insert_row(dataset: str, row: dict) -> dict:
    """
    Insert a new row into a dataset. Enforces required fields.
    
    Args:
        dataset (str): "real_estate" or "marketing".
        row (dict): Column-value pairs for the new record.
        
    Returns:
        dict: Status and the generated ID.
    """
    df = _load(dataset)
    id_col = ID_COLUMNS[dataset]

    # Tool-Level Guardrail: Check required fields
    required = REQUIRED_FIELDS[dataset]
    missing = [f for f in required if f not in row]
    if missing:
        return {
            "error": f"Missing required fields: {missing}. "
                     f"Please ask the user to provide them before inserting."
        }

    # Cast incoming values to match dataframe schema
    casted_row = {}
    for col, val in row.items():
        if col in df.columns:
            try:
                casted_row[col] = _cast_value(df, col, val)
            except ValueError as e:
                return {"error": str(e)}
        else:
            casted_row[col] = val

    # Auto-generate ID if not provided
    if id_col not in casted_row:
        prefix = "LST" if dataset == "real_estate" else "CMP"
        existing = df[id_col].str.extract(r"(\d+)")[0].astype(float)
        next_id = int(existing.max()) + 1 if not existing.empty else 1
        casted_row[id_col] = f"{prefix}-{next_id}"

    new_df = pd.concat([df, pd.DataFrame([casted_row])], ignore_index=True)
    _save(dataset, new_df)
    return {"status": "inserted", "id": casted_row[id_col], "row": casted_row}


def update_rows(dataset: str, filters: dict, updates: dict) -> dict:
    """
    Update rows matching the filters. Fails if more than 1 row matches.
    
    Args:
        dataset (str): "real_estate" or "marketing".
        filters (dict): {column: value} to find the row.
        updates (dict): {column: new_value} to apply.
        
    Returns:
        dict: Success status or Ambiguity error.
    """
    df = _load(dataset)
    
    # Validate filter columns
    for col in filters.keys():
        if col not in df.columns:
            return {"error": f"Filter column '{col}' not found."}
            
    # Validate update columns
    for col in updates.keys():
        if col not in df.columns:
            return {"error": f"Update column '{col}' not found."}

    matched_df = _apply_filters(df, filters)
    match_count = len(matched_df)
    
    # Tool-Level Guardrail: Ambiguity Check
    if match_count == 0:
        return {"error": "No rows matched the filters."}
    if match_count > 1:
        return {
            "error": f"Ambiguity Error: {match_count} rows matched the filters. "
                     f"Please ask the user to clarify or provide an exact ID."
        }

    # Execute update exactly on the 1 matched row
    index_to_update = matched_df.index[0]
    for col, val in updates.items():
        df.loc[index_to_update, col] = _cast_value(df[col], val)

    _save(dataset, df)
    
    id_col = ID_COLUMNS[dataset]
    row_id = df.loc[index_to_update, id_col]
    return {"status": "updated", "id": row_id, "updated_fields": updates}


def delete_rows(dataset: str, filters: dict) -> dict:
    """
    Delete rows matching the filters. Fails if more than 1 row matches.
    
    Args:
        dataset (str): "real_estate" or "marketing".
        filters (dict): {column: value} to find the row to delete.
        
    Returns:
        dict: Success status or Ambiguity error.
    """
    df = _load(dataset)
    
    # Validate filter columns
    for col in filters.keys():
        if col not in df.columns:
            return {"error": f"Filter column '{col}' not found."}

    matched_df = _apply_filters(df, filters)
    match_count = len(matched_df)
    
    # Tool-Level Guardrail: Ambiguity Check
    if match_count == 0:
        return {"error": "No rows matched the filters."}
    if match_count > 1:
        return {
            "error": f"Ambiguity Error: {match_count} rows matched the filters. "
                     f"Please ask the user to clarify or provide an exact ID."
        }

    # Execute delete exactly on the 1 matched row
    df = df.drop(matched_df.index).reset_index(drop=True)
    _save(dataset, df)
    
    return {"status": "deleted", "deleted_count": 1}


# ── registry (used by the agent) ─────────────────────────────────────────────

TOOL_FUNCTIONS = {
    "query_data":  query_data,
    "get_summary": get_summary,
    "insert_row":  insert_row,
    "update_rows": update_rows,
    "delete_rows": delete_rows,
}
