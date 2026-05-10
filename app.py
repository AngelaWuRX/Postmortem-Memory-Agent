import streamlit as st
from pathlib import Path

st.set_page_config(
    page_title="Incident Intelligence",
    page_icon="🛡️",
    layout="wide",
)

from agent.parser import parse_postmortem
from agent.memory import store, all_chunks, count as memory_count
from agent.artifact_generator import generate_all, save_artifacts
from agent.router import route

SAMPLE_DIR = Path("sample_data")
GENERATED_DIR = Path("generated")

# ── header ────────────────────────────────────────────────────────────────────

st.title("🛡️ Incident Intelligence")
st.caption("Your team's incident memory — learns from every postmortem, flags risky code changes before they ship.")

n = memory_count()
col1, col2, col3 = st.columns(3)
col1.metric("Incidents in memory", n)
col2.metric("Estimated tokens saved", f"{n * 1_850:,}" if n else "0", help="vs loading full postmortem docs")
col3.metric("Artifacts generated", len(list(GENERATED_DIR.glob("*"))) if GENERATED_DIR.exists() else 0)

st.divider()

tab_ingest, tab_pr, tab_history = st.tabs([
    "📥 Add Incident Report",
    "🔍 Assess a PR",
    "📊 Incident History",
])


# ── TAB 1: ADD INCIDENT REPORT ────────────────────────────────────────────────

with tab_ingest:
    st.subheader("Add an Incident Report")
    st.markdown(
        "Paste a postmortem or incident report. The system will extract the key facts, "
        "store them for future reference, and generate prevention artifacts automatically."
    )

    sample_files = sorted(SAMPLE_DIR.glob("postmortem_*.md")) if SAMPLE_DIR.exists() else []
    if sample_files:
        st.markdown("**Try a sample report:**")
        cols = st.columns(min(len(sample_files), 3))
        for col, f in zip(cols * 2, sample_files):
            label = f.stem.replace("postmortem_", "").replace("_", " ").title()
            if col.button(label, key=f"load_{f.stem}", use_container_width=True):
                st.session_state["ingest_text"] = f.read_text()

    postmortem_text = st.text_area(
        "Incident report",
        value=st.session_state.get("ingest_text", ""),
        height=220,
        placeholder="Paste your incident report or postmortem here...",
    )

    if st.button("📥 Save to Memory & Generate Artifacts", type="primary", disabled=not postmortem_text.strip()):
        with st.spinner("Reading the report..."):
            chunk = parse_postmortem(postmortem_text)
            store(chunk)

        sev_colors = {"SEV-1": "🔴", "SEV-2": "🟠", "SEV-3": "🟡", "SEV-4": "🟢"}
        icon = sev_colors.get(chunk.severity, "⚪")

        st.success(f"Saved: **{chunk.component}** — {icon} {chunk.severity} incident on {chunk.date}")

        with st.expander("What was extracted", expanded=True):
            st.markdown(f"**What went wrong:** {chunk.root_cause}")
            st.markdown(f"**How it was fixed:** {chunk.fix_pattern}")
            st.markdown(f"**How it was detected:** {chunk.detection_signal}")
            st.markdown(f"**Summary:** _{chunk.raw_summary}_")

        st.markdown("---")
        st.subheader("Prevention Artifacts")
        st.markdown("Generated automatically from this report:")

        with st.spinner("Creating prevention artifacts..."):
            artifacts = generate_all(chunk)
            save_artifacts(chunk, artifacts)

        art_tabs = st.tabs(["🧪 Regression Test", "📊 Monitoring Rule", "📋 Response Runbook", "🎫 Prevention Ticket"])

        with art_tabs[0]:
            st.markdown("**What this does:** A test that would have caught this bug in CI before it reached production.")
            with st.expander("View test code"):
                st.code(artifacts["regression_test.py"], language="python")
            st.download_button("Download regression_test.py", artifacts["regression_test.py"], "regression_test.py")

        with art_tabs[1]:
            st.markdown("**What this does:** An alert rule tuned to the exact thresholds seen during this incident.")
            with st.expander("View monitoring rule"):
                st.code(artifacts["monitor.yaml"], language="yaml")
            st.download_button("Download monitor.yaml", artifacts["monitor.yaml"], "monitor.yaml")

        with art_tabs[2]:
            st.markdown("**What this does:** Step-by-step response guide with exact commands for the next time this pattern appears.")
            st.markdown(artifacts["runbook.md"])
            st.download_button("Download runbook.md", artifacts["runbook.md"], "runbook.md")

        with art_tabs[3]:
            st.markdown("**What this does:** A ready-to-file ticket covering the prevention work, acceptance criteria, and definition of done.")
            st.markdown(artifacts["ticket.md"])
            st.download_button("Download ticket.md", artifacts["ticket.md"], "ticket.md")


