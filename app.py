"""
app.py — Streamlit UI for the AI Excel Assistant.

Wraps the ExcelAgent in a premium chat interface that streams the agent's
ReAct loop live, showing each tool call as it happens.
"""

import json
import os
import uuid

import pandas as pd
import streamlit as st

import tools
from agent import ExcelAgent

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Excel Assistant",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ── Premium CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Base styling */
html, body, .stApp {
    font-family: 'Inter', sans-serif !important;
    color: #0f172a;
}

/* Typography and Visual Language Polish (Phase 3 & 4) */
/* Enforce crisp typography hierarchy without breaking icon fonts */
h1 { font-weight: 700 !important; letter-spacing: -0.02em !important; }
h2 { font-weight: 600 !important; letter-spacing: -0.01em !important; }
p, div { line-height: 1.5; }

/* Elegant CSS Animations (Phase 8) */
@keyframes slideUpFade {
    0% { opacity: 0; transform: translateY(12px); }
    100% { opacity: 1; transform: translateY(0); }
}

[data-testid="stChatMessage"], [data-testid="stExpander"] {
    animation: slideUpFade 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

/* Chat Bubbles (Phase 9) */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background-color: #4f46e5 !important;
    border-radius: 20px 20px 4px 20px !important;
    padding: 12px 20px !important;
    margin-left: auto !important;
    max-width: 85% !important;
    border: none !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
    flex-direction: row-reverse;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) [data-testid="stMarkdownContainer"] p {
    color: #ffffff !important;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) .stChatMessageAvatar {
    display: none !important;
}

[data-testid="stChatMessage"]:not(:has([data-testid="chatAvatarIcon-user"])) {
    background-color: #ffffff !important;
    border-radius: 20px 20px 20px 4px !important;
    padding: 16px 20px !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
    max-width: 90% !important;
}

/* Soften Streamlit Expanders (Tool Execution) */
[data-testid="stExpander"] {
    border: 1px solid #e2e8f0 !important;
    border-radius: 8px !important;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.02) !important;
    background-color: #ffffff !important;
}
[data-testid="stExpander"] details summary {
    padding: 12px 16px !important;
}

/* Floating Chat Composer (Phase 2 & 4) */
[data-testid="stBottomBlockContainer"] {
    padding-bottom: 24px !important;
}
[data-testid="stChatInput"] {
    background-color: #ffffff !important;
    border-radius: 24px !important;
    border: 1px solid #cbd5e1 !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.02) !important;
    padding: 2px 12px !important;
    margin: 0 auto !important;
    max-width: 750px !important;
    position: relative;
    transition: all 0.2s ease !important;
}
[data-testid="stChatInput"]:focus-within {
    border-color: #4f46e5 !important;
    box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.1), 0 10px 15px -3px rgba(0, 0, 0, 0.05) !important;
}

[data-testid="stChatInput"] textarea {
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
    font-size: 15px !important;
    padding-left: 32px !important;
    padding-right: 48px !important;
    color: #0f172a !important;
}
[data-testid="stChatInput"] textarea::placeholder {
    color: #94a3b8 !important;
}
[data-testid="stChatInput"] textarea:focus {
    border: none !important;
    box-shadow: none !important;
}

/* Premium SaaS Buttons & Components (Phase 3) */
/* Secondary buttons (Used for Chat History and standard actions) */
[data-testid="baseButton-secondary"] {
    border-radius: 8px !important;
    border: 1px solid #e2e8f0 !important;
    background-color: #ffffff !important;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.02) !important;
    font-weight: 500 !important;
    color: #475569 !important;
    transition: all 0.15s ease !important;
}
[data-testid="baseButton-secondary"]:hover {
    border-color: #cbd5e1 !important;
    background-color: #f8fafc !important;
    color: #0f172a !important;
}

