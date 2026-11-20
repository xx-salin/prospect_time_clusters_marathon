'''
Scrape New York City Marathon finishers from the New York Road Runners
results API (results.nyrr.org), for matching to the Allen, Dechow, Pope and
Wu (2017) data.

Each runner has age, gender, net and gun time, country of residence and
citizenship (the 'iaaf' field, the World Athletics country code). Names,
cities and NYRR runner ids are not stored.

The API returns at most 500 runners per search and asks for the advanced
filter beyond that, so each year is fetched in net-time windows, and any
window with more than 500 finishers is split in half until it fits.

Usage:
    python3 scrape_nyc.py pilot          # 2013, 3:30:00 to 4:29:59
    python3 scrape_nyc.py                # every year in EVENT_CODES
    python3 scrape_nyc.py 2013 2011      # chosen years

Each finished window is saved in raw_windows/ and recorded in
raw_windows/manifest.csv, so full runs resume if interrupted.

Sam Salin (svsalin, xx-salin)
'''

import math
import os
import sys
import time
import pandas as pd
import requests
import scrape_boston as sbf
import scrape_boston_pilot as sb

# Defined constants for column names
YEAR = 'year'
BIB = 'bib'
AGE = 'age'
GENDER = 'gender'
COUNTRY_RES = 'country_residence'
NATIONALITY = 'nationality'
OVERALL_PLACE = 'overall_place'
NET_TIME = 'net_time'
GUN_TIME = 'gun_time'
NET_SEC = 'net_sec'
GUN_SEC = 'gun_sec'

API_URL = 'https://rmsprodapi.nyrr.org/api/v2/runners/finishers-filter'
HEADERS = {'User-Agent': sb.USER_AGENT,
           'Content-Type': 'application/json',
           'Origin': 'https://results.nyrr.org',
           'Referer': 'https://results.nyrr.org/'}

# NYRR event codes for the years the study has runner age (no 2012 race)
EVENT_CODES = {1999: '991107', 2000: 'NYC2000', 2001: 'b11106',
               2002: 'NYC2002', 2003: 'NYC2003', 2004: 'a41107',
               2005: 'a51106', 2006: 'a61105', 2007: 'a71104',
               2008: 'a81102', 2009: 'a91101', 2010: 'b01107',
               2011: '108', 2013: '40'}

# API field -> our column; everything else (names, city, ids) is dropped
FIELD_MAP = {'bib': BIB, 'age': AGE, 'gender': GENDER,
             'countryCode': COUNTRY_RES, 'iaaf': NATIONALITY,
             'overallPlace': OVERALL_PLACE, 'overallTime': NET_TIME,
             'gunTime': GUN_TIME}

# NYRR codes women as 'W'; the study uses 'F'
GENDER_CODES = {'W': 'F'}

PAGE_SIZE = 100        # largest page the API accepts
MAX_RESULTS = 500      # most runners one search will page through
SORT_COLUMN = 'overallTime'
DELAY = sb.DELAY       # seconds between requests
MAX_TRIES = sbf.MAX_TRIES
RETRY_WAIT = sbf.RETRY_WAIT

SCRAPE_DIR = os.path.join(sb.ROOT_DIR, 'scraped_data', 'nyc')
RAW_DIR = os.path.join(SCRAPE_DIR, 'raw_windows')
PILOT_YEAR = 2013
PILOT_WINDOW = (3 * 3600 + 30 * 60, 4 * 3600 + 29 * 60 + 59)
PILOT_FILE = os.path.join(SCRAPE_DIR, 'pilot', 'nyc_2013_pilot.csv')


def format_seconds(seconds):
    '''
    Purpose: format seconds as H:MM:SS, the API's time filter format

    Inputs:
        seconds (int)

    Returns: (str) e.g. 14399 -> '3:59:59'
    '''

    return f'{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}'


def make_windows():
    '''
    Purpose: starting net-time windows, in seconds: under 2:30, then
      10 minutes at a time to 7:00, then everything slower

    Returns: (list of tuple) (low, high) in seconds, inclusive
    '''

    edges = [0] + list(range(150 * 60, 420 * 60 + 1, 10 * 60))
    windows = [(low, high - 1) for low, high in zip(edges, edges[1:])]
    windows.append((420 * 60, 24 * 3600 - 1))

    return windows


