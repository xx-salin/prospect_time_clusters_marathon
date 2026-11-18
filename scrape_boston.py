'''
Full scrape of runner country from the Boston Athletic Association's
results archive, for the Boston years where the Allen, Dechow, Pope and Wu
(2017) data has runner age (needed for matching).

Each year is scraped in gun-time windows. A window is saved only once the
number of runners collected equals the count the archive reports, so an
interrupted run can be restarted and will skip finished windows. Requests
go one at a time, spaced out. Names and cities are not stored.

The archive's "Country" is country of RESIDENCE, not citizenship.

Sam Salin (svsalin, xx-salin)
'''

import os
import re
import sys
import time
import requests
import pandas as pd
import scrape_boston_pilot as sb

TARGET_YEARS = [2004, 2005, 2006, 2007, 2013]

SEARCH_URL = sb.ARCHIVE_URL + '?mode=results&RequestTimeout=600'
SORT_BY_TIME = 'ByTime'
SORT_BY_NAME = 'ByName'
MAX_TRIES = 4
RETRY_WAIT = 30       # seconds, doubled after each failed try

SCRAPE_DIR = os.path.join(sb.SCRIPT_DIR, 'scraped_data', 'boston')
RAW_DIR = os.path.join(SCRAPE_DIR, 'windows')