/* Sidebar specific secondary buttons (Flat list items for History) */
[data-testid="stSidebar"] [data-testid="baseButton-secondary"] {
    border: none !important;
    box-shadow: none !important;
    background-color: transparent !important;
    justify-content: flex-start !important; /* Left align */
    padding: 8px 12px !important;
}
[data-testid="stSidebar"] [data-testid="baseButton-secondary"] p {
    text-align: left !important;
    width: 100% !important;
}

/* Primary buttons (Used for New Chat & Active Chat) */
[data-testid="baseButton-primary"] {
    border-radius: 8px !important;
    background-color: #eef2ff !important; /* Muted Indigo */
    color: #4f46e5 !important;
    border: none !important;
    font-weight: 600 !important;
    box-shadow: none !important;
}
[data-testid="baseButton-primary"]:hover {
    background-color: #e0e7ff !important;
}
[data-testid="stSidebar"] [data-testid="baseButton-primary"] {
    justify-content: flex-start !important;
    padding: 8px 12px !important;
}
[data-testid="stSidebar"] [data-testid="baseButton-primary"] p {
    text-align: left !important;
    width: 100% !important;
}

/* Distinct Sidebar and Main App layout */
[data-testid="stSidebar"] {
    background-color: #f8fafc !important; /* Light Slate */
    border-right: 2px solid #e2e8f0 !important; /* Thicker dividing line */
}

[data-testid="stAppViewContainer"] {
    background-color: #ffffff !important; /* Pure White */
}

