from datetime import datetime, timedelta
import html

import streamlit as st
import streamlit.components.v1 as components

from utils.stock_graph import DEFAULT_LOOKBACK_DAYS, generate_chart, parse_tickers
from utils.ticker_assistant import process_text_with_stock_data

st.set_page_config(
    page_title="Morning Routine Program",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      section[data-testid="stSidebar"] {display: none !important;}
      [data-testid="collapsedControl"] {display: none !important;}
      .block-container {
        padding-top: 1.2rem;
        padding-bottom: 1rem;
        max-width: 96rem;
      }
      .tool-title {
        font-size: 1.35rem;
        font-weight: 700;
        margin-bottom: 0.15rem;
      }
      .tool-sub {
        color: #666;
        font-size: 0.92rem;
        margin-bottom: 0.8rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

if "ticker_input_text" not in st.session_state:
    st.session_state.ticker_input_text = (
        "Paste your text here.\n\n"
        "Example:\n"
        "Apple (AAPL US) and DBS (D05 SG) are in focus today.\n"
        "TSMC (2330 TW) also remains interesting."
    )
if "ticker_output_text" not in st.session_state:
    st.session_state.ticker_output_text = ""
if "ticker_logs" not in st.session_state:
    st.session_state.ticker_logs = []
if "chart_image_bytes" not in st.session_state:
    st.session_state.chart_image_bytes = None
if "chart_filename" not in st.session_state:
    st.session_state.chart_filename = ""
if "chart_error" not in st.session_state:
    st.session_state.chart_error = ""
if "chart_tickers_input" not in st.session_state:
    st.session_state.chart_tickers_input = "AAPL, MSFT, NVDA"

st.title("Morning Routine Program")

left, right = st.columns(2, gap="large")

with left:
    with st.container(border=True):
        st.markdown('<div class="tool-title">Ticker Assistant</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="tool-sub">Paste text and process ticker tags directly on this page.</div>',
            unsafe_allow_html=True,
        )

        st.text_area(
            "Input text",
            key="ticker_input_text",
            height=300,
            label_visibility="visible",
        )

        ta_col1, ta_col2 = st.columns(2)
        process_clicked = ta_col1.button("Process Text", use_container_width=True)
        clear_clicked = ta_col2.button("Clear", use_container_width=True)

        if clear_clicked:
            st.session_state.ticker_input_text = ""
            st.session_state.ticker_output_text = ""
            st.session_state.ticker_logs = []
            st.rerun()

        if process_clicked:
            if not st.session_state.ticker_input_text.strip():
                st.error("The text area is empty. Please enter some content and try again.")
            else:
                with st.spinner("Processing..."):
                    output_text, logs = process_text_with_stock_data(st.session_state.ticker_input_text)
                st.session_state.ticker_output_text = output_text
                st.session_state.ticker_logs = logs

        if st.session_state.ticker_output_text:
            st.subheader("Processed text")
            st.text_area(
                "Output",
                value=st.session_state.ticker_output_text,
                height=300,
                key="ticker_output_display",
            )

            escaped_text = html.escape(st.session_state.ticker_output_text)
            components.html(
                f"""
                <div style="margin-top:8px;margin-bottom:8px;">
                  <button
                    onclick="navigator.clipboard.writeText(document.getElementById('processed_text_value').value)"
                    style="
                      width:100%;
                      background:#ff4b4b;
                      color:white;
                      border:none;
                      border-radius:8px;
                      padding:0.7rem 1rem;
                      font-size:1rem;
                      font-weight:600;
                      cursor:pointer;
                    "
                  >
                    Copy processed text
                  </button>
                  <textarea id="processed_text_value" style="position:absolute;left:-9999px;top:-9999px;">{escaped_text}</textarea>
                </div>
                """,
                height=60,
            )

            if st.session_state.ticker_logs:
                st.subheader("Logs")
                st.code("\n".join(st.session_state.ticker_logs), language="text")

with right:
    with st.container(border=True):
        st.markdown('<div class="tool-title">Stock Graph Generator</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="tool-sub">Generates the same PNG chart logic as the original desktop version.</div>',
            unsafe_allow_html=True,
        )

        tickers_input = st.text_input(
            "Tickers",
            key="chart_tickers_input",
            help="Examples: AAPL, 9988.HK, 8306.T, ^GSPC, 175 HK, 9984 JT, MSFT US",
        )
        st.caption("Uses fixed original behavior: latest 365 days only. Put your logo file at logo/logo.png if needed.")

        if st.button("Generate Chart", use_container_width=True):
            tickers = parse_tickers(tickers_input)
            if not tickers:
                st.session_state.chart_error = "Please enter at least one ticker."
                st.session_state.chart_image_bytes = None
                st.session_state.chart_filename = ""
            else:
                st.session_state.chart_error = ""
                with st.spinner("Downloading price data and generating chart..."):
                    try:
                        end_date = datetime.now().strftime("%Y-%m-%d")
                        start_date = (datetime.now() - timedelta(days=DEFAULT_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
                        image_bytes, filename = generate_chart(
                            tickers=tickers,
                            start_date=start_date,
                            end_date=end_date,
                        )
                        st.session_state.chart_image_bytes = image_bytes
                        st.session_state.chart_filename = filename
                    except Exception as exc:
                        st.session_state.chart_image_bytes = None
                        st.session_state.chart_filename = ""
                        st.session_state.chart_error = str(exc)

        if st.session_state.chart_error:
            st.error(st.session_state.chart_error)

        if st.session_state.chart_image_bytes:
            st.image(st.session_state.chart_image_bytes, use_container_width=True)
            st.download_button(
                "Download PNG",
                data=st.session_state.chart_image_bytes,
                file_name=st.session_state.chart_filename,
                mime="image/png",
                use_container_width=True,
            )
