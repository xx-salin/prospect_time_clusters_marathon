'''
Attach scraped runner country to the Allen, Dechow, Pope and Wu (2017)
finishing-time data.

The released data has no names or bibs, so runners are matched on finishing
time to the second, age and gender. When several runners share a key, they
can't be told apart, but if all of them have the same country the country
can still be assigned. The clustering analysis only needs time and country,
not who each runner is.

Sam Salin (svsalin, xx-salin)
'''

import os
import pandas as pd

# Defined constants for column names
MARATHON = 'marathon'
YEAR = 'year'
AGE = 'age'
GENDER = 'gender'
CHIPTIME = 'chiptime'
TIME_SEC = 'time_sec'
STUDY_ROW = 'study_row'
MATCH_STATUS = 'match_status'
N_STUDY = 'n_study'
N_SCRAPED = 'n_scraped'
N_COUNTRIES = 'n_countries'

WEIGHT = 'weight'

MATCH_KEYS = [TIME_SEC, AGE, GENDER]

# Match statuses, from best to worst
UNIQUE = 'unique'
GROUP_SAME = 'group_same_country'
GROUP_MIXED = 'group_mixed_country'
COUNT_MISMATCH = 'count_mismatch'
NO_MATCH = 'no_match'
STATUS_ORDER = [UNIQUE, GROUP_SAME, GROUP_MIXED, COUNT_MISMATCH, NO_MATCH]
ASSIGNED = [UNIQUE, GROUP_SAME]

# Repository root (this file lives in src/)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUDY_FILE = os.path.join(ROOT_DIR, 'original_data',
                          'mnsc.2015-2417-SM-data-master_marathom',
                          'master_marathon.csv')


# Task 1
def load_study_race(csv_file, marathon, year):
    '''
    Purpose: read one marathon-year from master_marathon.csv and add the
      finishing time in whole seconds.

    Inputs:
        csv_file (string): path to master_marathon.csv
        marathon (str): marathon name as written in the data
        year (int): race year

    Returns: (dataframe) that race's rows, with the original row number
      kept in STUDY_ROW, or None if the file does not exist
    '''

    if not os.path.exists(csv_file):
        return None

    cols = [MARATHON, YEAR, AGE, GENDER, CHIPTIME]
    study = pd.read_csv(csv_file, usecols=cols, encoding='latin-1',
                        low_memory=False)
    study = study[(study[MARATHON] == marathon) & (study[YEAR] == year)]
    study = study.rename_axis(STUDY_ROW).reset_index()
    study[TIME_SEC] = (study[CHIPTIME] * 60).round().astype('Int64')
    study[AGE] = study[AGE].astype('Int64')

    return study


# Task 1b
def split_study_years(study_all, marathon, years):
    '''
    Purpose: same output as load_study_race, for several years, from a
      dataframe already read with read_study_file (so the large file is
      read only once).

    Inputs:
        study_all (dataframe): from read_study_file
        marathon (str): marathon name as written in the data
        years (list of int): race years

    Returns: (dict) {year: dataframe of that race's rows}
    '''

    races = {}
    for year in years:
        race = study_all[(study_all[MARATHON] == marathon) &
                         (study_all[YEAR] == year)].copy()
        race[TIME_SEC] = (race[CHIPTIME] * 60).round().astype('Int64')
        race[AGE] = race[AGE].astype('Int64')
        races[year] = race

    return races


def read_study_file(csv_file):
    '''
    Purpose: read the columns needed for matching from master_marathon.csv,
      keeping each row's position in STUDY_ROW

    Inputs:
        csv_file (string): path to master_marathon.csv

    Returns: (dataframe), or None if the file does not exist
    '''

    if not os.path.exists(csv_file):
        return None

    cols = [MARATHON, YEAR, AGE, GENDER, CHIPTIME]
    study = pd.read_csv(csv_file, usecols=cols, encoding='latin-1',
                        low_memory=False)

    return study.rename_axis(STUDY_ROW).reset_index()