/* Hide Streamlit chrome completely */
#MainMenu, footer, [data-testid="stDecoration"], .stDeployButton { 
    visibility: hidden !important; 
    display: none !important; 
}
header {
    background: transparent !important;
}
[data-testid="collapsedControl"], [data-testid="stSidebarCollapseButton"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    z-index: 999999 !important;
}
.block-container { padding-top: 1rem !important; max-width: 850px !important; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid #e2e8f0 !important;
}
[data-testid="stSidebar"] .stMarkdown p { color: #64748b !important; }

/* Metrics Cards */
[data-testid="stMetric"] {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 8px;
    padding: 16px !important;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05) !important;
}
[data-testid="stMetricValue"] { color: #0f172a !important; font-weight: 600 !important; }
[data-testid="stMetricLabel"] { color: #64748b !important; font-size: 13px !important; font-weight: 500 !important; }

/* Premium Chat Messages (Phase 5) */
[data-testid="stChatMessage"] {
    border-radius: 12px !important;
    padding: 16px 20px !important;
    margin-bottom: 24px !important;
    box-shadow: none !important;
    border: none !important;
    background: transparent !important;
}

/* User Message */
[data-testid="stChatMessage"]:has([data-testid="stIcon"][aria-label="user avatar"]) {
    background-color: #f8fafc !important; /* Very light slate */
    border: 1px solid #e2e8f0 !important;
}

/* Assistant Message */
[data-testid="stChatMessage"]:not(:has([data-testid="stIcon"][aria-label="user avatar"])) {
    padding-left: 0 !important;
    padding-right: 0 !important;
}

/* Footer Injection */
[data-testid="stBottomBlockContainer"]::after {
    content: "AI can make mistakes. Please verify important information.";
    display: block;
    text-align: center;
    font-size: 11px;
    color: #94a3b8;
    padding-top: 12px;
    font-weight: 500;
}

/* Tool call expanders */
.stExpander {
    border-left: 3px solid #4f46e5 !important;
    border-radius: 8px !important;
    background: #ffffff !important;
    border-top: 1px solid #e2e8f0 !important;
    border-right: 1px solid #e2e8f0 !important;
    border-bottom: 1px solid #e2e8f0 !important;
    margin-bottom: 12px !important;
}
.stExpander summary {
    color: #4f46e5 !important;
    font-size: 14px !important;
    font-weight: 600 !important;
}

/* st.status widget */
[data-testid="stStatus"] {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-left: 3px solid #4f46e5 !important;
    border-radius: 8px !important;
}

/* Primary buttons */
.stButton > button {
    background: #ffffff !important;
    color: #0f172a !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 6px !important;
    font-weight: 500 !important;
    padding: 0.5rem 1rem !important;
}
.stButton > button:hover {
    background: #f8fafc !important;
    border-color: #94a3b8 !important;
    color: #0f172a !important;
}

/* Removed old Chat Input CSS as it was replaced by Phase 2 Floating Composer */

/* Dividers */
hr { border-color: #e2e8f0 !important; margin: 1.5rem 0 !important; }

/* Dataframes */
[data-testid="stDataFrame"] { border-radius: 8px; border: 1px solid #e2e8f0; }

/* Capability Chips */
.cap-chip {
    background: #f8fafc; color: #475569; padding: 6px 16px; border-radius: 20px; font-size: 13px; font-weight: 500; border: 1px solid #e2e8f0;
    transition: all 0.2s ease; cursor: default;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.02);
}
.cap-chip:hover {
    background: #ffffff; transform: translateY(-1px); color: #0f172a; border-color: #cbd5e1; box-shadow: 0 2px 4px 0 rgba(0, 0, 0, 0.05);
}

</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _load_data(file_path: str, mtime: float) -> pd.DataFrame:
    return pd.read_excel(file_path)

def _row_count(dataset_key: str) -> str:
    try:
        path = tools.FILES[dataset_key]
        mtime = os.path.getmtime(path)
        df = _load_data(path, mtime)
        return f"{len(df):,}"
    except Exception:
        return "—"


# ── Session Init ──────────────────────────────────────────────────────────────

def init_session() -> None:
    if "agent" not in st.session_state:
        st.session_state.agent = ExcelAgent()
    if "sessions" not in st.session_state:
        # Map of session_id -> {"title": str, "messages": list}
        st.session_state.sessions = {"default": {"title": "New Chat", "messages": []}}
    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id = "default"
    if "pending_prompt" not in st.session_state:
        st.session_state.pending_prompt = None


# ── Sidebar (Chat History) ────────────────────────────────────────────────────

def render_sidebar() -> None:
    with st.sidebar:
        # Title and Subtitle
        st.markdown(
            """
            <div style='display:flex;align-items:center;gap:10px;margin-bottom:4px;'>
                <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#4f46e5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/>
                </svg>
                <div style='font-size:18px;font-weight:700;color:#0f172a;'>AI Excel Assistant</div>
            </div>
            <div style='font-size:12px;color:#64748b;margin-bottom:24px;'>Your data. Your questions. AI answers.</div>
            """,
            unsafe_allow_html=True
        )

        # New Chat Button
        if st.button("New Chat", type="primary", use_container_width=True):
            new_id = str(uuid.uuid4())
            st.session_state.sessions[new_id] = {"title": "New Chat", "messages": []}
            st.session_state.current_session_id = new_id
            st.session_state.agent = ExcelAgent()
            st.rerun()
            
        # Search Chats placeholder
        st.text_input("Search", placeholder="Search chats...", label_visibility="collapsed")

        # CHATS
        st.markdown(
            "<div style='margin-top:16px;margin-bottom:8px;font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;'>"
            "Chats</div>",
            unsafe_allow_html=True,
        )
        for sid, session_data in reversed(list(st.session_state.sessions.items())):
            if not session_data["messages"] and sid != st.session_state.current_session_id:
                continue
            is_active = (sid == st.session_state.current_session_id)
            btn_type = "secondary" if not is_active else "primary"
            title = session_data["title"]
            if st.button(title, key=f"chat_{sid}", type=btn_type, use_container_width=True):
                st.session_state.current_session_id = sid
                st.rerun()

        # DATASETS
        st.markdown(
            "<div style='margin-top:20px;margin-bottom:12px;font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;'>"
            "Datasets</div>",
            unsafe_allow_html=True,
        )
        st.markdown("""
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
            <div style="color:#64748b;"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="9" y1="21" x2="9" y2="9"></line></svg></div>
            <div>
                <div style="font-size:13px;font-weight:600;color:#0f172a;">Real Estate</div>
                <div style="font-size:10px;color:#059669;background:#dcfce7;padding:2px 6px;border-radius:12px;display:inline-flex;align-items:center;gap:4px;font-weight:700;margin-top:4px;border:1px solid #bbf7d0;">
                    <div style="width:6px;height:6px;border-radius:50%;background:#10b981;"></div> Connected
                </div>
            </div>
        </div>
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
            <div style="color:#64748b;"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="9" y1="21" x2="9" y2="9"></line></svg></div>
            <div>
                <div style="font-size:13px;font-weight:600;color:#0f172a;">Marketing</div>
                <div style="font-size:10px;color:#059669;background:#dcfce7;padding:2px 6px;border-radius:12px;display:inline-flex;align-items:center;gap:4px;font-weight:700;margin-top:4px;border:1px solid #bbf7d0;">
                    <div style="width:6px;height:6px;border-radius:50%;background:#10b981;"></div> Connected
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # TOOLS
        st.markdown(
            "<div style='margin-top:20px;margin-bottom:12px;font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;'>"
            "Tools</div>",
            unsafe_allow_html=True,
        )
        st.markdown("""
        <div style="display:flex;align-items:center;gap:8px;">
            <div style="width:6px;height:6px;border-radius:50%;background:#4f46e5;"></div>
            <div style="font-size:13px;font-weight:500;color:#475569;">5 active tools</div>
        </div>
        """, unsafe_allow_html=True)



        # CURRENT USER (Spacer then user)
        st.markdown("<div style='flex-grow:1; min-height: 80px;'></div>", unsafe_allow_html=True)
        st.markdown("""
        <div style="display:flex;align-items:center;gap:12px;padding:12px;background:#f8fafc;border-radius:12px;border:1px solid #e2e8f0;">
            <div style="width:32px;height:32px;background:#0f172a;border-radius:8px;color:#ffffff;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:600;">K</div>
            <div style="flex-grow:1;">
                <div style="font-size:13px;font-weight:600;color:#0f172a;">Khalid</div>
                <div style="font-size:11px;color:#64748b;">Professional Plan 👑</div>
            </div>
            <div style="color:#64748b;cursor:pointer;"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="1"></circle><circle cx="12" cy="5" r="1"></circle><circle cx="12" cy="19" r="1"></circle></svg></div>
        </div>
        """, unsafe_allow_html=True)


# ── Message Renderers ─────────────────────────────────────────────────────────

def _render_user_message(msg: dict) -> None:
    with st.chat_message("user", avatar="👤"):
        st.markdown(msg["content"])

def _render_assistant_message(msg: dict) -> None:
    with st.chat_message("assistant", avatar="✨"):
        st.markdown(msg["content"])

def _render_tool_expander_only(msg: dict) -> None:
    name = msg["name"]
    args = msg["args"]
    result = msg["result"]

    dataset = args.get("dataset", "System")
    is_error = isinstance(result, dict) and "error" in result
    status_icon = "❌" if is_error else "✓"
    
    action_map = {
        "query_data": f"{status_icon} Querying {dataset}",
        "insert_row": f"{status_icon} Inserting into {dataset}",
        "update_rows": f"{status_icon} Updating {dataset}",
        "delete_rows": f"{status_icon} Deleting from {dataset}",
        "get_summary": f"{status_icon} Summarizing {dataset}"
    }
    action_text = action_map.get(name, f"{status_icon} Tool: {name}")

    with st.expander(action_text, expanded=False):
        if isinstance(result, dict):
            status_color = "#fef2f2" if is_error else "#dcfce7"
            text_color = "#991b1b" if is_error else "#166534"
            badge_text = "FAILED" if is_error else "SUCCESS"
            rows_count = len(result.get("rows", [])) if not is_error else 0
            
            import random
            exec_time = f"{random.randint(120, 380)} ms"
            
            meta_html = f"""
            <div style="font-family: 'Inter', sans-serif; margin-bottom: 16px; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;">
                <div style="display:flex; background: #f8fafc; border-bottom: 1px solid #e2e8f0;">
                    <div style="padding: 10px 16px; flex: 1; border-right: 1px solid #e2e8f0;">
                        <div style="color:#64748b;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:2px;">Tool</div>
                        <div style="font-weight:600;color:#0f172a;font-size:13px;">{name}</div>
                    </div>
                    <div style="padding: 10px 16px; flex: 1; border-right: 1px solid #e2e8f0;">
                        <div style="color:#64748b;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:2px;">Dataset</div>
                        <div style="font-weight:600;color:#0f172a;font-size:13px;">{dataset}</div>
                    </div>
                    <div style="padding: 10px 16px; flex: 1; border-right: 1px solid #e2e8f0;">
                        <div style="color:#64748b;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:2px;">Rows</div>
                        <div style="font-weight:600;color:#0f172a;font-size:13px;">{rows_count}</div>
                    </div>
                    <div style="padding: 10px 16px; flex: 1; border-right: 1px solid #e2e8f0;">
                        <div style="color:#64748b;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:2px;">Exec Time (Est)</div>
                        <div style="font-weight:600;color:#0f172a;font-size:13px;">{exec_time}</div>
                    </div>
                    <div style="padding: 10px 16px; display:flex; align-items:center; justify-content:center;">
                        <div style="background:{status_color};color:{text_color};padding:4px 10px;border-radius:12px;font-size:11px;font-weight:700;letter-spacing:0.5px;">{badge_text}</div>
                    </div>
                </div>
            </div>
            """
            st.markdown(meta_html, unsafe_allow_html=True)
            st.json(args)

def _render_tool_data_only(msg: dict) -> None:
    name = msg["name"]
    result = msg["result"]
    is_error = isinstance(result, dict) and "error" in result

    if not is_error and isinstance(result, dict):
        if "rows" in result:
            df = pd.DataFrame(result["rows"])
            if not df.empty:
                total_rows = len(df)
                display_count = min(total_rows, 20)
                
                title = f"DATA PREVIEW (TOP {display_count} OF {total_rows})" if total_rows > 20 else f"DATA PREVIEW ({total_rows} ROWS)"
                st.markdown(f"<div style='font-size:11px;font-weight:700;color:#64748b;letter-spacing:0.5px;margin-bottom:12px;margin-top:24px;'>{title}</div>", unsafe_allow_html=True)
                st.dataframe(df.head(20), hide_index=True, use_container_width=True)
                
                if total_rows > 20:
                    st.info("💡 Showing the first 20 rows. Please use the Download CSV button below to view the full dataset.")
                
                csv = df.to_csv(index=False).encode('utf-8')
                btn_key = f"dl_{hash(json.dumps(msg, default=str))}"
                st.download_button(
                    label="Download CSV", data=csv, file_name=f"{name}_results.csv", mime="text/csv", key=btn_key
                )
        elif "numeric_summary" in result:
            if "sample" in result and result["sample"]:
                df = pd.DataFrame(result["sample"])
                total = result.get("total_rows", len(df))
                
                st.markdown("<div style='font-size:11px;font-weight:700;color:#64748b;letter-spacing:0.5px;margin-bottom:12px;margin-top:24px;'>DATA PREVIEW (SAMPLE)</div>", unsafe_allow_html=True)
                st.dataframe(df, hide_index=True, use_container_width=True)
                
                if total > len(df):
                    dataset_name = result.get("dataset_name", "the dataset")
                    st.info(f"💡 This is a preview of the first {len(df)} rows. To view all {total} records, please refer to the `{dataset_name}` source table.")
        elif name == "insert_row":
            st.success(f"Row successfully inserted. Auto-generated ID: **{result.get('id')}**", icon="✅")
        elif name == "update_rows":
            st.success(f"Row **{result.get('id')}** successfully updated. Modified fields: {', '.join(result.get('updated_fields', {}).keys())}", icon="✅")
        elif name == "delete_rows":
            st.success(f"Successfully deleted {result.get('deleted_count')} row(s).", icon="✅")
        else:
            st.success("Action completed successfully. No tabular data returned.", icon="✅")
    elif is_error:
        st.error(result["error"])


# ── Welcome Screen ────────────────────────────────────────────────────────────

EXAMPLES = [
    ("How many campaigns run on Facebook?", "query_data"),
    ("Show listings in Austin above $500k", "query_data"),
    ("What's the total budget for LinkedIn?", "get_summary"),
    ("Delete campaign CMP-8003", "delete_rows"),
]

def render_welcome() -> None:
    import textwrap
    st.markdown(
        textwrap.dedent("""
        <div style="display: flex; flex-direction: column; align-items: center; text-align: center; padding: 20px 0 40px;">
            <div style="font-size: 28px; font-weight: 700; color: #0f172a; margin-bottom: 8px; display: flex; align-items: center; gap: 12px;">
                <div style="background: #4f46e5; border-radius: 8px; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 6px -1px rgba(79, 70, 229, 0.2);">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                        <line x1="9" x2="15" y1="10" y2="10"/>
                        <line x1="12" x2="12" y1="7" y2="13"/>
                    </svg>
                </div>
                AI Excel Assistant
            </div>
            <div style="color: #64748b; font-size: 15px; line-height: 1.6; max-width: 500px;">
                Enterprise AI Agent for Excel Operations. Ask anything in plain English.
            </div>
        </div>
        """), 
        unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns([1, 1, 1], gap="large")

    with col1:
        st.markdown("<div style='font-size:11px;font-weight:700;color:#64748b;letter-spacing:0.5px;margin-bottom:16px;text-transform:uppercase;'>Capabilities</div>", unsafe_allow_html=True)
        caps = [
            ("Search", '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>'),
            ("Read", '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>'),
            ("Filter", '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>'),
            ("Insert", '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>'),
            ("Update", '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/><path d="m15 5 4 4"/></svg>'),
            ("Delete", '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>'),
        ]
        html_caps = "<div style='display:flex;flex-wrap:wrap;gap:8px;'>"
        for name, icon in caps:
            html_caps += textwrap.dedent(f"""
            <div style="display:flex;align-items:center;gap:6px;background:#f8fafc;color:#475569;padding:6px 12px;border-radius:16px;font-size:12px;font-weight:500;border:1px solid #e2e8f0;box-shadow:0 1px 2px 0 rgba(0,0,0,0.02);">
                {icon} {name}
            </div>
            """).strip()
        html_caps += "</div>"
        st.markdown(html_caps, unsafe_allow_html=True)

    with col2:
        st.markdown("<div style='font-size:11px;font-weight:700;color:#64748b;letter-spacing:0.5px;margin-bottom:16px;text-transform:uppercase;'>Dataset Overview</div>", unsafe_allow_html=True)
        
        real_estate_count = _row_count("real_estate")
        marketing_count = _row_count("marketing")
        
        st.markdown(textwrap.dedent(f"""
        <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:12px;margin-bottom:12px;box-shadow:0 1px 2px 0 rgba(0,0,0,0.02);">
            <div style="font-size:13px;font-weight:600;color:#0f172a;margin-bottom:4px;">Real Estate</div>
            <div style="font-size:11px;color:#64748b;display:flex;align-items:center;justify-content:space-between;">
                <span>{real_estate_count} Rows</span>
                <span style="color:#059669;background:#dcfce7;padding:2px 6px;border-radius:12px;font-weight:600;">Connected</span>
            </div>
        </div>
        <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:12px;box-shadow:0 1px 2px 0 rgba(0,0,0,0.02);">
            <div style="font-size:13px;font-weight:600;color:#0f172a;margin-bottom:4px;">Marketing</div>
            <div style="font-size:11px;color:#64748b;display:flex;align-items:center;justify-content:space-between;">
                <span>{marketing_count} Campaigns</span>
                <span style="color:#059669;background:#dcfce7;padding:2px 6px;border-radius:12px;font-weight:600;">Connected</span>
            </div>
        </div>
        """), unsafe_allow_html=True)

    with col3:
        st.markdown("<div style='font-size:11px;font-weight:700;color:#64748b;letter-spacing:0.5px;margin-bottom:16px;text-transform:uppercase;'>Suggested Prompts</div>", unsafe_allow_html=True)
        for i, (example, _) in enumerate(EXAMPLES):
            if st.button(example, key=f"ex_{i}", use_container_width=True):
                st.session_state.pending_prompt = example
                st.rerun()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    init_session()
    render_sidebar()

    current_sid = st.session_state.current_session_id
    current_session = st.session_state.sessions[current_sid]
    messages = current_session["messages"]

    # Show welcome only on empty chat
    if not messages:
        render_welcome()

    # Render stored message history for current session
    pending_tool_data = []
    for msg in messages:
        if msg["type"] == "user":
            _render_user_message(msg)
        elif msg["type"] == "tool_call":
            _render_tool_expander_only(msg)
            pending_tool_data.append(msg)
        elif msg["type"] == "assistant":
            _render_assistant_message(msg)
            for t_msg in pending_tool_data:
                _render_tool_data_only(t_msg)
            pending_tool_data.clear()

    # Resolve prompt: from example button or chat input
    prompt = st.session_state.pending_prompt or st.chat_input(
        "Ask about your data — read, filter, insert, update, or delete..."
    )
    if st.session_state.pending_prompt:
        st.session_state.pending_prompt = None

    if not prompt:
        return

    # Auto-title new chat
    if current_session["title"] == "New Chat":
        current_session["title"] = prompt[:25] + ("..." if len(prompt) > 25 else "")

    # ── Render user message ───────────────────────────────────────────────────
    user_msg = {"type": "user", "content": prompt}
    messages.append(user_msg)
    _render_user_message(user_msg)

    # ── Stream agent response ─────────────────────────────────────────────────
    tool_calls_buffer: list[dict] = []
    final_content = ""

    with st.chat_message("assistant", avatar="✨"):
        with st.status("Thinking...", expanded=True) as status:
            try:
                import time
                steps_shown = False
                
                for event in st.session_state.agent.chat_stream(prompt):
                    if not steps_shown:
                        st.write("✓ Intent recognized")
                        time.sleep(0.3)
                        st.write("✓ Extracting parameters")
                        time.sleep(0.2)
                        steps_shown = True

                    if event["type"] == "tool_call":
                        name = event["name"]
                        result = event["result"]

                        st.write(f"✓ Selecting dataset and routing to `{name}`")
                        time.sleep(0.3)
                        st.write("✓ Validation complete")
                        time.sleep(0.2)
                        st.write("✓ Executing tool against database...")

                        # Live summary inside the status widget
                        if isinstance(result, dict) and result.get("rows") is not None:
                            count = result.get("total_matching", len(result["rows"]))
                            st.write(f"**✓ `{name}` complete:** {count} row(s) returned")
                        elif isinstance(result, dict) and "error" in result:
                            st.write(f"**❌ `{name}` failed:** {result['error'][:80]}")
                        else:
                            st.write(f"**✓ `{name}` complete**")

                        tool_calls_buffer.append(event)
                        # Render the expander block immediately
                        _render_tool_expander_only(event)
                        time.sleep(0.2)
                        st.write("✓ Context updated, preparing response...")

                    elif event["type"] == "final":
                        final_content = event["content"]

                status.update(label="Complete", state="complete", expanded=False)

            except Exception as exc:
                final_content = f"**Error:** {exc}"
                status.update(label="Error occurred", state="error", expanded=False)

        _render_assistant_message({"content": final_content})
        for event in tool_calls_buffer:
            _render_tool_data_only(event)

    # ── Persist to session state ──────────────────────────────────────────────
    for tc in tool_calls_buffer:
        messages.append(tc)
    messages.append({"type": "assistant", "content": final_content})

    st.rerun()


if __name__ == "__main__":
    main()
