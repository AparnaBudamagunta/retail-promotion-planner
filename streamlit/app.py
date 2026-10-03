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
        "desc":   "Seasonal promotion · India"
    },
    {
        "label": "🧴 FMCG Stock Clearance",
        "prompt": "I need to clear my FMCG stock in India before year end.",
        "desc":   "Inventory clearance · India"
    },
    {
        "label": "🖥️ Black Friday Electronics",
        "prompt": "Build a promotion for electronics in USA for Black Friday.",
        "desc":   "Peak event · USA"
    },
    {
        "label": "🧼 Single Brand Diwali",
        "prompt": "Build a promotion for Ariel in India for Diwali.",
        "desc":   "Brand promotion · India"
    }
]

# ── PAGE SETUP ─────────────────────────────────────────────────
st.set_page_config(
    page_title="Promotion Planner",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── STYLES ─────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Inter:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background: #FAFAF8;
}

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.stApp {
    background: #FAFAF8;
}

/* ── SIDEBAR ── */
[data-testid="stSidebar"] {
    background: #1A1A2E;
    border-right: 2px solid #E8380D;
}

[data-testid="stSidebar"] * {
    color: #E8EAF0 !important;
}

[data-testid="stSidebar"] .stButton button {
    background: #252540 !important;
    border: 1px solid #353558 !important;
    color: #E8EAF0 !important;
    border-radius: 6px !important;
    text-align: left !important;
    padding: 10px 14px !important;
    font-size: 13px !important;
    margin-bottom: 6px !important;
    transition: border-color 0.2s !important;
}

[data-testid="stSidebar"] .stButton button:hover {
    border-color: #E8380D !important;
    background: #2D2D50 !important;
}

/* ── HERO HEADER ── */
.hero {
    background: #E8380D;
    border-radius: 0px;
    padding: 28px 36px;
    margin-bottom: 28px;
    color: white;
    border-bottom: 4px solid #C42D09;
}

.hero-title {
    font-family: 'Playfair Display', serif;
    font-size: 32px;
    font-weight: 700;
    margin: 0 0 6px 0;
    letter-spacing: -0.5px;
    line-height: 1.2;
}

.hero-sub {
    font-size: 14px;
    color: rgba(255,255,255,0.8);
    margin: 0;
    font-weight: 300;
    letter-spacing: 0.2px;
}

.hero-tag {
    display: inline-block;
    background: rgba(0,0,0,0.2);
    color: rgba(255,255,255,0.9);
    font-size: 10px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 2px;
    margin-bottom: 12px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}

/* ── SECTION CARDS ── */
.section-card {
    background: white;
    border-radius: 4px;
    padding: 24px 28px;
    margin-bottom: 16px;
    border-left: 4px solid #E8380D;
    border-top: 1px solid #E8EBF0;
    border-right: 1px solid #E8EBF0;
    border-bottom: 1px solid #E8EBF0;
}

.section-number {
    font-size: 10px;
    font-weight: 700;
    color: #E8380D;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 4px;
}

.section-heading {
    font-family: 'Playfair Display', serif;
    font-size: 18px;
    font-weight: 700;
    color: #1A1A2E;
    margin-bottom: 16px;
}

/* ── USER MESSAGE ── */
.user-msg {
    background: #1A1A2E;
    color: #F0F0F8;
    border-radius: 4px;
    padding: 16px 20px;
    margin-bottom: 24px;
    font-size: 15px;
    font-style: italic;
    border-left: 4px solid #E8380D;
}

.user-msg-label {
    font-size: 10px;
    font-weight: 700;
    color: #E8380D;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 6px;
    font-style: normal;
}

/* ── ACCENTURE PURPLE CTA ── */
.accenture-note {
    background: #F5F0FF;
    border-left: 3px solid #A100FF;
    padding: 10px 16px;
    border-radius: 0 4px 4px 0;
    font-size: 13px;
    color: #3D0080;
    margin-top: 20px;
}

/* ── DATA TABLES ── */
table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    font-family: 'Inter', sans-serif;
}

th {
    background: #1A1A2E;
    color: #F0F0F8;
    font-weight: 600;
    padding: 10px 14px;
    text-align: left;
    font-size: 11px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}

td {
    padding: 10px 14px;
    border-bottom: 1px solid #F0F0EC;
    color: #2D2D2D;
}

tr:nth-child(even) td {
    background: #FAFAF8;
}

tr:last-child td {
    border-bottom: none;
}

