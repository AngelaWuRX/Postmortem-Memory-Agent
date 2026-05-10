import streamlit as st
import os
import re
import html
from pathlib import Path
from collections import Counter

st.set_page_config(
    page_title="Incident Intelligence",
    page_icon=":material/shield:",
    layout="wide",
)

st.markdown(
    """
    <style>
    :root {
        --pma-bg: #f6f8fb;
        --pma-panel: #ffffff;
        --pma-ink: #111827;
        --pma-muted: #5b6472;
        --pma-border: #d9e0ea;
        --pma-accent: #16a34a;
        --pma-accent-dark: #166534;
        --pma-navy: #172033;
        --pma-blue: #2563eb;
    }

    .stApp {
        background:
            linear-gradient(180deg, #eef4fb 0%, #f8fafc 280px, #f6f8fb 100%);
        color: var(--pma-ink);
    }

    [data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid var(--pma-border);
    }

    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] label {
        color: var(--pma-muted);
    }

    .block-container {
        max-width: 1180px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    h1, h2, h3 {
        color: var(--pma-ink);
        letter-spacing: 0;
    }

    h1 {
        font-size: 2.35rem !important;
        line-height: 1.05 !important;
        margin-bottom: 0.35rem !important;
    }

    h3 {
        font-size: 1.1rem !important;
        margin-top: 0.25rem !important;
    }

    div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.86);
        border: 1px solid var(--pma-border);
        border-radius: 8px;
        padding: 1rem 1rem 0.9rem;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
    }

    div[data-testid="stMetricLabel"] p {
        color: var(--pma-muted);
        font-size: 0.82rem;
        font-weight: 600;
    }

    div[data-testid="stMetricValue"] {
        color: var(--pma-navy);
        font-weight: 750;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 0.35rem;
        border-bottom: 1px solid var(--pma-border);
    }

    .stTabs [data-baseweb="tab"] {
        height: 2.55rem;
        padding: 0 0.9rem;
        border-radius: 7px 7px 0 0;
        color: var(--pma-muted);
        font-weight: 650;
    }

    .stTabs [aria-selected="true"] {
        background: #ffffff;
        color: var(--pma-ink);
        border: 1px solid var(--pma-border);
        border-bottom-color: #ffffff;
    }

    .stTabs [data-baseweb="tab-highlight"] {
        background-color: var(--pma-accent);
    }

    .stButton > button,
    .stDownloadButton > button {
        border-radius: 7px;
        border: 1px solid var(--pma-border);
        font-weight: 650;
        transition: border-color 180ms ease, box-shadow 180ms ease, color 180ms ease;
        cursor: pointer;
    }

    .stButton > button:hover,
    .stDownloadButton > button:hover {
        border-color: var(--pma-accent);
        color: var(--pma-accent-dark);
        box-shadow: 0 1px 8px rgba(22, 163, 74, 0.14);
    }

    .stSelectbox div[data-baseweb="select"] > div,
    textarea {
        border-radius: 7px !important;
    }

    .pma-hero {
        display: grid;
        gap: 0.6rem;
        padding: 1.35rem 1.45rem;
        margin-bottom: 1.2rem;
        background: linear-gradient(135deg, #ffffff 0%, #f7fbff 58%, #eef8f2 100%);
        border: 1px solid var(--pma-border);
        border-radius: 8px;
        box-shadow: 0 10px 28px rgba(15, 23, 42, 0.07);
    }

    .pma-kicker {
        color: var(--pma-accent-dark);
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .pma-subtitle {
        max-width: 760px;
        color: var(--pma-muted);
        font-size: 1.02rem;
        line-height: 1.55;
        margin: 0;
    }

    .pma-card {
        background: #ffffff;
        border: 1px solid var(--pma-border);
        border-radius: 8px;
        padding: 1rem;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        margin-bottom: 0.8rem;
    }

    .pma-card-title {
        font-size: 0.82rem;
        color: var(--pma-muted);
        font-weight: 750;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 0.4rem;
    }

    .pma-incident-row {
        display: grid;
        grid-template-columns: 120px 210px 1fr;
        gap: 0.9rem;
        align-items: start;
        padding: 0.85rem 0;
        border-bottom: 1px solid #e7ecf3;
    }

    .pma-incident-row:last-child {
        border-bottom: 0;
    }

    .pma-date {
        color: var(--pma-muted);
        font-size: 0.9rem;
        font-weight: 650;
    }

    .pma-service {
        color: var(--pma-ink);
        font-weight: 750;
    }

    .pma-summary {
        color: #334155;
        line-height: 1.45;
    }

    .pma-service-row {
        display: grid;
        grid-template-columns: minmax(130px, 190px) 1fr 40px;
        gap: 0.75rem;
        align-items: center;
        padding: 0.72rem 0;
        border-bottom: 1px solid #e7ecf3;
    }

    .pma-service-row:last-child {
        border-bottom: 0;
    }

    .pma-progress {
        height: 0.55rem;
        border-radius: 999px;
        background: #e7edf5;
        overflow: hidden;
    }

    .pma-progress > span {
        display: block;
        height: 100%;
        border-radius: inherit;
        background: linear-gradient(90deg, var(--pma-blue), var(--pma-accent));
    }

    .pma-count {
        color: var(--pma-ink);
        font-weight: 800;
        text-align: right;
    }

    .pma-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        border-radius: 999px;
        padding: 0.18rem 0.55rem;
        font-size: 0.75rem;
        font-weight: 800;
        border: 1px solid transparent;
        white-space: nowrap;
    }

    .sev-1 { color: #991b1b; background: #fee2e2; border-color: #fecaca; }
    .sev-2 { color: #9a3412; background: #ffedd5; border-color: #fed7aa; }
    .sev-3 { color: #854d0e; background: #fef9c3; border-color: #fde68a; }
    .sev-4 { color: #166534; background: #dcfce7; border-color: #bbf7d0; }
    .sev-unknown { color: #334155; background: #e2e8f0; border-color: #cbd5e1; }

    .pma-muted {
        color: var(--pma-muted);
    }

    .pma-empty {
        border: 1px dashed #cbd5e1;
        background: rgba(255,255,255,0.72);
        border-radius: 8px;
        padding: 1.1rem;
        color: var(--pma-muted);
    }

    @media (max-width: 760px) {
        .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }

        .pma-incident-row {
            grid-template-columns: 1fr;
            gap: 0.25rem;
        }

        h1 {
            font-size: 1.85rem !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Demo controls")
    demo_mode = st.toggle(
        "Use local demo mode",
        value=os.environ.get("PMA_DEMO_MODE", "1") == "1",
        help="Runs without API calls — uses deterministic local parsing.",
    )
    os.environ["PMA_DEMO_MODE"] = "1" if demo_mode else "0"
    if demo_mode:
        st.caption("No external model calls will be made.")
    elif not os.environ.get("ANTHROPIC_API_KEY"):
        st.warning("Set ANTHROPIC_API_KEY to use live model calls.")

    st.divider()
    st.markdown("**Engineers:** use the CLI")
    st.code("pma ingest <postmortem.md>\npma review <diff.patch>\npma memory", language="bash")

from agent.memory import all_chunks

GENERATED_DIR = Path("generated")
SEV_CLASS = {"SEV-1": "sev-1", "SEV-2": "sev-2", "SEV-3": "sev-3", "SEV-4": "sev-4"}


def severity_badge(severity: str) -> str:
    class_name = SEV_CLASS.get(severity, "sev-unknown")
    return f'<span class="pma-pill {class_name}">{html.escape(severity)}</span>'

chunks = all_chunks()
n = len(chunks)

st.markdown(
    """
    <section class="pma-hero">
        <div class="pma-kicker">Incident memory layer</div>
        <h1>Incident Intelligence</h1>
        <p class="pma-subtitle">
            A living record of production failures, fixes, prevention work, and risky patterns that should not ship twice.
        </p>
    </section>
    """,
    unsafe_allow_html=True,
)

tab_overview, tab_log, tab_prevention = st.tabs([
    "Overview",
    "Incident Log",
    "Prevention Output",
])


# ── TAB 1: OVERVIEW ───────────────────────────────────────────────────────────

with tab_overview:
    if n == 0:
        st.markdown(
            '<div class="pma-empty">No incidents logged yet. Engineers can add incidents from the terminal with <code>pma ingest &lt;postmortem.md&gt;</code>.</div>',
            unsafe_allow_html=True,
        )
    else:
        # Top-line metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Incidents logged", n)
        col2.metric("Services affected", len(set(c.component for c in chunks)))
        artifact_count = len(list(GENERATED_DIR.glob("*.md"))) + len(list(GENERATED_DIR.glob("*.py"))) + len(list(GENERATED_DIR.glob("*.yaml"))) if GENERATED_DIR.exists() else 0
        col3.metric("Prevention artifacts", artifact_count)
        col4.metric("Context tokens saved", f"{n * 1_850:,}", help="vs loading full postmortem docs on every query")

        st.divider()

        left, right = st.columns([1, 2])

        with left:
            st.subheader("By severity")
            sev_data = Counter(c.severity for c in chunks)
            sev_cols = st.columns(2)
            for sev in ["SEV-1", "SEV-2", "SEV-3", "SEV-4"]:
                count = sev_data.get(sev, 0)
                with sev_cols[["SEV-1", "SEV-2", "SEV-3", "SEV-4"].index(sev) % 2]:
                    st.markdown(
                        f"""
                        <div class="pma-card">
                            <div>{severity_badge(sev)}</div>
                            <div style="font-size:1.8rem;font-weight:800;margin-top:.35rem;">{count}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        with right:
            st.subheader("Incidents by service")
            service_counts = Counter(c.component for c in chunks)
            max_count = max(service_counts.values()) if service_counts else 1
            service_rows = []
            for service, count in sorted(service_counts.items(), key=lambda item: item[1], reverse=True):
                width = max(8, int((count / max_count) * 100))
                service_rows.append(
                    f"""
                    <div class="pma-service-row">
                        <div class="pma-service">{html.escape(service)}</div>
                        <div class="pma-progress"><span style="width:{width}%"></span></div>
                        <div class="pma-count">{count}</div>
                    </div>
                    """
                )
            st.markdown(f'<div class="pma-card">{"".join(service_rows)}</div>', unsafe_allow_html=True)

        st.divider()
        st.subheader("Recent incidents")

        rows_html = []
        for c in sorted(chunks, key=lambda x: x.date, reverse=True):
            rows_html.append(
                f"""
                <div class="pma-incident-row">
                    <div class="pma-date">{c.date}</div>
                    <div><div class="pma-service">{html.escape(c.component)}</div>{severity_badge(c.severity)}</div>
                    <div class="pma-summary">{html.escape(c.raw_summary)}</div>
                </div>
                """
            )
        st.markdown(f'<div class="pma-card">{"".join(rows_html)}</div>', unsafe_allow_html=True)


# ── TAB 2: INCIDENT LOG ───────────────────────────────────────────────────────

with tab_log:
    if n == 0:
        st.markdown(
            '<div class="pma-empty">No incidents logged yet. Engineers can add incidents from the terminal with <code>pma ingest &lt;postmortem.md&gt;</code>.</div>',
            unsafe_allow_html=True,
        )
    else:
        # Filters
        fc1, fc2, _ = st.columns([1, 1, 3])
        services = ["All services"] + sorted(set(c.component for c in chunks))
        severities = ["All severities", "SEV-1", "SEV-2", "SEV-3", "SEV-4"]
        sel_service = fc1.selectbox("Service", services, label_visibility="collapsed")
        sel_severity = fc2.selectbox("Severity", severities, label_visibility="collapsed")

        filtered = sorted(chunks, key=lambda x: x.date, reverse=True)
        if sel_service != "All services":
            filtered = [c for c in filtered if c.component == sel_service]
        if sel_severity != "All severities":
            filtered = [c for c in filtered if c.severity == sel_severity]

        st.caption(f"Showing {len(filtered)} of {n} incidents")
        st.divider()

        for c in filtered:
            with st.expander(f"{c.component} - {c.date} - {c.severity}"):
                st.markdown(severity_badge(c.severity), unsafe_allow_html=True)
                st.markdown("**What went wrong**")
                st.markdown(c.root_cause)
                st.markdown("**How it was resolved**")
                st.markdown(c.fix_pattern)
                st.markdown("**How it was detected**")
                st.markdown(c.detection_signal)
                if c.tags:
                    st.markdown(" ".join(f"`{t}`" for t in c.tags))


# ── TAB 3: PREVENTION OUTPUT ──────────────────────────────────────────────────

with tab_prevention:
    ticket_path = GENERATED_DIR / "ticket.md"
    runbook_path = GENERATED_DIR / "runbook.md"
    has_artifacts = GENERATED_DIR.exists() and (ticket_path.exists() or runbook_path.exists())

    if not has_artifacts:
        st.markdown(
            '<div class="pma-empty">No prevention artifacts yet. Engineers generate them with <code>pma ingest &lt;postmortem.md&gt;</code>.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<p class="pma-muted">Automatically generated prevention work from the latest incident: ticket, runbook, regression coverage, and monitoring.</p>',
            unsafe_allow_html=True,
        )
        st.divider()

        def strip_code_blocks(text: str) -> str:
            """Replace code fences with a plain-language note for non-technical readers."""
            return re.sub(
                r"```[\s\S]*?```",
                "_→ Technical implementation details available in the engineering runbook._",
                text,
            )

        col_left, col_right = st.columns(2)

        with col_left:
            if ticket_path.exists():
                st.subheader("Prevention Ticket")
                st.markdown("Ready to file in Jira, Linear, or GitHub Issues.")
                st.markdown(strip_code_blocks(ticket_path.read_text()))
                st.download_button(
                    "Download ticket.md",
                    ticket_path.read_text(),
                    "ticket.md",
                    width="stretch",
                )

        with col_right:
            if runbook_path.exists():
                st.subheader("Response Runbook")
                st.markdown("Step-by-step guide for on-call response if this pattern recurs.")
                st.markdown(strip_code_blocks(runbook_path.read_text()))
                st.download_button(
                    "Download runbook.md",
                    runbook_path.read_text(),
                    "runbook.md",
                    width="stretch",
                )

        st.divider()
        st.subheader("Engineering Artifacts")
        st.markdown("These are also generated but intended for the engineering team.")

        eng_cols = st.columns(2)
        test_path = GENERATED_DIR / "regression_test.py"
        monitor_path = GENERATED_DIR / "monitor.yaml"

        with eng_cols[0]:
            if test_path.exists():
                st.markdown("**Regression Test**")
                st.markdown("A test that would catch this bug before it reaches production.")
                st.download_button("Download regression_test.py", test_path.read_text(), "regression_test.py", width="stretch")

        with eng_cols[1]:
            if monitor_path.exists():
                st.markdown("**Monitoring Rule**")
                st.markdown("An alert tuned to the exact signal that detected this incident.")
                st.download_button("Download monitor.yaml", monitor_path.read_text(), "monitor.yaml", width="stretch")