def make_windows():
    '''
    Purpose: gun-time windows covering every finisher: one window for
      times under 2:30, 10-minute windows from 2:30 to 6:59:59, and one
      window from 7:00 to 9:59:59.

    Inputs: none

    Returns: (list of tuple) ((h, m, s), (h, m, s)) bounds, inclusive
    '''

    windows = [((1, 0, 0), (2, 29, 59))]
    for start in range(150, 420, 10):
        end = start + 9
        windows.append(((start // 60, start % 60, 0),
                        (end // 60, end % 60, 59)))
    windows.append(((7, 0, 0), (9, 59, 59)))

    return windows


def post_with_retry(session, url, **kwargs):
    '''
    Purpose: send one POST, waiting and retrying on network or server
      errors

    Inputs:
        session (requests.Session)
        url (str)
        kwargs: passed to session.post

    Returns: (requests.Response) the successful response
    '''

    wait = RETRY_WAIT
    for attempt in range(1, MAX_TRIES + 1):
        try:
            response = session.post(url, timeout=sb.TIMEOUT, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as err:
            if attempt == MAX_TRIES:
                raise
            print(f'  request failed ({err}); retry in {wait}s', flush=True)
            time.sleep(wait)
            wait *= 2

    return None


# Task 1
def search_window(session, year, low, high, sort_order):
    '''
    Purpose: run the archive's search for one window and return the
      reported count with the first page of runners.

    Inputs:
        session (requests.Session)
        year (int): race year
        low, high (tuple of int): (hours, minutes, seconds) bounds;
          the search form only takes hours and minutes, so low seconds
          must be 0 and high seconds must be 59
        sort_order (str): SORT_BY_TIME or SORT_BY_NAME

    Returns: (int) reported number of runners, (list of dict) first page,
      (bool) whether there is a next page
    '''

    form = {'SortOrder': sort_order, 'RaceYearLowID': year,
            'RaceYearHighID': year, 'LastName': '', 'FirstName': '',
            'City': '', 'StateID': 0, 'Zip': '', 'CountryOfResidenceID': 0,
            'TimeLowHr': low[0], 'TimeLowMin': f'{low[1]:02d}',
            'TimeHighHr': high[0], 'TimeHighMin': f'{high[1]:02d}',
            'AgeLowID': 0, 'AgeHighID': 0, 'GenderID': 0, 'BibNumber': ''}
    response = post_with_retry(session, SEARCH_URL, data=form)
    time.sleep(sb.DELAY)

    found = re.search(r'returned\s+([\d,]+)\s+result', response.text)
    reported = int(found.group(1).replace(',', '')) if found else 0
    runners, has_next = sb.parse_results(response.text)

    return reported, runners, has_next


# Task 2
def scrape_window_full(session, year, low, high, sort_order=SORT_BY_TIME):
    '''
    Purpose: collect every runner in one window: the search page, then
      each following page of 25.

    Inputs:
        session (requests.Session)
        year (int), low, high (tuple of int): see search_window
        sort_order (str): SORT_BY_TIME or SORT_BY_NAME

    Returns: (int) reported number of runners, (list of dict) runners
    '''

    reported, runners, has_next = search_window(session, year, low, high,
                                                sort_order)
    params = sb.build_query(year, low, high)
    params['VarSortOrder'] = sort_order
    start = sb.PAGE_SIZE + 1
    while has_next:
        response = post_with_retry(session, sb.ARCHIVE_URL, params=params,
                                   data={'start': start})
        time.sleep(sb.DELAY)
        page, has_next = sb.parse_results(response.text)
        if not page:
            break
        runners.extend(page)
        start += sb.PAGE_SIZE

    return reported, runners


# Task 3
def scrape_year(session, year, windows=None, raw_dir=RAW_DIR):
    '''
    Purpose: scrape every window for one year, skipping windows already
      saved, then combine them into one file per year.

    Inputs:
        session (requests.Session)
        year (int): race year
        windows (list of tuple): from make_windows
        raw_dir (str): folder for finished windows

    Returns: (dataframe) one row per bib, and (dict) reported and
      collected counts for the year
    '''

    if windows is None:
        windows = make_windows()
    os.makedirs(raw_dir, exist_ok=True)

    reported_total = 0
    frames = []
    for low, high in windows:
        tag = f'{year}_{low[0]}{low[1]:02d}'
        path = os.path.join(raw_dir, f'{tag}.csv')
        count_path = path.replace('.csv', '.count')

        if os.path.exists(path) and os.path.exists(count_path):
            with open(count_path) as f:
                reported = int(f.read())
            reported_total += reported
            if reported > 0:
                frames.append(pd.read_csv(path, dtype={sb.BIB: str}))
            continue

        reported, runners = scrape_window_full(session, year, low, high)
        window_df = pd.DataFrame(runners)
        if reported and window_df[sb.BIB].nunique() < reported:
            _, extra = scrape_window_full(session, year, low, high,
                                          SORT_BY_NAME)
            window_df = pd.concat([window_df, pd.DataFrame(extra)])
        if not window_df.empty:
            window_df = window_df.drop_duplicates(subset=[sb.BIB])

        collected = len(window_df)
        print(f'{tag}: reported {reported}, collected {collected}',
              flush=True)
        reported_total += reported
        if reported and collected == 0:
            continue
        window_df.to_csv(path, index=False)
        with open(count_path, 'w') as f:
            f.write(str(reported))
        frames.append(window_df)

    year_df = pd.concat(frames).drop_duplicates(subset=[sb.YEAR, sb.BIB])
    year_df[sb.OFFICIAL_SEC] = year_df[sb.OFFICIAL_TIME].map(
        sb.time_to_seconds)
    year_df[sb.NET_SEC] = year_df[sb.NET_TIME].map(sb.time_to_seconds)
    year_df.to_csv(os.path.join(SCRAPE_DIR, f'boston_{year}.csv'),
                   index=False)

    return year_df, {'year': year, 'reported': reported_total,
                     'collected': len(year_df)}


if __name__ == '__main__':
    years = [int(y) for y in sys.argv[1:]] or TARGET_YEARS
    boston_session = requests.Session()
    boston_session.headers['User-Agent'] = sb.USER_AGENT

    checks = []
    for target in years:
        print(f'=== {target}', flush=True)
        _, check = scrape_year(boston_session, target)
        print(check, flush=True)
        checks.append(check)

    pd.DataFrame(checks).to_csv(os.path.join(SCRAPE_DIR, 'scrape_check.csv'),
                                index=False)
    print('done', flush=True)
