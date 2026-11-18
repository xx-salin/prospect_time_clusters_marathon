'''
Match the NYC 2013 pilot scrape (net time 3:30:00 to 4:29:59) to the study
data and report how well it worked, for both citizenship (nationality) and
country of residence. Also checks whether the study's chiptime is NYRR's
net time or gun time.

Sam Salin (svsalin, xx-salin)
'''

import os
import pandas as pd
import match_nationality as mn
import scrape_nyc as sn

MATCHED_FILE = os.path.join(sn.SCRAPE_DIR, 'nyc_2013_pilot_matched.csv')
SUMMARY_FILE = os.path.join(mn.SCRIPT_DIR, 'output',
                            'nyc_2013_pilot_match_summary.csv')


def load_pilot(time_col):
    '''
    Purpose: read the pilot scrape and set the matching keys

    Inputs:
        time_col (str colname): sn.NET_SEC or sn.GUN_SEC

    Returns: (dataframe) scraped runners with TIME_SEC and AGE as integers
    '''

    scraped = pd.read_csv(sn.PILOT_FILE, dtype={sn.BIB: str})
    scraped[mn.TIME_SEC] = scraped[time_col].astype('Int64')
    scraped[mn.AGE] = scraped[sn.AGE].astype('Int64')

    return scraped


if __name__ == '__main__':
    study = mn.load_study_race(mn.STUDY_FILE, 'New York City Marathon',
                               sn.PILOT_YEAR)
    low, high = sn.PILOT_WINDOW
    in_window = study[mn.TIME_SEC].between(low, high)
    print(f'Study rows, NYC 2013: {len(study)}; '
          f'in pilot window: {in_window.sum()}')

    summaries = {}
    for time_col in [sn.NET_SEC, sn.GUN_SEC]:
        scraped = load_pilot(time_col)
        for country_col in [sn.NATIONALITY, sn.COUNTRY_RES]:
            summary = mn.summarize_matches(study, scraped, country_col)
            summaries[(time_col, country_col)] = summary['percent']
            print(f'{time_col} / {country_col}: '
                  f'{summary.loc[mn.ASSIGNED, "percent"].sum():.1f}% '
                  'of scraped runners resolved')

    table = pd.DataFrame(summaries).T
    table.index.names = ['time_source', 'country_col']
    os.makedirs(os.path.dirname(SUMMARY_FILE), exist_ok=True)
    table.to_csv(SUMMARY_FILE)
    print('\nScraped runners by match status (percent)')
    print(table.to_string())

    scraped = load_pilot(sn.NET_SEC)
    print(f'\nScraped runners: {len(scraped)}; nationality differs from '
          f'residence for '
          f'{(scraped[sn.NATIONALITY] != scraped[sn.COUNTRY_RES]).mean():.1%}')

    by_nat = mn.attach_country(study[in_window], scraped, sn.NATIONALITY)
    by_res = mn.attach_country(study[in_window], scraped, sn.COUNTRY_RES)
    matched = by_nat.merge(by_res[[mn.STUDY_ROW, sn.COUNTRY_RES]],
                           on=mn.STUDY_ROW, how='outer')
    matched.to_csv(MATCHED_FILE, index=False)

    assigned = matched[sn.NATIONALITY].notna()
    print(f'Study rows in window given a nationality: {assigned.sum()} of '
          f'{in_window.sum()} ({assigned.sum() / in_window.sum():.1%})')
    print(matched.loc[assigned, sn.NATIONALITY].value_counts()
          .head(12).to_string())
