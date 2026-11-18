'''
Match the full Boston scrape (every year the study has runner age) to the
Allen, Dechow, Pope and Wu (2017) data, then run the clustering estimates
by runner country of residence as a first use of the template.

Sam Salin (svsalin, xx-salin)
'''

import os
import pandas as pd
import match_nationality as mn
import scrape_boston as sbf
import scrape_boston_pilot as sb
import country_clusters as cc

RESIDENCE_GROUP = 'residence_group'
TIME_SOURCE = 'time_source'

MATCHED_FILE = os.path.join(sbf.SCRAPE_DIR, 'boston_matched_all_years.csv')
SUMMARY_FILE = os.path.join(mn.SCRIPT_DIR, 'output',
                            'boston_match_summary.csv')
MINUTE_FILE = os.path.join(mn.SCRIPT_DIR, 'output',
                           'boston_minute_before_after_by_residence.csv')
EXCESS_FILE = os.path.join(mn.SCRIPT_DIR, 'output',
                           'boston_excess_mass_by_residence.csv')


def load_scraped_year(year, time_col):
    '''
    Purpose: read one scraped year and set the matching keys

    Inputs:
        year (int): race year
        time_col (str colname): sb.NET_SEC or sb.OFFICIAL_SEC

    Returns: (dataframe) scraped runners with TIME_SEC and AGE as integers
    '''

    scraped = pd.read_csv(os.path.join(sbf.SCRAPE_DIR, f'boston_{year}.csv'),
                          dtype={sb.BIB: str})
    scraped[mn.TIME_SEC] = scraped[time_col].astype('Int64')
    scraped[mn.AGE] = scraped[sb.AGE].astype('Int64')

    return scraped


def match_year(study, year):
    '''
    Purpose: match one year, using whichever archive time (net or gun)
      gives more resolved runners

    Inputs:
        study (dataframe): that year's study rows
        year (int): race year

    Returns: (dataframe) matched study rows, (dataframe) match summary
    '''

    best = None
    for time_col in [sb.NET_SEC, sb.OFFICIAL_SEC]:
        scraped = load_scraped_year(year, time_col)
        summary = mn.summarize_matches(study, scraped, sb.COUNTRY_RES)
        resolved = summary.loc[mn.ASSIGNED, 'runners'].sum()
        if best is None or resolved > best[0]:
            best = (resolved, time_col, scraped, summary)

    _, time_col, scraped, summary = best
    matched = mn.attach_country(study, scraped, sb.COUNTRY_RES)
    summary = summary['percent'].rename(year).to_frame().T
    summary.insert(0, 'scraped', len(scraped))
    summary.insert(0, 'study_rows', len(study))
    summary.insert(0, TIME_SOURCE, time_col)
    summary['study_rows_assigned'] = matched[sb.COUNTRY_RES].notna().sum()

    return matched, summary


def residence_group(code):
    '''
    Purpose: collapse country codes into groups big enough to estimate

    Inputs:
        code (str): three-letter country of residence

    Returns: (str) 'USA', 'Canada' or 'Other countries'
    '''

    if code == 'USA':
        return 'USA'
    if code == 'CAN':
        return 'Canada'

    return 'Other countries'


if __name__ == '__main__':
    study_all = mn.read_study_file(mn.STUDY_FILE)
    races = mn.split_study_years(study_all, 'Boston Marathon',
                                 sbf.TARGET_YEARS)

    matched_years, summaries = [], []
    for year, race in races.items():
        matched, summary = match_year(race, year)
        matched_years.append(matched)
        summaries.append(summary)

    matched_all = pd.concat(matched_years)
    summary_all = pd.concat(summaries)
    os.makedirs(os.path.dirname(SUMMARY_FILE), exist_ok=True)
    matched_all.to_csv(MATCHED_FILE, index=False)
    summary_all.to_csv(SUMMARY_FILE)
    pd.set_option('display.width', 200)
    print('Match results by year (percent of scraped runners)')
    print(summary_all.to_string())

    # Merge country onto the full processed dataset by original row
    marathons = cc.read_and_process_marathons(cc.DATA_FILE)
    assigned = matched_all.dropna(subset=[sb.COUNTRY_RES])
    marathons.loc[assigned[mn.STUDY_ROW], sb.COUNTRY_RES] = (
        assigned[sb.COUNTRY_RES].to_numpy())
    boston = marathons[marathons[sb.COUNTRY_RES].notna()].copy()
    boston[RESIDENCE_GROUP] = boston[sb.COUNTRY_RES].map(residence_group)

    print('\nBoston finishers with a country, by group')
    print(cc.get_group_summary(boston, RESIDENCE_GROUP).round(1).to_string())

    minute = cc.get_minute_before_after(boston, RESIDENCE_GROUP).round(1)
    minute.to_csv(MINUTE_FILE)
    print('\nPercent more finishers in the minute before vs after')
    print(minute.to_string())

    excess = cc.make_excess_mass_table(boston, RESIDENCE_GROUP,
                                       min_finishers=1000)
    excess.to_csv(EXCESS_FILE)
    print('\nExcess mass by country of residence (Boston only)')
    print(excess.to_string())