# Task 2
def classify_keys(study, scraped, country_col, keys=MATCH_KEYS):
    '''
    Purpose: compare how many study rows and scraped runners share each
      match key, and how many countries the scraped runners have.

    Inputs:
        study (dataframe): from load_study_race
        scraped (dataframe): must have the key columns and country_col
        country_col (str colname): scraped country column
        keys (list of str): columns to match on

    Returns: (dataframe) one row per key seen in the scraped data, with
      counts, the country if there is only one, and a match status
    '''

    study_counts = study.groupby(keys).size().rename(N_STUDY)
    scraped_groups = scraped.groupby(keys)[country_col]
    key_info = pd.concat([scraped_groups.size().rename(N_SCRAPED),
                          scraped_groups.nunique().rename(N_COUNTRIES),
                          scraped_groups.first().rename(country_col)],
                         axis=1)
    key_info = key_info.join(study_counts, how='left')
    key_info[N_STUDY] = key_info[N_STUDY].fillna(0).astype(int)

    same_count = key_info[N_STUDY] == key_info[N_SCRAPED]
    one_country = key_info[N_COUNTRIES] == 1
    status = pd.Series(COUNT_MISMATCH, index=key_info.index)
    status[same_count & ~one_country] = GROUP_MIXED
    status[same_count & one_country] = GROUP_SAME
    status[same_count & (key_info[N_SCRAPED] == 1)] = UNIQUE
    status[key_info[N_STUDY] == 0] = NO_MATCH
    key_info[MATCH_STATUS] = status

    key_info.loc[~key_info[MATCH_STATUS].isin(ASSIGNED), country_col] = None

    return key_info.reset_index()


# Task 3
def attach_country(study, scraped, country_col, keys=MATCH_KEYS):
    '''
    Purpose: give each study row the scraped country when its key is
      resolved (a unique match, or a group where every runner has the
      same country).

    Inputs:
        study (dataframe): from load_study_race
        scraped (dataframe): must have the key columns and country_col
        country_col (str colname): scraped country column
        keys (list of str): columns to match on

    Returns: (dataframe) study rows whose key appears in the scraped data,
      with country_col (empty when unresolved) and MATCH_STATUS
    '''

    key_info = classify_keys(study, scraped, country_col, keys)
    key_info = key_info[key_info[MATCH_STATUS] != NO_MATCH]

    return study.merge(key_info[keys + [country_col, MATCH_STATUS]],
                       on=keys, how='inner')


# Task 3b
def attach_country_shares(study, scraped, country_col, keys=MATCH_KEYS):
    '''
    Purpose: fractional assignment. Every study row whose key appears in
      the scraped data gets one row per country among the scraped runners
      with that key, weighted by that country's share of them. A key with
      runners from the U.S., the U.S. and France gives each of its study
      rows weight 2/3 for U.S. and 1/3 for France. Because all rows in a
      key have the same finishing time, the weighted counts by country and
      time are exact when the study and scrape counts agree, so nothing is
      dropped for having a mixed key.

    Inputs:
        study (dataframe), scraped (dataframe), country_col (str),
        keys (list of str): see attach_country

    Returns: (dataframe) one row per (study row, country): study columns,
      country_col, WEIGHT (summing to 1 for each study row) and
      MATCH_STATUS
    '''

    key_info = classify_keys(study, scraped, country_col, keys)
    key_info = key_info[key_info[MATCH_STATUS] != NO_MATCH]

    known = scraped.dropna(subset=[country_col])
    shares = (known.groupby(keys + [country_col]).size().rename(WEIGHT)
              .reset_index())
    shares[WEIGHT] = shares[WEIGHT] / shares.groupby(keys)[WEIGHT].transform(
        'sum')
    shares = shares.merge(key_info[keys + [MATCH_STATUS]], on=keys)

    return study.merge(shares, on=keys, how='inner')


# Task 4
def summarize_matches(study, scraped, country_col, keys=MATCH_KEYS):
    '''
    Purpose: share of scraped runners in each match status

    Inputs:
        study (dataframe), scraped (dataframe), country_col (str),
        keys (list of str): see attach_country

    Returns: (dataframe) runner counts and percent by match status
    '''

    key_info = classify_keys(study, scraped, country_col, keys)
    runners = key_info.groupby(MATCH_STATUS)[N_SCRAPED].sum()
    runners = runners.reindex(STATUS_ORDER, fill_value=0)

    summary = pd.DataFrame({'runners': runners,
                            'percent': 100 * runners / runners.sum()})

    return summary.round(1)