def post_with_retry(session, payload):
    '''
    Purpose: send one API request, waiting and retrying on network or
      server errors (a 4xx error means a bad request and is not retried)

    Inputs:
        session (requests.Session)
        payload (dict): JSON body

    Returns: (dict) the decoded JSON response
    '''

    wait = RETRY_WAIT
    for attempt in range(1, MAX_TRIES + 1):
        try:
            response = session.post(API_URL, json=payload,
                                    timeout=sb.TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as err:
            if err.response.status_code < 500 or attempt == MAX_TRIES:
                raise
        except requests.RequestException:
            if attempt == MAX_TRIES:
                raise
        print(f'  request failed; retry in {wait}s', flush=True)
        time.sleep(wait)
        wait *= 2


# Task 1
def fetch_page(session, year, page_index, low=None, high=None,
               page_size=PAGE_SIZE):
    '''
    Purpose: get one page of finishers sorted by net time, optionally
      only those with net time between low and high

    Inputs:
        session (requests.Session)
        year (int): race year
        page_index (int): page number, starting at 1
        low, high (int): net-time bounds in seconds, inclusive
        page_size (int): runners per page

    Returns: (list of dict) runners on the page, (int) total finishers
      matching the search
    '''

    payload = {'eventCode': EVENT_CODES[year], 'searchString': None,
               'handicap': None, 'sortColumn': SORT_COLUMN,
               'sortDescending': False, 'pageIndex': page_index,
               'pageSize': page_size}
    if low is not None:
        payload['overallTimeFrom'] = format_seconds(low)
        payload['overallTimeTo'] = format_seconds(high)

    data = post_with_retry(session, payload)
    time.sleep(DELAY)

    return data.get('items') or [], data.get('totalItems', 0)


# Task 2
def parse_runners(items, year):
    '''
    Purpose: keep only the fields needed for matching and clustering

    Inputs:
        items (list of dict): runners from fetch_page
        year (int): race year

    Returns: (list of dict) one dict per runner
    '''

    runners = []
    for item in items:
        runner = {YEAR: year}
        for field, col in FIELD_MAP.items():
            runner[col] = item.get(field)
        runners.append(runner)

    return runners


# Task 3
def scrape_window(session, year, low, high):
    '''
    Purpose: get every finisher with net time from low to high. If the
      search holds more than MAX_RESULTS runners, split the window in half
      and fetch each half.

    Inputs:
        session (requests.Session)
        year (int): race year
        low, high (int): net-time bounds in seconds, inclusive

    Returns: (int) finishers the API reports in the window,
      (list of dict) runners collected
    '''

    items, total = fetch_page(session, year, 1, low, high)

    if total > MAX_RESULTS and high > low:
        mid = (low + high) // 2
        total_low, runners_low = scrape_window(session, year, low, mid)
        total_high, runners_high = scrape_window(session, year, mid + 1,
                                                 high)
        return total_low + total_high, runners_low + runners_high

    runners = parse_runners(items, year)
    n_pages = min(math.ceil(total / PAGE_SIZE), MAX_RESULTS // PAGE_SIZE)
    for page_index in range(2, n_pages + 1):
        items, _ = fetch_page(session, year, page_index, low, high)
        runners.extend(parse_runners(items, year))

    return total, runners


def add_seconds(df):
    '''
    Purpose: drop repeated bibs, recode gender to the study's codes and
      add net and gun time in seconds

    Inputs:
        df (dataframe): runners from scrape_window

    Returns: (dataframe)
    '''

    df = df.drop_duplicates(subset=[YEAR, BIB]).copy()
    df[GENDER] = df[GENDER].replace(GENDER_CODES)
    # Some runners have no gun time; pandas reads those as NaN (a float)
    for time_col, sec_col in [(NET_TIME, NET_SEC), (GUN_TIME, GUN_SEC)]:
        df[sec_col] = df[time_col].map(
            lambda t: sb.time_to_seconds(t) if isinstance(t, str) else None)

    return df


# Task 4
def scrape_year(session, year, windows=None, raw_dir=RAW_DIR):
    '''
    Purpose: scrape every finisher of one year, saving each starting
      window and skipping windows already saved

    Inputs:
        session (requests.Session)
        year (int): race year
        windows (list of tuple): from make_windows
        raw_dir (str): folder for finished windows

    Returns: (dataframe) one row per bib, and (dict) the event's total
      finishers, the sum reported over the windows and the number
      collected
    '''

    if windows is None:
        windows = make_windows()
    os.makedirs(raw_dir, exist_ok=True)
    event_total = fetch_page(session, year, 1, page_size=1)[1]

    done = sbf.read_manifest(raw_dir)
    reported_total = 0
    frames = []
    for low, high in windows:
        tag = f'{year}_{low:05d}'
        if tag in done:
            reported_total += done[tag]
            frames.append(sbf.load_window(raw_dir, tag, done[tag]))
            continue

        reported, runners = scrape_window(session, year, low, high)
        window_df = pd.DataFrame(runners, columns=[YEAR] +
                                 list(FIELD_MAP.values()))
        if len(window_df):
            window_df.to_csv(os.path.join(raw_dir, f'{tag}.csv'),
                             index=False)
        sbf.record_window(raw_dir, tag, reported, window_df[BIB].nunique())
        reported_total += reported
        frames.append(window_df)
        print(f'{year} {format_seconds(low)}: reported {reported}, '
              f'collected {window_df[BIB].nunique()}', flush=True)

    year_df = add_seconds(pd.concat(frames))
    year_df.to_csv(os.path.join(SCRAPE_DIR, f'nyc_{year}.csv'), index=False)

    return year_df, {YEAR: year, 'event_total': event_total,
                     'reported': reported_total,
                     'collected': len(year_df)}


# Task 5
def scrape_pilot(session, year=PILOT_YEAR, window=PILOT_WINDOW):
    '''
    Purpose: scrape one net-time window of one year as a pilot

    Inputs:
        session (requests.Session)
        year (int): race year
        window (tuple): (low, high) net time in seconds

    Returns: (dataframe) runners, one row per bib
    '''

    reported, runners = scrape_window(session, year, *window)
    pilot = add_seconds(pd.DataFrame(runners))
    print(f'pilot {year} {format_seconds(window[0])}-'
          f'{format_seconds(window[1])}: reported {reported}, '
          f'rows {len(runners)}, unique bibs {len(pilot)}')

    return pilot


if __name__ == '__main__':
    os.makedirs(SCRAPE_DIR, exist_ok=True)
    nyc_session = requests.Session()
    nyc_session.headers.update(HEADERS)

    if sys.argv[1:] == ['pilot']:
        scrape_pilot(nyc_session).to_csv(PILOT_FILE, index=False)
    else:
        years = [int(y) for y in sys.argv[1:]] or list(EVENT_CODES)
        checks = []
        for target in years:
            _, check = scrape_year(nyc_session, target)
            print(check, flush=True)
            checks.append(check)
        sbf.update_check(SCRAPE_DIR, checks)
