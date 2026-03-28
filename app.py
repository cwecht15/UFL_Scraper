from __future__ import annotations

from pathlib import Path

import streamlit as st

from scrape_foxsports_ufl_pbp import (
    AMBIGUITY_REPORT_HEADERS,
    DEFAULT_ROSTER,
    DEFAULT_TEMPLATE,
    csv_text,
    default_output_path,
    extract_rows,
)


st.set_page_config(page_title="UFL Fox Sports PBP Exporter", page_icon="football", layout="wide")


def app_css() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top right, rgba(158, 201, 88, 0.18), transparent 32%),
                linear-gradient(180deg, #f8f4ec 0%, #f2eee5 100%);
        }
        .hero {
            padding: 1.2rem 1.4rem;
            border: 1px solid rgba(33, 33, 33, 0.08);
            border-radius: 18px;
            background: rgba(255, 255, 255, 0.82);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
            margin-bottom: 1rem;
        }
        .hero h1 {
            font-size: 2rem;
            margin: 0 0 0.3rem 0;
            color: #18220f;
        }
        .hero p {
            margin: 0;
            color: #44503b;
            font-size: 1rem;
        }
        .note-card {
            padding: 0.9rem 1rem;
            border-radius: 14px;
            background: rgba(24, 34, 15, 0.05);
            border: 1px solid rgba(24, 34, 15, 0.08);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def validate_inputs() -> list[str]:
    issues: list[str] = []
    if not DEFAULT_TEMPLATE.exists():
        issues.append(f"Missing template file: {DEFAULT_TEMPLATE}")
    if not DEFAULT_ROSTER.exists():
        issues.append(f"Missing roster file: {DEFAULT_ROSTER}")
    return issues


def main() -> None:
    app_css()

    st.markdown(
        """
        <div class="hero">
            <h1>UFL Fox Sports PBP Exporter</h1>
            <p>Paste a Fox Sports UFL game URL to generate a play-by-play CSV and an ambiguity report you can download immediately.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    issues = validate_inputs()
    if issues:
        for issue in issues:
            st.error(issue)
        st.stop()

    with st.sidebar:
        st.subheader("What You Get")
        st.markdown(
            """
            - Play-by-play CSV in the sample schema
            - Ambiguity report for short-name collisions
            - Missing-target warnings for thrown passes
            - Automatic roster-based full-name enrichment
            """
        )
        st.markdown('<div class="note-card">Built for Fox Sports UFL game pages with the play-by-play tab.</div>', unsafe_allow_html=True)

    default_url = "https://www.foxsports.com/ufl/week-1-birmingham-stallions-vs-louisville-kings-mar-27-2026-game-boxscore-87?tab=playbyplay"
    game_url = st.text_input("Fox Sports game URL", value=default_url, placeholder="https://www.foxsports.com/ufl/...")

    col1, col2 = st.columns([1, 3])
    with col1:
        run_clicked = st.button("Generate CSVs", type="primary", use_container_width=True)
    with col2:
        st.caption("The app uses the local roster file to enrich player names and writes the ambiguity report automatically.")

    if not run_clicked:
        return

    if not game_url.strip():
        st.error("Enter a Fox Sports game URL first.")
        return

    try:
        with st.spinner("Scraping Fox Sports play-by-play and building exports..."):
            headers, rows, ambiguity_rows = extract_rows(game_url.strip(), DEFAULT_TEMPLATE, DEFAULT_ROSTER)
            pbp_csv = csv_text(headers, rows)
            ambiguity_csv = csv_text(AMBIGUITY_REPORT_HEADERS, ambiguity_rows)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not generate outputs: {exc}")
        return

    output_name = default_output_path(game_url.strip())
    ambiguity_name = output_name.with_name(f"{output_name.stem}_ambiguity_report.csv")

    stats = st.columns(3)
    stats[0].metric("Rows", max(len(rows) - 1, 0))
    stats[1].metric("Ambiguity Rows", len(ambiguity_rows))
    stats[2].metric("Files", 2)

    download_cols = st.columns(2)
    with download_cols[0]:
        st.download_button(
            "Download Play-by-Play CSV",
            data=pbp_csv,
            file_name=output_name.name,
            mime="text/csv",
            use_container_width=True,
        )
    with download_cols[1]:
        st.download_button(
            "Download Ambiguity Report",
            data=ambiguity_csv,
            file_name=ambiguity_name.name,
            mime="text/csv",
            use_container_width=True,
        )

    st.subheader("Preview")
    st.caption("Top rows from the generated play-by-play export.")
    st.dataframe(rows[:15], use_container_width=True, hide_index=True)

    st.subheader("Ambiguity Report")
    if ambiguity_rows:
        st.dataframe(ambiguity_rows, use_container_width=True, hide_index=True)
    else:
        st.success("No ambiguity or missing-player issues were found for this game.")


if __name__ == "__main__":
    main()
