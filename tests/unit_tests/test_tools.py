import pytest
import pandas as pd
from unittest.mock import patch
import sys
from pathlib import Path

# Add project root to path so we can import tools
sys.path.append(str(Path(__file__).parent.parent))
import tools

# --- Fixtures ---

@pytest.fixture
def mock_marketing_df():
    """Returns a mock dataframe representing marketing campaigns."""
    return pd.DataFrame([
        {
            "Campaign ID": "CMP-1",
            "Campaign Name": "Summer Splash 2024",
            "Channel": "Facebook",
            "Budget Allocated": 10000,
            "Amount Spent": 9500
        },
        {
            "Campaign ID": "CMP-2",
            "Campaign Name": "Summer Mega Sale",
            "Channel": "Facebook",
            "Budget Allocated": 15000,
            "Amount Spent": 14000
        },
        {
            "Campaign ID": "CMP-3",
            "Campaign Name": "Winter Promo",
            "Channel": "LinkedIn",
            "Budget Allocated": 5000,
            "Amount Spent": 4000
        }
    ])

@pytest.fixture
def mock_real_estate_df():
    """Returns a mock dataframe representing real estate listings."""
    return pd.DataFrame([
        {
            "Listing ID": "LST-1",
            "Property Type": "House",
            "City": "Seattle",
            "State": "WA",
            "Bedrooms": 3,
            "List Price": 500000
        },
        {
            "Listing ID": "LST-2",
            "Property Type": "Condo",
            "City": "Boston",
            "State": "MA",
            "Bedrooms": 2,
            "List Price": 300000
        }
    ])

# --- Tests for query_data ---

@patch("tools._load")
def test_query_data_exact_match(mock_load, mock_marketing_df):
    mock_load.return_value = mock_marketing_df
    
    result = tools.query_data("marketing", filters={"Channel": "Facebook"})
    
    assert result["total_matching"] == 2
    assert result["rows"][0]["Campaign ID"] == "CMP-1"
    assert result["rows"][1]["Campaign ID"] == "CMP-2"

@patch("tools._load")
def test_query_data_numeric_operators(mock_load, mock_marketing_df):
    mock_load.return_value = mock_marketing_df
    
    # Test >= operator
    result = tools.query_data("marketing", filters={"Budget Allocated": ">=10000"})
    assert result["total_matching"] == 2
    
    # Test < operator
    result = tools.query_data("marketing", filters={"Budget Allocated": "<10000"})
    assert result["total_matching"] == 1
    assert result["rows"][0]["Campaign ID"] == "CMP-3"

# --- Tests for get_summary ---

@patch("tools._load")
def test_get_summary_group_by(mock_load, mock_marketing_df):
    mock_load.return_value = mock_marketing_df
    
    result = tools.get_summary("marketing", group_by="Channel", metric="sum")
    
    assert result["group_by"] == "Channel"
    assert result["metric"] == "sum"
    assert len(result["rows"]) == 2
    
    # Find Facebook sum
    fb_row = next(r for r in result["rows"] if r["Channel"] == "Facebook")
    assert fb_row["Budget Allocated"] == 25000

# --- Tests for insert_row ---

@patch("tools._save")
@patch("tools._load")
def test_insert_row_success(mock_load, mock_save, mock_real_estate_df):
    mock_load.return_value = mock_real_estate_df
    
    # Has all required fields: "Property Type", "City", "State", "List Price"
    new_row = {
        "Property Type": "Townhouse",
        "City": "Austin",
        "State": "TX",
        "List Price": 450000
    }
    
    result = tools.insert_row("real_estate", new_row)
    
    assert result["status"] == "inserted"
    assert result["id"] == "LST-3" # Auto-incremented ID
    
    # Verify save was called with the new dataframe size
    saved_df = mock_save.call_args[0][1]
    assert len(saved_df) == 3

@patch("tools._load")
def test_insert_row_missing_required_fields(mock_load, mock_real_estate_df):
    mock_load.return_value = mock_real_estate_df
    
    # Missing 'List Price'
    incomplete_row = {
        "Property Type": "Townhouse",
        "City": "Austin",
        "State": "TX"
    }
    
    result = tools.insert_row("real_estate", incomplete_row)
    
    assert "error" in result
    assert "Missing required fields" in result["error"]
    assert "List Price" in result["error"]

# --- Tests for update_rows ---

@patch("tools._load")
def test_update_rows_ambiguity_guardrail(mock_load, mock_marketing_df):
    mock_load.return_value = mock_marketing_df
    
    # "Facebook" matches CMP-1 and CMP-2
    result = tools.update_rows(
        "marketing", 
        filters={"Channel": "Facebook"}, 
        updates={"Budget Allocated": 20000}
    )
    
    assert "error" in result
    assert "Ambiguity Error" in result["error"]

@patch("tools._save")
@patch("tools._load")
def test_update_rows_exact_match(mock_load, mock_save, mock_marketing_df):
    mock_load.return_value = mock_marketing_df
    
    result = tools.update_rows(
        "marketing", 
        filters={"Campaign ID": "CMP-1"}, 
        updates={"Budget Allocated": 20000}
    )
    
    assert result["status"] == "updated"
    assert result["id"] == "CMP-1"
    
    # Verify the dataframe was updated correctly
    saved_df = mock_save.call_args[0][1]
    assert saved_df.loc[saved_df["Campaign ID"] == "CMP-1", "Budget Allocated"].iloc[0] == 20000

# --- Tests for delete_rows ---

@patch("tools._load")
def test_delete_rows_ambiguity_guardrail(mock_load, mock_marketing_df):
    mock_load.return_value = mock_marketing_df
    
    # "Facebook" matches CMP-1 and CMP-2
    result = tools.delete_rows("marketing", filters={"Channel": "Facebook"})
    
    assert "error" in result
    assert "Ambiguity Error" in result["error"]

@patch("tools._save")
@patch("tools._load")
def test_delete_rows_exact_match(mock_load, mock_save, mock_marketing_df):
    mock_load.return_value = mock_marketing_df
    
    result = tools.delete_rows("marketing", filters={"Campaign ID": "CMP-1"})
    
    assert result["status"] == "deleted"
    
    # Verify the row was removed
    saved_df = mock_save.call_args[0][1]
    assert len(saved_df) == 2
    assert "CMP-1" not in saved_df["Campaign ID"].values
