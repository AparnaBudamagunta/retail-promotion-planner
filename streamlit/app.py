import streamlit as st
import requests
import time

# ── CONFIG ────────────────────────────────────────────────────
DATABRICKS_URL   = st.secrets["DATABRICKS_URL"]
DATABRICKS_TOKEN = st.secrets["DATABRICKS_TOKEN"]
JOB_ID           = 28161186495029

HEADERS = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type":  "application/json"
}

EXAMPLE_PROMPTS = [
    {
        "label": "🥤 Diwali Beverages",
        "prompt": "Build a promotion for beverages in India for Diwali. My marketing budget is 10000 INR.",
        "desc":   "Seasonal promotion across India"
    },
    {
        "label": "🧴 FMCG Clearance",
        "prompt": "I need to clear my FMCG stock in India before year end.",
        "desc":   "Inventory clearance drive"
    },
    {
        "label": "🖥️ Black Friday Electronics",
        "prompt": "Build a promotion for electronics in USA for Black Friday.",
        "desc":   "High-demand seasonal event"
    },
    {
        "label": "🧼 Ariel Diwali",
        "prompt": "Build a promotion for Ariel in India for Diwali.",
        "desc":   "Single brand promotion"
    }
]

STEPS = [
    "Parsing your request...",
    "Fetching catalog and market data...",
    "Running financial simulation...",
    "Getting AI decisions...",
    "Assembling your plan..."
]

# ── PAGE SETUP ─────────────────────────────────────────────────
st.set_page_config(
    page_title = "Promotion Planner",
    page_icon  = "🛒",
    layout     = "wide",
    initial_sidebar_state = "expanded"
)

# ── STYLES ─────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Hide default streamlit chrome */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Main background */
.stApp {
    background: #F7F8FA;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #1A1D2E;
    border-right: 1px solid #2D3148;
}

[data-testid="stSidebar"] * {
    color: #E8EAF0 !important;
}

