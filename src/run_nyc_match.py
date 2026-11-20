'''
Match the full NYC Marathon scrape (every year the study has runner age) to
the Allen, Dechow, Pope and Wu (2017) data. Each study row gets the
runner's citizenship (nationality) and country of residence where the
match key resolves it.

Run scrape_nyc.py first.

Sam Salin (svsalin, xx-salin)
'''

import os
import pandas as pd
import match_nationality as mn
import scrape_nyc as sn

NYC = 'New York City Marathon'
TIME_SOURCE = 'time_source'
KEYS_USED = 'keys_used'
NAT_STATUS = 'nationality_status'
RES_STATUS = 'residence_status'

# NYRR rounds some times one second higher than the study's source (about
# 8% of runners in 2011), so leftover rows get a second pass at +-1 second
NEAR_SHIFTS = [-1, 1]
# Years where NYRR lists gun time only (net equals gun for nearly everyone);
# the study has chip times there, so exact matching is not possible.
# These years (1999-2005) are dropped from the NYC analysis.
GUN_ONLY_SHARE = 0.99
DROPPED_LABEL = 'dropped: NYRR has gun time only'

MATCHED_FILE = os.path.join(sn.SCRAPE_DIR, 'nyc_matched_all_years.csv')
# Fractional assignment: one row per (study row, country) with a weight
FRACTIONAL_FILES = {
    sn.NATIONALITY: os.path.join(sn.SCRAPE_DIR, 'nyc_fractional_nationality.csv'),
    sn.COUNTRY_RES: os.path.join(sn.SCRAPE_DIR, 'nyc_fractional_residence.csv')}
FRACTIONAL_COLS = [mn.STUDY_ROW, mn.YEAR, mn.WEIGHT, mn.MATCH_STATUS]
SUMMARY_FILE = os.path.join(mn.ROOT_DIR, 'output', 'nyc',
                            'nyc_match_summary.csv')


def load_scraped_year(year, time_col):
    '''
    Purpose: read one scraped year and set the matching keys

    Inputs:
        year (int): race year
        time_col (str colname): sn.NET_SEC or sn.GUN_SEC

    Returns: (dataframe) scraped runners with TIME_SEC and AGE as
      integers, or None if the year has not been scraped
    '''

    path = os.path.join(sn.SCRAPE_DIR, f'nyc_{year}.csv')
    if not os.path.exists(path):
        return None

    scraped = pd.read_csv(path, dtype={sn.BIB: str})
    scraped[mn.TIME_SEC] = scraped[time_col].astype('Int64')
    scraped[mn.AGE] = scraped[sn.AGE].astype('Int64')

    return scraped


def match_keys(study):
    '''
    Purpose: choose the match keys; years where the study has no gender
      (2010) are matched on time and age only

    Inputs:
        study (dataframe): one year's study rows

    Returns: (list of str) key columns
    '''

    if study[mn.GENDER].isna().all():
        return [mn.TIME_SEC, mn.AGE]

    return mn.MATCH_KEYS


def has_chip_time(year):
    '''
    Purpose: check whether NYRR lists a net (chip) time separate from the
      gun time for a year

    Inputs:
        year (int): race year

    Returns: (bool) False if net equals gun for nearly every runner
    '''

    scraped = load_scraped_year(year, sn.NET_SEC)
    same = (scraped[sn.NET_SEC] == scraped[sn.GUN_SEC]).mean()

    return same < GUN_ONLY_SHARE


def near_match(study, scraped, country_col, keys, shifts=NEAR_SHIFTS,
               attach=mn.attach_country):
    '''
    Purpose: second pass for rows the exact match left out: study rows
      whose key is not in the scrape, and scraped runners whose key is not
      in the study. Shift the scraped times by each amount in turn; a
      runner or study row used by one shift is not used again.

    Inputs:
        study (dataframe), scraped (dataframe), country_col (str),
        keys (list of str): see match_nationality.attach_country
        shifts (list of int): seconds added to the scraped times
        attach (function): mn.attach_country, or mn.attach_country_shares
          for fractional assignment

    Returns: (dataframe) study rows matched in this pass, with
      MATCH_STATUS labelled by the shift (e.g. 'unique_-1s')
    '''

    key_info = mn.classify_keys(study, scraped, country_col, keys)
    found = study.merge(key_info[keys], on=keys, how='left', indicator=True)
    left_study = study[(found['_merge'] == 'left_only').to_numpy()]
    unmatched_keys = key_info.loc[key_info[mn.MATCH_STATUS] == mn.NO_MATCH,
                                  keys]
    left_scraped = scraped.merge(unmatched_keys, on=keys)

    frames = []
    for shift in shifts:
        shifted = left_scraped.assign(
            **{mn.TIME_SEC: left_scraped[mn.TIME_SEC] + shift})
        matched = attach(left_study, shifted, country_col, keys)
        matched[mn.MATCH_STATUS] = matched[mn.MATCH_STATUS] + f'_{shift:+d}s'
        frames.append(matched)

        used = shifted.merge(matched[keys].drop_duplicates(), on=keys,
                             how='left', indicator=True)
        left_scraped = left_scraped[(used['_merge'] == 'left_only')
                                    .to_numpy()]
        left_study = left_study[~left_study[mn.STUDY_ROW].isin(
            matched[mn.STUDY_ROW])]

    return pd.concat(frames, ignore_index=True)


