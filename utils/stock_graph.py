import io
import math
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from dateutil.relativedelta import relativedelta
from PIL import Image
from plotly.subplots import make_subplots

DEFAULT_LOOKBACK_DAYS = 365
GENERATED_DIR = Path(__file__).resolve().parents[1] / 'generated'


def normalize_ticker(token: str) -> str:
    token = token.strip().upper()
    token = re.sub(r"\s+", " ", token)
    if not token:
        return ""

    jp_match = re.fullmatch(r"(\d{4})[ .]?(?:JT|JP|T)", token)
    if jp_match:
        return f"{jp_match.group(1)}.T"

    hk_match = re.fullmatch(r"(\d{1,5})[ .]?HK", token)
    if hk_match:
        return f"{hk_match.group(1).zfill(4)}.HK"

    tw_match = re.fullmatch(r"(\d{4})[ .]?TW", token)
    if tw_match:
        return f"{tw_match.group(1)}.TW"

    si_match = re.fullmatch(r"([A-Z0-9]{1,5})[ .]?SP", token)
    if si_match:
        return f"{si_match.group(1)}.SI"

    us_match = re.fullmatch(r"([A-Z][A-Z0-9.-]{0,9})\s+(?:US|UN|UQ|UW)", token)
    if us_match:
        return us_match.group(1)

    if token.endswith('.JT'):
        return token[:-3] + '.T'

    return token.replace(' ', '') if '.' in token else token


def parse_tickers(tickers_str: str) -> list[str]:
    raw_tokens = [t.strip() for t in tickers_str.split(',') if t.strip()]
    tickers = []
    seen = set()
    for token in raw_tokens:
        norm = normalize_ticker(token)
        if norm and norm not in seen:
            tickers.append(norm)
            seen.add(norm)
    return tickers


def create_output_path() -> Path:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    return GENERATED_DIR / filename


