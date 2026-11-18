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

MATCHED_FILE = os.path.join(sn.SCRAPE_DIR, 'nyc_matched_all_years.csv')
SUMMARY_FILE = os.path.join(mn.SCRIPT_DIR, 'output', 'nyc_match_summary.csv')


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
    by_nat = mn.attach_country(study, scraped, sn.NATIONALITY, keys)
    by_res = mn.attach_country(study, scraped, sn.COUNTRY_RES, keys)
    by_nat = by_nat.rename(columns={mn.MATCH_STATUS: NAT_STATUS})
    by_res = by_res[[mn.STUDY_ROW, sn.COUNTRY_RES, mn.MATCH_STATUS]].rename(
        columns={mn.MATCH_STATUS: RES_STATUS})
    matched = by_nat.merge(by_res, on=mn.STUDY_ROW, how='outer')

    summary = summary['percent'].rename(year).to_frame().T
    summary.insert(0, 'scraped', len(scraped))
    summary.insert(0, 'study_rows', len(study))
    summary.insert(0, KEYS_USED, '+'.join(keys))
    summary.insert(0, TIME_SOURCE, time_col)
    summary['rows_with_nationality'] = matched[sn.NATIONALITY].notna().sum()
    summary['rows_with_residence'] = matched[sn.COUNTRY_RES].notna().sum()

    return matched, summary


if __name__ == '__main__':
    study_all = mn.read_study_file(mn.STUDY_FILE)
    years = [y for y in sn.EVENT_CODES
             if load_scraped_year(y, sn.NET_SEC) is not None]
    races = mn.split_study_years(study_all, NYC, years)

    matched_years, summaries = [], []
    for year, race in races.items():
        matched, summary = match_year(race, year)
        matched_years.append(matched)
        summaries.append(summary)
        print(summary.to_string(header=not summaries[:-1]), flush=True)

    os.makedirs(os.path.dirname(SUMMARY_FILE), exist_ok=True)
    pd.concat(matched_years).to_csv(MATCHED_FILE, index=False)
    pd.concat(summaries).to_csv(SUMMARY_FILE)