def match_country(study, scraped, country_col, keys):
    '''
    Purpose: exact match, then the +-1 second pass on what is left

    Inputs:
        study (dataframe), scraped (dataframe), country_col (str),
        keys (list of str): see match_nationality.attach_country

    Returns: (dataframe) matched study rows with country_col and
      MATCH_STATUS
    '''

    exact = mn.attach_country(study, scraped, country_col, keys)
    near = near_match(study, scraped, country_col, keys)

    return pd.concat([exact, near], ignore_index=True)


def match_country_shares(study, scraped, country_col, keys):
    '''
    Purpose: fractional assignment (mn.attach_country_shares), exact match
      then the +-1 second pass

    Inputs:
        study (dataframe), scraped (dataframe), country_col (str),
        keys (list of str): see match_nationality.attach_country

    Returns: (dataframe) one row per (study row, country) with WEIGHT
    '''

    exact = mn.attach_country_shares(study, scraped, country_col, keys)
    near = near_match(study, scraped, country_col, keys,
                      attach=mn.attach_country_shares)

    return pd.concat([exact, near], ignore_index=True)


def match_year(study, year):
    '''
    Purpose: match one year on both nationality and residence, using
      whichever archive time (net or gun) resolves more runners

    Inputs:
        study (dataframe): that year's study rows
        year (int): race year

    Returns: (dataframe) matched study rows with nationality, residence
      and their match statuses, and (dataframe) one-row summary
    '''

    keys = match_keys(study)
    best = None
    for time_col in [sn.NET_SEC, sn.GUN_SEC]:
        scraped = load_scraped_year(year, time_col)
        summary = mn.summarize_matches(study, scraped, sn.NATIONALITY, keys)
        resolved = summary.loc[mn.ASSIGNED, 'runners'].sum()
        if best is None or resolved > best[0]:
            best = (resolved, time_col, scraped, summary)

    _, time_col, scraped, summary = best
    by_nat = match_country(study, scraped, sn.NATIONALITY, keys)
    by_res = match_country(study, scraped, sn.COUNTRY_RES, keys)
    by_nat = by_nat.rename(columns={mn.MATCH_STATUS: NAT_STATUS})
    by_res = by_res[[mn.STUDY_ROW, sn.COUNTRY_RES, mn.MATCH_STATUS]].rename(
        columns={mn.MATCH_STATUS: RES_STATUS})
    matched = by_nat.merge(by_res, on=mn.STUDY_ROW, how='outer')

    summary = summary['percent'].rename(year).to_frame().T
    summary.insert(0, 'scraped', len(scraped))
    summary.insert(0, 'study_rows', len(study))
    summary.insert(0, KEYS_USED, '+'.join(keys))
    summary.insert(0, TIME_SOURCE, time_col)
    near = by_nat[NAT_STATUS].str.endswith('s') & by_nat[sn.NATIONALITY].notna()
    summary['rows_with_nationality'] = matched[sn.NATIONALITY].notna().sum()
    summary['of_which_pm1s'] = near.sum()
    summary['rows_with_residence'] = matched[sn.COUNTRY_RES].notna().sum()
    summary['pct_study_rows_nationality'] = round(
        100 * summary['rows_with_nationality'] / len(study), 1)

    fractional = {col: match_country_shares(study, scraped, col, keys)
                  [FRACTIONAL_COLS[:1] + [col] + FRACTIONAL_COLS[1:]]
                  for col in FRACTIONAL_FILES}
    covered = fractional[sn.NATIONALITY][mn.STUDY_ROW].nunique()
    summary['pct_study_rows_fractional'] = round(100 * covered / len(study),
                                                 1)

    return matched, summary, fractional


if __name__ == '__main__':
    study_all = mn.read_study_file(mn.STUDY_FILE)
    years = [y for y in sn.EVENT_CODES
             if load_scraped_year(y, sn.NET_SEC) is not None]
    races = mn.split_study_years(study_all, NYC, years)

    matched_years, summaries, fractional_years = [], [], {}
    for year, race in races.items():
        if not has_chip_time(year):
            summary = pd.DataFrame({TIME_SOURCE: [DROPPED_LABEL],
                                    'study_rows': [len(race)]}, index=[year])
            summaries.append(summary)
            print(f'{year}: {DROPPED_LABEL}', flush=True)
            continue
        matched, summary, fractional = match_year(race, year)
        matched_years.append(matched)
        summaries.append(summary)
        for col, frac in fractional.items():
            fractional_years.setdefault(col, []).append(frac)
        print(summary.to_string(), flush=True)

    os.makedirs(os.path.dirname(SUMMARY_FILE), exist_ok=True)
    pd.concat(matched_years).to_csv(MATCHED_FILE, index=False)
    for col, frames in fractional_years.items():
        pd.concat(frames).to_csv(FRACTIONAL_FILES[col], index=False)
    pd.concat(summaries).to_csv(SUMMARY_FILE)
