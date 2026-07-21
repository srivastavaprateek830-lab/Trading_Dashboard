"""
shared/theme.py
Injects the Signal Matrix Pro visual language into the Streamlit dashboard -
colors, fonts, and card styling pulled directly from the original Lovable
project's design tokens (src/index.css), so the real, working dashboard
looks the same as the mockup that was reviewed and approved.

Call inject_theme() once near the top of every page.
"""

import streamlit as st

COLORS = {
    "background": "#090d15",
    "card": "#0f141f",
    "foreground": "#f2f5f8",
    "muted_fg": "#8796ab",
    "primary": "#1eeba0",   # success / bullish
    "accent": "#26b2f2",
    "destructive": "#e44444",  # bearish
    "warning": "#faaf2e",
    "border": "#1f2533",
}


def inject_theme():
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=JetBrains+Mono:wght@400;600&display=swap');

        html, body, [class*="css"] {{
            font-family: 'Space Grotesk', sans-serif;
        }}

        h1, h2, h3 {{
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 700;
        }}

        code, .stCodeBlock, [data-testid="stMetricValue"] {{
            font-family: 'JetBrains Mono', monospace;
        }}

        /* Card-style containers (matches Lovable's bg-card/60 border-border) */
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background-color: {COLORS['card']};
            border: 1px solid {COLORS['border']};
            border-radius: 10px;
        }}

        /* Metric cards */
        [data-testid="stMetric"] {{
            background-color: {COLORS['card']};
            border: 1px solid {COLORS['border']};
            border-radius: 10px;
            padding: 1rem;
        }}

        /* Sidebar */
        section[data-testid="stSidebar"] {{
            background-color: #070b12;
            border-right: 1px solid {COLORS['border']};
        }}

        /* Buttons - primary accent matches the teal/green brand color */
        .stButton > button {{
            background-color: {COLORS['primary']};
            color: {COLORS['background']};
            border: none;
            border-radius: 8px;
            font-weight: 600;
        }}
        .stButton > button:hover {{
            background-color: {COLORS['accent']};
            color: {COLORS['background']};
        }}

        /* Signal badges - use badge(label, kind) below to render these */
        .signal-badge {{
            display: inline-block;
            padding: 2px 10px;
            border-radius: 6px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            font-weight: 600;
        }}
        .signal-buy {{
            background-color: rgba(30, 235, 160, 0.12);
            color: {COLORS['primary']};
            border: 1px solid rgba(30, 235, 160, 0.4);
        }}
        .signal-sell {{
            background-color: rgba(228, 68, 68, 0.12);
            color: {COLORS['destructive']};
            border: 1px solid rgba(228, 68, 68, 0.4);
        }}
        .signal-flat {{
            background-color: rgba(135, 150, 171, 0.12);
            color: {COLORS['muted_fg']};
            border: 1px solid rgba(135, 150, 171, 0.3);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def badge(label: str, kind: str = "flat") -> str:
    """Returns HTML for a colored signal badge - kind is 'buy', 'sell', or 'flat'."""
    return f'<span class="signal-badge signal-{kind}">{label}</span>'
