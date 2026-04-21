import re
import time
from decimal import Decimal, ROUND_HALF_UP

import yfinance as yf


def custom_round(n):
    if n is None:
        return None
    try:
        return int(Decimal(str(n)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except Exception:
        return None


def get_stock_data(symbol, market, cache, log_messages=None):
    if market == 'US':
        ticker_symbol = f'{symbol}'
    elif market == 'HK':
        ticker_symbol = f'{symbol}.HK'
    elif market == 'SG':
        ticker_symbol = f'{symbol}.SI'
    elif market == 'TW':
        ticker_symbol = f'{symbol}.TW'
    elif market == 'ID':
        ticker_symbol = f'{symbol}.JK'
    else:
        if log_messages is not None:
            log_messages.append(f'Unsupported market: {market}')
        return {'ytd_change': None, 'pe_ratio': None}

    if ticker_symbol in cache:
        return cache[ticker_symbol]

    try:
        if log_messages is not None:
            log_messages.append(f'Fetching: {ticker_symbol}...')
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        pe_ratio, ytd_change = None, None

        if info and info.get('quoteType') not in ['INDEX', 'MUTUALFUND', 'ETF', 'CURRENCY', None]:
            pe_ratio = info.get('trailingPE')
            if pe_ratio is not None and pe_ratio <= 0:
                pe_ratio = None

        hist = stock.history(period='ytd', auto_adjust=False)
        if not hist.empty and 'Close' in hist.columns and len(hist['Close']) >= 2:
            hist = hist.sort_index()
            current_price = hist['Close'].iloc[-1]
            start_price = hist['Close'].iloc[0]
            if start_price is not None and start_price != 0:
                ytd_change = (current_price - start_price) / start_price

        data = {'ytd_change': ytd_change, 'pe_ratio': pe_ratio}
        cache[ticker_symbol] = data
        time.sleep(0.25)
        return data
    except Exception as e:
        if log_messages is not None:
            log_messages.append(f'Error {ticker_symbol}: {str(e)}')
        cache[ticker_symbol] = {'ytd_change': None, 'pe_ratio': None}
        return {'ytd_change': None, 'pe_ratio': None}


def process_text_with_stock_data(input_text):
    cache = {}
    pattern = r'\(([^)\s]+)\s+(US|HK|SG|TW|ID)\)'
    matches = re.findall(pattern, input_text)
    replacements = {}
    unique_combinations = sorted(list(set(matches)))
    log_messages = [f'Found {len(unique_combinations)} unique stock ticker combinations to process...']

    for symbol, market in unique_combinations:
        data = get_stock_data(symbol, market, cache, log_messages=log_messages)
        ytd_change, pe_ratio = data['ytd_change'], data['pe_ratio']

        ytd_display = 'N/A ytd'
        if ytd_change is not None:
            try:
                ytd_percentage = ytd_change * 100
                rounded_ytd_int = custom_round(ytd_percentage)
                if rounded_ytd_int == 0:
                    ytd_display = 'flat ytd'
                else:
                    sign = '+' if rounded_ytd_int > 0 else ''
                    ytd_display = f'{sign}{rounded_ytd_int}% ytd'
            except Exception as e:
                log_messages.append(f'YTD formatting error {symbol} {market}: {e}')
                ytd_display = 'Error ytd'

        pe_display = ''
        rounded_pe = custom_round(pe_ratio)
        if rounded_pe is not None and rounded_pe > 0:
            pe_display = f'{rounded_pe}x PE'

        additional_info = ''
        if ytd_display not in ['N/A ytd', 'Error ytd']:
            additional_info += f', {ytd_display}'
        if pe_display:
            additional_info += f', {pe_display}'

        original = f'({symbol} {market})'
        replacement = f'({symbol} {market}{additional_info})'
        replacements[original] = replacement

    output_text = input_text
    for original in sorted(replacements.keys(), key=len, reverse=True):
        output_text = output_text.replace(original, replacements[original])

    log_messages.append('Replacement completed.')
    return output_text, log_messages