def get_logo_path() -> Path | None:
    repo_root = Path(__file__).resolve().parents[1]
    candidates = [
        repo_root / 'logo' / 'logo.png',
        repo_root / 'logo.png',
        repo_root / 'assets' / 'logo.png',
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def build_subplot_title(ticker: str, ytd_returns: dict, pe_ratios: dict) -> str:
    if ticker.startswith('^') or ticker.startswith('.'):
        base = ticker
        region = 'Index'
    elif ticker.endswith('.HK'):
        base = ticker.replace('.HK', '')
        region = 'HK'
    elif ticker.endswith('.SI'):
        base = ticker.replace('.SI', '')
        region = 'SG'
    elif ticker.endswith('.TW'):
        base = ticker.replace('.TW', '')
        region = 'TW'
    elif ticker.endswith('.JK'):
        base = ticker.replace('.JK', '')
        region = 'ID'
    elif ticker.endswith('.PA'):
        base = ticker.replace('.PA', '')
        region = 'FP'
    elif ticker.endswith('.DE'):
        base = ticker.replace('.DE', '')
        region = 'GR'
    elif ticker.endswith('.T'):
        base = ticker.replace('.T', '')
        region = 'JP'
    else:
        base = ticker
        region = 'US'

    yr = ytd_returns.get(ticker, np.nan)
    ytd_str = 'N/A' if pd.isna(yr) else ('flat' if abs(round(yr, 0)) < 0.5 else f"{round(yr, 0):+.0f}%")
    pe_val = pe_ratios.get(ticker, np.nan)
    pe_str = '' if pd.isna(pe_val) else f", {int(round(pe_val, 0))}x PE"
    title_region_part = f" {region}" if region != 'Index' else ''
    return f"<b>{base}{title_region_part}</b><br><span style='font-size: 24px;'>{ytd_str} ytd{pe_str}</span>"


def generate_chart(tickers: list[str], start_date: str, end_date: str) -> tuple[bytes, str]:
    year_start = f"{end_date[:4]}-01-01"
    chart_start_date = start_date
    output_path = create_output_path()
    temp_chart_path = output_path.with_name(output_path.stem + '_temp.png')

    download_start = min(start_date, year_start)
    raw = yf.download(
        tickers,
        start=download_start,
        end=(pd.to_datetime(end_date) + pd.Timedelta(days=1)).strftime('%Y-%m-%d'),
        auto_adjust=False,
        progress=False,
        threads=True,
    )
    if raw.empty:
        raise ValueError('No data available for the given tickers and date range.')

    data = raw['Adj Close']
    close_data = raw['Close']

    if isinstance(data, pd.Series):
        data = data.to_frame(name=tickers[0])
    if isinstance(close_data, pd.Series):
        close_data = close_data.to_frame(name=tickers[0])

    chart_data_df = data.loc[chart_start_date:end_date].dropna(how='all')
    if chart_data_df.empty:
        raise ValueError('No data available for the chart date range.')

    first_values = chart_data_df.apply(lambda x: x.dropna().iloc[0] if not x.dropna().empty else np.nan)
    valid_tickers = first_values.dropna().index.tolist()
    if len(valid_tickers) == 0:
        raise ValueError('No valid tickers with data in the specified range.')

    percentage_change_df = (chart_data_df[valid_tickers] / first_values[valid_tickers] - 1) * 100

    ma_df = pd.DataFrame(index=chart_data_df.index)
    for ticker in valid_tickers:
        ma_series = chart_data_df[ticker].rolling(window=20, min_periods=1).mean()
        ma_percentage = (ma_series / first_values[ticker] - 1) * 100
        ma_df[ticker] = ma_percentage

    ytd_returns = {}
    year_start_ts = pd.to_datetime(year_start)
    for ticker in valid_tickers:
        try:
            s = close_data[ticker].dropna()
            s_after = s[s.index >= year_start_ts]
            if not s_after.empty:
                first_price = s_after.iloc[0]
                last_price = s.iloc[-1]
                if pd.notna(first_price) and first_price != 0 and pd.notna(last_price):
                    ytd_returns[ticker] = (last_price / first_price - 1) * 100
                else:
                    ytd_returns[ticker] = np.nan
            else:
                ytd_returns[ticker] = np.nan
        except Exception:
            ytd_returns[ticker] = np.nan

    pe_ratios = {}
    for ticker in valid_tickers:
        try:
            stock = yf.Ticker(ticker)
            pe_ratios[ticker] = stock.info.get('trailingPE', np.nan)
        except Exception:
            pe_ratios[ticker] = np.nan

    last_values = percentage_change_df.apply(lambda x: x.dropna().iloc[-1] if not x.dropna().empty else np.nan)
    sorted_tickers = last_values.sort_values(ascending=False).index.tolist()
    num_charts = len(sorted_tickers)

    if num_charts <= 2:
        v_spacing = 0
    elif num_charts <= 4:
        v_spacing = 240
    elif num_charts <= 6:
        v_spacing = 220
    elif num_charts <= 8:
        v_spacing = 190
    else:
        v_spacing = 180

    legend_y = {0: 1.6, 2: 1.6, 4: 1.3, 6: 1.15, 8: 1.106}.get(
        next((i for i in [0, 2, 4, 6, 8] if num_charts <= i), 8),
        1.075,
    )
    title_y = {0: 0.95, 2: 0.945, 4: 0.96, 6: 0.97, 8: 0.98}.get(
        next((i for i in [0, 2, 4, 6, 8] if num_charts <= i), 8),
        0.98,
    )

    ncols = 2
    nrows = math.ceil(num_charts / ncols)
    aspect_ratio = 10 / 5
    subplot_height = 250
    subplot_width = aspect_ratio * subplot_height
    h_spacing = 100
    top_margin = 200
    bottom_margin = 168

    fig_width = ncols * subplot_width + (ncols - 1) * h_spacing
    fig_height = nrows * subplot_height + (nrows - 1) * v_spacing + top_margin + bottom_margin

    horizontal_spacing = h_spacing / fig_width if ncols > 1 else 0
    vertical_spacing = v_spacing / fig_height if nrows > 1 else 0

    subplot_titles = [build_subplot_title(ticker, ytd_returns, pe_ratios) for ticker in sorted_tickers]
    total_subplots = nrows * ncols
    all_titles = subplot_titles + [''] * (total_subplots - len(subplot_titles))

    fig = make_subplots(
        rows=nrows,
        cols=ncols,
        subplot_titles=all_titles,
        shared_xaxes=False,
        shared_yaxes=False,
        vertical_spacing=vertical_spacing,
        horizontal_spacing=horizontal_spacing,
    )

    for i, ticker in enumerate(sorted_tickers):
        row = i // ncols + 1
        col = i % ncols + 1
        series = percentage_change_df[ticker].dropna()
        current_last_value = last_values.get(ticker, np.nan)
        color = 'green' if pd.notna(current_last_value) and current_last_value > 0 else 'red'
        fig.add_trace(
            go.Scatter(
                x=series.index,
                y=series.values,
                mode='lines',
                name=ticker,
                line=dict(color=color),
                showlegend=False,
            ),
            row=row,
            col=col,
        )
        if ticker in ma_df.columns:
            fig.add_trace(
                go.Scatter(
                    x=ma_df.index,
                    y=ma_df[ticker],
                    mode='lines',
                    name=f'{ticker} 20d MA',
                    line=dict(color='#3f9ece', dash='2px,2px'),
                    showlegend=False,
                ),
                row=row,
                col=col,
            )

    start_dt = pd.to_datetime(chart_start_date)
    end_dt = pd.to_datetime(end_date)
    start_month = start_dt.to_period('M')
    end_month = end_dt.to_period('M')
    months = pd.date_range(start=start_month.start_time, end=end_month.start_time, freq='MS')
    num_months = len(months)

    if num_months <= 5:
        dtick = 'M1'
        tick0 = months[0].strftime('%Y-%m-%d') if len(months) else start_dt.strftime('%Y-%m-%d')
    else:
        parity = end_month.month % 2
        tick0_found = False
        tick0 = start_dt.strftime('%Y-%m-%d')
        for m in months:
            if m.month % 2 == parity:
                tick0 = m.strftime('%Y-%m-%d')
                tick0_found = True
                break
        if not tick0_found and len(months):
            tick0 = months[0].strftime('%Y-%m-%d')
        dtick = 'M2'

    freq = 'MS' if dtick == 'M1' else '2MS'
    try:
        tickvals = pd.date_range(start=tick0, end=end_dt, freq=freq)
        tickvals = tickvals[(tickvals >= start_dt) & (tickvals <= end_dt)]
    except ValueError:
        tickvals = pd.date_range(start=start_dt, end=end_dt, freq='MS')
        if num_months > 5:
            tickvals = tickvals[::2]

    current_date = datetime.now()
    target_month_prev_year = current_date - relativedelta(months=10)
    target_year = target_month_prev_year.year
    target_month = target_month_prev_year.month

    prev_year_ticks = [date for date in tickvals if date.year == target_year]
    closest_tick = None
    if prev_year_ticks:
        closest_tick = min(prev_year_ticks, key=lambda d: abs(d.month - target_month))

    ticktext = []
    displayed_years = set()
    for date in tickvals:
        year = date.year
        month_label = f"<span style='font-size:100%; color: black;'>{date.strftime('%b')}</span>"
        year_label = ''
        is_first_for_year = year not in displayed_years
        is_target_prev_year_tick = year == target_year and closest_tick is not None and date == closest_tick
        if is_first_for_year or is_target_prev_year_tick:
            year_label = f"<br><span style='font-size:80%; color: gray;'>{year}</span>"
            displayed_years.add(year)
        ticktext.append(f'{month_label}{year_label}')

    fig.update_xaxes(
        range=[chart_start_date, end_date],
        tickvals=tickvals,
        ticktext=ticktext,
        tickangle=0,
    )

    for j in range(len(sorted_tickers), total_subplots):
        row = j // ncols + 1
        col = j % ncols + 1
        fig.update_xaxes(visible=False, row=row, col=col)
        fig.update_yaxes(visible=False, row=row, col=col)

    fig.update_yaxes(ticksuffix='%')
    for r in range(1, nrows + 1):
        fig.update_yaxes(title_text='Performance', row=r, col=1)
        for c in range(2, ncols + 1):
            fig.update_yaxes(title_text=None, row=r, col=c)

    title_text = "<span style='font-size:120%;'><b>Stocks mentioned in the news</b></span><br>1Y Performance"
    fig.update_layout(
        title_text=title_text,
        title_font=dict(family='Arial', color='black', size=40),
        title_x=0.5,
        title_y=title_y,
        margin=dict(l=20, r=20, t=top_margin, b=bottom_margin),
        font=dict(family='Arial', color='black', size=20),
        showlegend=True,
        legend=dict(
            x=1,
            y=legend_y,
            xanchor='right',
            yanchor='top',
            bgcolor='rgba(255,255,255,0.5)',
            bordercolor='black',
            borderwidth=1,
        ),
        width=int(fig_width),
        height=int(fig_height),
        autosize=False,
        plot_bgcolor='#f5f5f5',
    )

    for annotation in fig['layout']['annotations']:
        annotation['font'] = dict(family='Arial', color='black', size=36)

    fig.write_image(str(temp_chart_path))

    logo_path = get_logo_path()
    if logo_path and logo_path.exists():
        try:
            chart_img = Image.open(temp_chart_path)
            logo_img = Image.open(logo_path)
            max_logo_size = 200
            if logo_img.width > max_logo_size or logo_img.height > max_logo_size:
                logo_img.thumbnail((max_logo_size, max_logo_size), Image.Resampling.LANCZOS)
            position = (0, chart_img.height - logo_img.height)
            chart_img.paste(logo_img, position, logo_img if logo_img.mode == 'RGBA' else None)
            chart_img.save(output_path)
            temp_chart_path.unlink(missing_ok=True)
        except Exception:
            temp_chart_path.replace(output_path)
    else:
        temp_chart_path.replace(output_path)

    image_bytes = output_path.read_bytes()
    return image_bytes, output_path.name
