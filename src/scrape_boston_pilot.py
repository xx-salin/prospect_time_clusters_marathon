'''
Pilot scrape of runner country from the Boston Athletic Association's
results archive (2001-2019), to test matching against the Allen, Dechow,
Pope and Wu (2017) data.

Source: https://registration.baa.org/cfm_Archive/iframe_ArchiveSearch.cfm
The site has no robots.txt and its legal page has no rule against automated
access. Requests are spaced out and sent one at a time. Names and cities
are not stored: the match only needs bib, age, gender, times and country.

The archive's "Country" is country of RESIDENCE, not citizenship.

Sam Salin (svsalin, xx-salin)
'''

import os
import re
import time
import html
import requests
import pandas as pd

# Defined constants for column names
YEAR = 'year'
BIB = 'bib'
AGE = 'age'
GENDER = 'gender'
COUNTRY_RES = 'country_residence'
OFFICIAL_TIME = 'official_time'
NET_TIME = 'net_time'
OFFICIAL_SEC = 'official_sec'
NET_SEC = 'net_sec'

ARCHIVE_URL = ('https://registration.baa.org/cfm_Archive/'
               'iframe_ArchiveSearch.cfm')
USER_AGENT = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
              'academic research pilot')
PAGE_SIZE = 25        # the archive returns 25 runners per request
DELAY = 1.5           # seconds between requests
TIMEOUT = 60

# Repository root (this file lives in src/)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE = os.path.join(ROOT_DIR, 'scraped_data', 'boston', 'pilot',
                           'boston_2013_pilot.csv')

PILOT_YEAR = 2013
# Gun-time windows (h, m, s) to sample: 10 minutes around 3:00, 3:30, 4:00
PILOT_WINDOWS = [((2, 55, 0), (3, 4, 59)),
                 ((3, 25, 0), (3, 34, 59)),
                 ((3, 55, 0), (4, 4, 59))]


def time_to_seconds(text):
    '''
    Purpose: convert an H:MM:SS string to seconds

    Inputs:
        text (str): e.g. '3:00:01'

    Returns: (int) seconds, or None if the text is not a time
    '''

    if not isinstance(text, str):   # blank times are read in as NaN
        return None
    match = re.fullmatch(r'\s*(\d+):(\d{2}):(\d{2})\s*', text)
    if match is None:
        return None
    hours, minutes, seconds = (int(g) for g in match.groups())

    return 3600 * hours + 60 * minutes + seconds


# Task 1
def build_query(year, low, high):
    '''
    Purpose: build the archive's query parameters for one year and one
      official (gun) time window, sorted by finish time.

    Inputs:
        year (int): race year
        low, high (tuple of int): (hours, minutes, seconds) bounds

    Returns: (dict) query string parameters
    '''

    return {'mode': 'results', 'criteria': '', 'StoredProcParamsOn': 'yes',
            'VarRaceYearLowID': year, 'VarRaceYearHighID': year,
            'VarAgeLowID': 0, 'VarAgeHighID': 0, 'VarGenderID': 0,
            'VarBibNumber': '', 'VarLastName': '', 'VarFirstName': '',
            'VarStateID': 0, 'VarCountryOfResidenceID': 0, 'VarCity': '',
            'VarZip': '',
            'VarTimeLowHr': low[0], 'VarTimeLowMin': f'{low[1]:02d}',
            'VarTimeLowSec': f'{low[2]:02d}',
            'VarTimeHighHr': high[0], 'VarTimeHighMin': f'{high[1]:02d}',
            'VarTimeHighSec': f'{high[2]:02d}',
            'VarSortOrder': 'ByTime', 'VarAddInactiveYears': 0,
            'records': PAGE_SIZE, 'headerexists': 'Yes',
            'queryname': 'SearchResults',
            'tablefields': ('RaceYear,FullBibNumber,FormattedSortName,'
                            'AgeOnRaceDay,GenderCode,City,StateAbbrev,'
                            'CountryOfResAbbrev,ReportingSegment')}


# Task 2
def parse_results(page_html):
    '''
    Purpose: pull one record per runner out of an archive results page

    Inputs:
        page_html (str): html of one results page

    Returns: (list of dict) runners on the page, and (bool) whether the
      page has a "Next 25 Records" button
    '''

    def cells(fragment):
        raw = re.findall(r'<td[^>]*>(.*?)</td>', fragment, re.S)
        return [html.unescape(re.sub(r'<[^>]+>', '', c)).strip()
                for c in raw]

    runners = []
    blocks = page_html.split('class="tr_header"')[1:]
    for block in blocks:
        header, _, detail = block.partition('table_infogrid')
        top = cells(header)
        bottom = cells(detail)
        if len(top) < 8 or len(bottom) < 5:
            continue
        runners.append({YEAR: int(top[0]),
                        BIB: top[1],
                        AGE: int(top[3]) if top[3].isdigit() else None,
                        GENDER: top[4],
                        COUNTRY_RES: top[7],
                        OFFICIAL_TIME: bottom[3],
                        NET_TIME: bottom[4]})

    has_next = 'name="next"' in page_html

    return runners, has_next


# Task 3
def scrape_window(session, year, low, high, delay=DELAY):
    '''
    Purpose: page through every runner in one gun-time window

    Inputs:
        session (requests.Session)
        year (int): race year
        low, high (tuple of int): (hours, minutes, seconds) bounds
        delay (float): seconds to wait between requests

    Returns: (list of dict) runners in the window
    '''

    params = build_query(year, low, high)
    runners = []
    start = 1
    while True:
        response = session.post(ARCHIVE_URL, params=params,
                                data={'start': start}, timeout=TIMEOUT)
        response.raise_for_status()
        page, has_next = parse_results(response.text)
        runners.extend(page)
        time.sleep(delay)
        if not has_next or not page:
            break
        start += PAGE_SIZE

    return runners


# Task 4
def scrape_pilot(year=PILOT_YEAR, windows=PILOT_WINDOWS,
                 output_file=OUTPUT_FILE):
    '''
    Purpose: scrape the pilot windows and save them as a csv

    Inputs:
        year (int): race year
        windows (list of tuple): gun-time windows to scrape
        output_file (str): where to save the csv

    Returns: (dataframe) scraped runners, one row per bib
    '''

    session = requests.Session()
    session.headers['User-Agent'] = USER_AGENT

    runners = []
    for low, high in windows:
        found = scrape_window(session, year, low, high)
        print(f'{year} {low}-{high}: {len(found)} runners')
        runners.extend(found)

    df = pd.DataFrame(runners).drop_duplicates(subset=[YEAR, BIB])
    df[OFFICIAL_SEC] = df[OFFICIAL_TIME].map(time_to_seconds)
    df[NET_SEC] = df[NET_TIME].map(time_to_seconds)

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    df.to_csv(output_file, index=False)

    return df


if __name__ == '__main__':
    scraped = scrape_pilot()
    print(f'Saved {len(scraped)} runners to {OUTPUT_FILE}')
    print(scraped[COUNTRY_RES].value_counts().head(10).to_string())
