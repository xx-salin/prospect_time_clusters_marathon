'''
Match the Boston 2013 pilot scrape to the study data and report how well
it worked.

Sam Salin (svsalin, xx-salin)
'''

import os
import pandas as pd
import match_nationality as mn
import scrape_boston_pilot as sb

MATCHED_FILE = os.path.join(mn.SCRIPT_DIR, 'scraped_data',
                            'boston_2013_pilot_matched.csv')
SUMMARY_FILE = os.path.join(mn.SCRIPT_DIR, 'output',
                            'boston_2013_pilot_match_summary.csv')

if __name__ == '__main__':
    study = mn.load_study_race(mn.STUDY_FILE, 'Boston Marathon', 2013)

    scraped = pd.read_csv(sb.OUTPUT_FILE)
    scraped[mn.TIME_SEC] = scraped[sb.NET_SEC].astype('Int64')
    scraped[mn.AGE] = scraped[sb.AGE].astype('Int64')

    summary = mn.summarize_matches(study, scraped, sb.COUNTRY_RES)
    matched = mn.attach_country(study, scraped, sb.COUNTRY_RES)

    os.makedirs(os.path.dirname(SUMMARY_FILE), exist_ok=True)
    summary.to_csv(SUMMARY_FILE)
    matched.to_csv(MATCHED_FILE, index=False)

    assigned = matched[sb.COUNTRY_RES].notna()
    print(f'Study rows, Boston 2013: {len(study)}')
    print(f'Scraped runners: {len(scraped)}')
    print('\nScraped runners by match status')
    print(summary.to_string())
    print(f'\nStudy rows given a country: {assigned.sum()} of '
          f'{len(matched)} matched rows')
    print(matched.loc[assigned, sb.COUNTRY_RES].value_counts()
          .head(8).to_string())