# ── TAB 2: ASSESS A PR ────────────────────────────────────────────────────────

with tab_pr:
    st.subheader("Assess a Code Change for Risk")
    st.markdown(
        "Paste a pull request diff. The system searches past incident memory for matching "
        "patterns and tells you whether this change is safe to merge."
    )

    if memory_count() == 0:
        st.info("No incidents in memory yet — add a report from the first tab to enable risk assessment.")

    load_col1, load_col2, _ = st.columns([1, 1, 4])
    bad_path = SAMPLE_DIR / "future_pr_bad.diff"
    safe_path = SAMPLE_DIR / "future_pr_safe.diff"
    if bad_path.exists() and load_col1.button("Load risky example"):
        st.session_state["diff_text"] = bad_path.read_text()
    if safe_path.exists() and load_col2.button("Load safe example"):
        st.session_state["diff_text"] = safe_path.read_text()

    diff_text = st.text_area(
        "Pull request diff",
        value=st.session_state.get("diff_text", ""),
        height=220,
        placeholder="Paste the output of `git diff` here...",
    )

    if st.button("🔍 Assess Risk", type="primary", disabled=not diff_text.strip()):
        with st.spinner("Checking against past incidents..."):
            result = route(diff_text)

        decision = result["decision"]
        score = result["risk_score"]

        if decision == "safe":
            st.success(f"## {result['decision_label']}")
        elif decision == "needs-review":
            st.warning(f"## {result['decision_label']}")
        else:
            st.error(f"## {result['decision_label']}")

        col1, col2 = st.columns([1, 3])
        col1.metric("Risk Score", f"{score} / 10")
        with col2:
            st.markdown("**Assessment**")
            st.markdown(result["recommendation"])

        if result["warnings"]:
            st.markdown("**Specific concerns:**")
            for w in result["warnings"]:
                st.markdown(f"- {w}")

        if result["matched_incidents"]:
            sev_icons = {"SEV-1": "🔴", "SEV-2": "🟠", "SEV-3": "🟡", "SEV-4": "🟢"}
            with st.expander(f"Past incidents this resembles ({len(result['matched_incidents'])})"):
                for c in result["matched_incidents"]:
                    icon = sev_icons.get(c.severity, "⚪")
                    st.markdown(
                        f"**{icon} {c.component}** — {c.date}  \n"
                        f"What happened: {c.root_cause}  \n"
                        f"How it was fixed: {c.fix_pattern}"
                    )
                    st.divider()


# ── TAB 3: INCIDENT HISTORY ───────────────────────────────────────────────────

with tab_history:
    st.subheader("Incident History")

    chunks = all_chunks()
    if not chunks:
        st.info("No incidents recorded yet. Add your first report from the **Add Incident Report** tab.")
    else:
        sev_icons = {"SEV-1": "🔴", "SEV-2": "🟠", "SEV-3": "🟡", "SEV-4": "🟢"}

        import pandas as pd
        rows = [
            {
                "Severity": f"{sev_icons.get(c.severity, '⚪')} {c.severity}",
                "System": c.component,
                "Date": c.date,
                "What went wrong": c.root_cause,
                "How it was detected": c.detection_signal,
            }
            for c in sorted(chunks, key=lambda x: x.date, reverse=True)
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        with st.expander("Full incident details"):
            for c in sorted(chunks, key=lambda x: x.date, reverse=True):
                icon = sev_icons.get(c.severity, "⚪")
                st.markdown(f"### {icon} {c.component} — {c.date}")
                st.markdown(f"**What went wrong:** {c.root_cause}")
                st.markdown(f"**How it was fixed:** {c.fix_pattern}")
                st.markdown(f"**How it was detected:** {c.detection_signal}")
                st.divider()

        json_path = GENERATED_DIR / "incident_memory.json"
        if json_path.exists():
            st.download_button(
                "Export incident history (JSON)",
                json_path.read_text(),
                "incident_memory.json",
                mime="application/json",
            )