/* Hero header */
.hero {
    background: linear-gradient(135deg, #1A1D2E 0%, #2D3561 100%);
    border-radius: 16px;
    padding: 32px 36px;
    margin-bottom: 24px;
    color: white;
}

.hero h1 {
    font-size: 28px;
    font-weight: 700;
    margin: 0 0 6px 0;
    letter-spacing: -0.5px;
}

.hero p {
    font-size: 15px;
    color: #9CA3C8;
    margin: 0;
}

.hero-badge {
    display: inline-block;
    background: rgba(99, 120, 255, 0.2);
    border: 1px solid rgba(99, 120, 255, 0.4);
    color: #8B9FFF;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 20px;
    margin-bottom: 14px;
    letter-spacing: 0.5px;
}

/* Section cards */
.section-card {
    background: white;
    border-radius: 12px;
    padding: 24px 28px;
    margin-bottom: 16px;
    border: 1px solid #E8EBF0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

.section-label {
    font-size: 11px;
    font-weight: 600;
    color: #6378FF;
    letter-spacing: 0.8px;
    margin-bottom: 8px;
    text-transform: uppercase;
}

.section-title {
    font-size: 17px;
    font-weight: 600;
    color: #1A1D2E;
    margin-bottom: 16px;
}

/* Metric row */
.metric-row {
    display: flex;
    gap: 16px;
    margin-bottom: 20px;
    flex-wrap: wrap;
}

.metric-box {
    background: #F0F3FF;
    border-radius: 10px;
    padding: 14px 20px;
    min-width: 140px;
    flex: 1;
}

.metric-value {
    font-size: 22px;
    font-weight: 700;
    color: #1A1D2E;
}

.metric-label {
    font-size: 12px;
    color: #6B7280;
    margin-top: 2px;
}

/* Risk indicator */
.risk-low {
    background: #ECFDF5;
    border: 1px solid #A7F3D0;
    color: #065F46;
    padding: 8px 14px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    display: inline-block;
}

.risk-medium {
    background: #FFFBEB;
    border: 1px solid #FDE68A;
    color: #92400E;
    padding: 8px 14px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    display: inline-block;
}

.risk-high {
    background: #FEF2F2;
    border: 1px solid #FECACA;
    color: #991B1B;
    padding: 8px 14px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    display: inline-block;
}

/* Pass/fail badges */
.badge-pass {
    background: #ECFDF5;
    color: #065F46;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 600;
}

.badge-fail {
    background: #FEF2F2;
    color: #991B1B;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 600;
}

/* Example prompt buttons */
.example-btn {
    background: #2D3148;
    border: 1px solid #3D4268;
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 8px;
    cursor: pointer;
    transition: background 0.2s;
    width: 100%;
    text-align: left;
}

.example-btn:hover {
    background: #363B5E;
}

/* Progress steps */
.step-active {
    color: #6378FF;
    font-weight: 500;
}

.step-done {
    color: #10B981;
}

.step-pending {
    color: #9CA3AF;
}

/* Chat input area */
[data-testid="stChatInput"] {
    border-top: 1px solid #E8EBF0;
    padding-top: 16px;
}

/* User message */
.user-msg {
    background: #1A1D2E;
    color: white;
    border-radius: 12px;
    padding: 14px 18px;
    margin-bottom: 20px;
    font-size: 15px;
    max-width: 80%;
    margin-left: auto;
}

/* Tables */
table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}

th {
    background: #F0F3FF;
    color: #1A1D2E;
    font-weight: 600;
    padding: 10px 14px;
    text-align: left;
    border-bottom: 2px solid #E8EBF0;
}

td {
    padding: 10px 14px;
    border-bottom: 1px solid #F3F4F6;
    color: #374151;
}

tr:last-child td {
    border-bottom: none;
}

/* Divider */
.plan-divider {
    border: none;
    border-top: 1px solid #E8EBF0;
    margin: 8px 0 20px 0;
}

/* Footer */
.footer {
    text-align: center;
    color: #9CA3AF;
    font-size: 12px;
    padding: 20px;
    margin-top: 20px;
}
</style>
""", unsafe_allow_html=True)


# ── SIDEBAR ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='padding: 8px 0 20px 0;'>
        <div style='font-size:22px; font-weight:700; 
                    letter-spacing:-0.5px;'>
            🛒 Promotion Planner
        </div>
        <div style='font-size:12px; color:#6B7A9A; 
                    margin-top:4px;'>
            AI-powered retail decisions
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("""
    <div style='font-size:11px; font-weight:600; 
                color:#6B7A9A; letter-spacing:0.8px;
                margin-bottom:12px;'>
        TRY THESE EXAMPLES
    </div>
    """, unsafe_allow_html=True)

    for ex in EXAMPLE_PROMPTS:
        if st.button(
            f"{ex['label']}\n{ex['desc']}",
            key=f"ex_{ex['label']}",
            use_container_width=True
        ):
            st.session_state["prefill"] = ex["prompt"]
            st.rerun()

    st.markdown("---")
    st.markdown("""
    <div style='font-size:11px; font-weight:600; 
                color:#6B7A9A; letter-spacing:0.8px;
                margin-bottom:12px;'>
        HOW IT WORKS
    </div>
    <div style='font-size:13px; line-height:1.8;'>
        <div style='margin-bottom:8px;'>
            <span style='color:#6378FF;'>①</span> 
            Describe your promotion goal
        </div>
        <div style='margin-bottom:8px;'>
            <span style='color:#6378FF;'>②</span> 
            AI analyses your catalog
        </div>
        <div style='margin-bottom:8px;'>
            <span style='color:#6378FF;'>③</span> 
            Simulation runs across scenarios
        </div>
        <div style='margin-bottom:8px;'>
            <span style='color:#6378FF;'>④</span> 
            Full plan delivered instantly
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    if st.button("🗑️ Clear conversation",
                 use_container_width=True):
        st.session_state["messages"] = []
        st.session_state.pop("prefill", None)
        st.rerun()

    st.markdown("""
    <div style='font-size:11px; color:#4B5278; 
                margin-top:20px; line-height:1.6;'>
        Powered by<br>
        <strong style='color:#6B7A9A;'>
            Databricks Delta Lake
        </strong><br>
        <strong style='color:#6B7A9A;'>
            Groq AI (LLM)
        </strong>
    </div>
    """, unsafe_allow_html=True)


# ── MAIN AREA ──────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Hero header
st.markdown("""
<div class='hero'>
    <div class='hero-badge'>AI-POWERED</div>
    <h1>Retail Promotion Planner</h1>
    <p>Describe any promotion in plain English. 
       Get a complete data-driven plan in seconds — 
       P&amp;L simulation, segment playbook, 
       competitor context and execution checklist.</p>
</div>
""", unsafe_allow_html=True)

# Show conversation history
for msg in st.session_state["messages"]:
    if msg["role"] == "user":
        st.markdown(
            f"<div class='user-msg'>{msg['content']}</div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(msg["content"], unsafe_allow_html=True)


# ── HELPERS ────────────────────────────────────────────────────
def run_job(prompt: str) -> str:
    """Submit Databricks job and poll for result."""

    # Submit
    run_resp = requests.post(
        f"{DATABRICKS_URL}/api/2.1/jobs/run-now",
        headers=HEADERS,
        json={
            "job_id": JOB_ID,
            "notebook_params": {"user_request": prompt}
        }
    )

    if run_resp.status_code != 200:
        return f"❌ Could not start job: {run_resp.text}"

    run_id = run_resp.json()["run_id"]

    # Poll
    max_wait = 360
    elapsed  = 0
    while elapsed < max_wait:
        time.sleep(10)
        elapsed += 10

        status_resp = requests.get(
            f"{DATABRICKS_URL}/api/2.1/jobs/runs/get",
            headers=HEADERS,
            params={"run_id": run_id}
        )
        status = status_resp.json()
        state  = status["state"]["life_cycle_state"]

        if state == "TERMINATED":
            if status["state"]["result_state"] == "SUCCESS":
                tasks       = status.get("tasks", [])
                task_run_id = tasks[0]["run_id"] if tasks else run_id

                out_resp = requests.get(
                    f"{DATABRICKS_URL}/api/2.1/jobs/runs/get-output",
                    headers=HEADERS,
                    params={"run_id": task_run_id}
                )
                return out_resp.json().get(
                    "notebook_output", {}
                ).get("result", "No output returned.")
            else:
                return "❌ Job did not complete successfully. Please try again."

        elif state in ["INTERNAL_ERROR", "SKIPPED"]:
            return "❌ An error occurred. Please try again."

    return "⏱️ Request timed out. Please try again."


def show_progress():
    """Show animated progress steps."""
    placeholder = st.empty()
    for i, step in enumerate(STEPS):
        lines = []
        for j, s in enumerate(STEPS):
            if j < i:
                lines.append(f"✅ {s}")
            elif j == i:
                lines.append(f"⏳ **{s}**")
            else:
                lines.append(f"○ {s}")
        placeholder.markdown("\n\n".join(lines))
        time.sleep(2)
    placeholder.empty()
    return placeholder


# ── CHAT INPUT ─────────────────────────────────────────────────
prefill  = st.session_state.pop("prefill", "")
prompt   = st.chat_input(
    "Describe your promotion — product, region, event, budget..."
) or prefill

if prompt:
    # Show user message
    st.markdown(
        f"<div class='user-msg'>{prompt}</div>",
        unsafe_allow_html=True
    )
    st.session_state["messages"].append({
        "role": "user", "content": prompt
    })

    # Progress + job
    with st.status(
        "Building your promotion plan...",
        expanded=True
    ) as status_box:
        st.write("📡 Connecting to Databricks...")
        time.sleep(1)
        st.write("📦 Loading your product catalog...")
        time.sleep(1)
        st.write("🧮 Running financial simulation...")
        time.sleep(1)
        st.write("🤖 AI making promotion decisions...")

        plan = run_job(prompt)

        st.write("✅ Plan ready.")
        status_box.update(
            label="Plan complete", state="complete"
        )

    # Display plan
    st.markdown(plan, unsafe_allow_html=False)
    st.session_state["messages"].append({
        "role": "assistant", "content": plan
    })

    # Footer note
    st.markdown("""
    <div class='footer'>
        Plan generated using Delta Lake catalog data · 
        Groq AI decisions · 
        PySpark financial simulation
    </div>
    """, unsafe_allow_html=True)