/* ── POSITIVE/NEGATIVE NUMBERS ── */
.num-positive { color: #00875A; font-weight: 600; }
.num-negative { color: #D32F2F; font-weight: 600; }

/* ── FOOTER ── */
.footer {
    text-align: center;
    color: #9CA3AF;
    font-size: 11px;
    padding: 24px;
    margin-top: 8px;
    border-top: 1px solid #E8EBF0;
    letter-spacing: 0.3px;
}

/* ── DIVIDER ── */
.et-divider {
    border: none;
    border-top: 2px solid #E8380D;
    margin: 8px 0 24px 0;
    opacity: 0.3;
}

/* Status box */
[data-testid="stStatusWidget"] {
    background: #1A1A2E !important;
    border: 1px solid #E8380D !important;
    color: white !important;
}
</style>
""", unsafe_allow_html=True)


# ── SIDEBAR ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='padding: 16px 0 24px 0;'>
        <div style='font-size:11px; font-weight:700;
                    letter-spacing:1.5px; color:#E8380D;
                    text-transform:uppercase;
                    margin-bottom:8px;'>
            Promotion Planner
        </div>
        <div style='font-size:13px; color:#9CA3C8;
                    line-height:1.5;'>
            AI-powered retail promotion decisions 
            backed by live catalog data.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style='font-size:10px; font-weight:700;
                color:#E8380D; letter-spacing:1.5px;
                text-transform:uppercase;
                margin-bottom:10px;'>
        Try an example
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

    st.markdown("<div style='margin:20px 0; border-top:1px solid #2D2D50;'></div>",
                unsafe_allow_html=True)

    st.markdown("""
    <div style='font-size:10px; font-weight:700;
                color:#E8380D; letter-spacing:1.5px;
                text-transform:uppercase;
                margin-bottom:12px;'>
        How it works
    </div>
    <div style='font-size:12px; line-height:2; color:#9CA3C8;'>
        <span style='color:#E8380D; font-weight:600;'>01</span>
        &nbsp; Describe your promotion<br>
        <span style='color:#E8380D; font-weight:600;'>02</span>
        &nbsp; AI reads your catalog<br>
        <span style='color:#E8380D; font-weight:600;'>03</span>
        &nbsp; Simulation runs P&amp;L<br>
        <span style='color:#E8380D; font-weight:600;'>04</span>
        &nbsp; Full plan delivered
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='margin:20px 0; border-top:1px solid #2D2D50;'></div>",
                unsafe_allow_html=True)

    if st.button("Clear conversation",
                 use_container_width=True):
        st.session_state["messages"] = []
        st.session_state.pop("prefill", None)
        st.rerun()

    st.markdown("""
    <div style='font-size:11px; color:#4B5278;
                margin-top:24px; line-height:1.8;'>
        Powered by<br>
        <span style='color:#6B7A9A; font-weight:500;'>
            Databricks Delta Lake
        </span><br>
        <span style='color:#6B7A9A; font-weight:500;'>
            Groq AI
        </span><br>
        <span style='color:#A100FF; font-weight:500;'>
            Accenture &amp; ET Hackathon 2026
        </span>
    </div>
    """, unsafe_allow_html=True)


# ── MAIN ───────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Hero
st.markdown("""
<div class='hero'>
    <div class='hero-tag'>Accenture &amp; ET Hackathon 2026</div>
    <div class='hero-title'>AI Retail Promotion Planner</div>
    <div class='hero-sub'>
        Describe any promotion in plain English — 
        get a complete data-driven plan in seconds. 
        P&amp;L simulation · Segment playbook · 
        Competitor context · Execution checklist.
    </div>
</div>
""", unsafe_allow_html=True)

# Conversation history
for msg in st.session_state["messages"]:
    if msg["role"] == "user":
        st.markdown(f"""
        <div class='user-msg'>
            <div class='user-msg-label'>Your request</div>
            {msg['content']}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(msg["content"])
        st.markdown("<hr class='et-divider'>",
                    unsafe_allow_html=True)


# ── JOB RUNNER ─────────────────────────────────────────────────
def run_job(prompt: str) -> str:
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
                task_run_id = tasks[0]["run_id"] \
                    if tasks else run_id
                out_resp = requests.get(
                    f"{DATABRICKS_URL}/api/2.1/jobs/runs/get-output",
                    headers=HEADERS,
                    params={"run_id": task_run_id}
                )
                return out_resp.json().get(
                    "notebook_output", {}
                ).get("result", "No output returned.")
            else:
                return "❌ Job did not complete. Please try again."

        elif state in ["INTERNAL_ERROR", "SKIPPED"]:
            return "❌ An error occurred. Please try again."

    return "⏱️ Request timed out. Please try again."


# ── CHAT INPUT ─────────────────────────────────────────────────
prefill = st.session_state.pop("prefill", "")
prompt  = st.chat_input(
    "Describe your promotion — product, region, event, budget..."
) or prefill

if prompt:
    st.markdown(f"""
    <div class='user-msg'>
        <div class='user-msg-label'>Your request</div>
        {prompt}
    </div>
    """, unsafe_allow_html=True)

    st.session_state["messages"].append({
        "role": "user", "content": prompt
    })

    with st.status(
        "Building your promotion plan...",
        expanded=True
    ) as status_box:
        st.write("📡 Connecting to Databricks...")
        time.sleep(1)
        st.write("📦 Fetching your product catalog...")
        time.sleep(1)
        st.write("🧮 Running financial simulation...")
        time.sleep(1)
        st.write("🤖 AI making promotion decisions...")

        plan = run_job(prompt)

        st.write("✅ Plan ready.")
        status_box.update(
            label="Plan ready", state="complete"
        )

    st.markdown(plan)
    st.markdown("<hr class='et-divider'>",
                unsafe_allow_html=True)

    st.markdown("""
    <div class='accenture-note'>
        This plan was generated using live Delta Lake 
        catalog data, PySpark financial simulation, 
        and Groq AI decision-making — 
        no hardcoded rules or templates.
    </div>
    """, unsafe_allow_html=True)

    st.session_state["messages"].append({
        "role": "assistant", "content": plan
    })

    st.markdown("""
    <div class='footer'>
        Databricks Delta Lake · Groq AI · PySpark Simulation · 
        Accenture &amp; ET Hackathon 2026
    </div>
    """, unsafe_allow_html=True)