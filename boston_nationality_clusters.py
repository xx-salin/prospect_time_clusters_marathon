'''
Clustering of Boston Marathon finishing times at round-number reference
points, grouped by runner NATIONALITY.

Uses the pipeline in country_clusters.py (Allen, Dechow, Pope and Wu 2017
excess-mass estimate) with the nationality column attached by
run_boston_match.py. Nationality here is the runner's country of residence
from the Boston Athletic Association results archive; Boston does not
publish citizenship.

Also reports how well the matching worked: how many study rows got a
nationality, why the rest were dropped, whether the drops differ by
nationality, and an estimate of how many assigned nationalities are wrong.

Run run_boston_match.py first.

Sam Salin (svsalin, xx-salin)
'''

import os
import pandas as pd
import country_clusters as cc
import match_nationality as mn
import run_boston_match as rb
import scrape_boston as sbf
import scrape_boston_pilot as sb

# Defined constants for column names
YEAR = cc.YEAR
MARATHON = cc.MARATHON
AGE = cc.AGE
GENDER = cc.GENDER
CHIPTIME = cc.CHIPTIME
NATIONALITY = cc.NATIONALITY
NAT_REGION = 'nationality_region'
COUNTRY_RES = sb.COUNTRY_RES
MATCH_STATUS = mn.MATCH_STATUS
STUDY_ROW = mn.STUDY_ROW
TIME_SEC = mn.TIME_SEC
SAMPLE = 'sample'

BOSTON = 'Boston Marathon'
YEARS = sbf.TARGET_YEARS

MATCHED_FILE = rb.MATCHED_FILE
MATCH_SUMMARY_FILE = rb.SUMMARY_FILE
OUTPUT_DIR = cc.OUTPUT_DIR
NATIONALITY_FILE = os.path.join(sbf.SCRAPE_DIR,
                                'boston_study_with_nationality.csv')

# Study rows whose match key never appears in the scrape
NOT_IN_SCRAPE = 'not_in_scrape'
# Scraped runners with a missing age or time, so no match key
MISSING_KEY = 'missing_key'
STUDY_STATUSES = [mn.UNIQUE, mn.GROUP_SAME, mn.GROUP_MIXED,
                  mn.COUNT_MISMATCH, NOT_IN_SCRAPE]

# Region of the runner's nationality, labelled as in Table 3 of the paper
# (there the region is where the race was held)
EUROPE = {'AUT', 'BEL', 'CRO', 'CYP', 'CZE', 'DEN', 'ESP', 'EST', 'FIN',
          'FRA', 'GBR', 'GER', 'GRE', 'HUN', 'IRL', 'ISL', 'ITA', 'LAT',
          'LTU', 'LUX', 'NED', 'NOR', 'POL', 'POR', 'ROM', 'RUS', 'SCG',
          'SER', 'SLO', 'SUI', 'SVK', 'SWE', 'TUR', 'UKR'}

# Boston has far fewer non-US finishers than the full data, so the
# minimum group size is lower than country_clusters.MIN_FINISHERS.
# Estimates for groups near these cut-offs are noisy; see the t-stats.
MIN_FINISHERS_NATIONALITY = 400
MIN_FINISHERS_REGION = 1000

# Placebo shifts (seconds) applied to scraped times to measure how often a
# match key lines up by chance
PLACEBO_SHIFTS = [-40, -20, -10, -5, 5, 10, 20, 40]


def nationality_region(code):
    '''
    Purpose: map a three-letter country code to the paper's regions

    Inputs:
        code (str): country of residence code from the BAA archive

    Returns: (str) 'U.S.', 'Canada', 'Europe' or 'Other'
    '''

    if code == 'USA':
        return cc.REGION_LABELS['us']
    if code == 'CAN':
        return cc.REGION_LABELS['canada']
    if code in EUROPE:
        return cc.REGION_LABELS['europe']

    return cc.REGION_LABELS['other']


def add_match_keys(study):
    '''
    Purpose: build the match keys (time in seconds, age, gender) from
      processed study rows, as match_nationality.split_study_years does

    Inputs:
        study (dataframe): processed study rows

    Returns: (dataframe) STUDY_ROW plus the match keys
    '''

    keys = study[[AGE, GENDER, CHIPTIME]].copy()
    keys[TIME_SEC] = (keys[CHIPTIME] * 60).round().astype('Int64')
    keys[AGE] = keys[AGE].astype('Int64')
    keys[GENDER] = keys[GENDER].astype(str)

    return keys.rename_axis(STUDY_ROW).reset_index()


def read_time_sources(summary_file):
    '''
    Purpose: read which archive time (net or gun) each year was matched on

    Inputs:
        summary_file (str): match summary written by run_boston_match.py

    Returns: (dict) {year: time column}, or None if the file does not exist
    '''

    if not os.path.exists(summary_file):
        return None

    summary = pd.read_csv(summary_file, index_col=0)

    return summary[rb.TIME_SOURCE].to_dict()


# Task 1
def read_boston_nationality(matched_file, data_file, years=YEARS):
    '''
    Purpose: take every Boston study row in the scraped years and attach
      the matched nationality and match status. Rows that could not be
      matched stay in, with nationality missing, so drops can be counted.

    Inputs:
        matched_file (str): boston_matched_all_years.csv
        data_file (str): master_marathon.csv
        years (list of int): race years that were scraped

    Returns: (dataframe) processed Boston study rows indexed by original
      row number, or None if either file does not exist
    '''

    if not (os.path.exists(matched_file) and os.path.exists(data_file)):
        return None

    marathons = cc.read_and_process_marathons(data_file)
    boston = marathons[(marathons[MARATHON] == BOSTON) &
                       marathons[YEAR].isin(years)].copy()
    boston = boston.rename_axis(STUDY_ROW)

    matched = pd.read_csv(matched_file,
                          usecols=[STUDY_ROW, COUNTRY_RES, MATCH_STATUS])
    boston = boston.join(matched.set_index(STUDY_ROW))
    boston[MATCH_STATUS] = boston[MATCH_STATUS].fillna(NOT_IN_SCRAPE)

    assigned = boston[MATCH_STATUS].isin(mn.ASSIGNED)
    boston[NATIONALITY] = boston[COUNTRY_RES].where(assigned)
    boston[NAT_REGION] = boston[NATIONALITY].map(nationality_region,
                                                 na_action='ignore')
    boston = boston.drop(columns=[COUNTRY_RES])

    return boston


# Task 2
def get_match_report(boston):
    '''
    Purpose: for each year, how many study rows got a nationality and why
      the others were dropped

    Inputs:
        boston (dataframe): from read_boston_nationality

    Returns: (dataframe) one row per year plus 'All years': counts, and
      percent of study rows in each match status, or None if the match
      status column is missing
    '''

    if MATCH_STATUS not in boston.columns:
        return None

    counts = (boston.groupby([YEAR, MATCH_STATUS]).size()
              .unstack(fill_value=0)
              .reindex(columns=STUDY_STATUSES, fill_value=0))
    counts.index = counts.index.astype(str)
    counts.loc['All years'] = counts.sum()

    report = pd.DataFrame({'study_rows': counts.sum(axis=1)})
    report['assigned'] = counts[mn.ASSIGNED].sum(axis=1)
    report['dropped'] = report['study_rows'] - report['assigned']
    report['pct_assigned'] = 100 * report['assigned'] / report['study_rows']
    report['pct_dropped'] = 100 - report['pct_assigned']

    pct = 100 * counts.div(report['study_rows'], axis=0)
    pct.columns = [f'pct_{status}' for status in pct.columns]

    return report.join(pct).rename_axis(YEAR).round(2)


# Task 3
def get_scraped_status(boston, time_sources):
    '''
    Purpose: give each scraped runner the status of its match key, so drops
      can be broken down by the runner's nationality (only the scrape knows
      the nationality of runners who were dropped)

    Inputs:
        boston (dataframe): from read_boston_nationality
        time_sources (dict): {year: time column}, from read_time_sources

    Returns: (dataframe) one row per scraped runner: year, country of
      residence, time in seconds and match status
    '''

    frames = []
    for year, time_col in time_sources.items():
        study = add_match_keys(boston[boston[YEAR] == year])
        scraped = rb.load_scraped_year(year, time_col)
        key_info = mn.classify_keys(study, scraped, COUNTRY_RES)
        runners = scraped.merge(key_info[mn.MATCH_KEYS + [MATCH_STATUS]],
                                on=mn.MATCH_KEYS, how='left')
        runners[MATCH_STATUS] = runners[MATCH_STATUS].fillna(MISSING_KEY)
        frames.append(runners[[YEAR, COUNTRY_RES, TIME_SEC, MATCH_STATUS]])

    return pd.concat(frames, ignore_index=True)


# Task 4
def get_drop_rate_by_group(scraped_status, group_col):
    '''
    Purpose: percent of scraped runners in each nationality (or region)
      whose nationality could not be passed to the study data. If this
      differs a lot across groups, the matched sample over- or
      under-represents some nationalities.

    Inputs:
        scraped_status (dataframe): from get_scraped_status
        group_col (str colname): COUNTRY_RES or NAT_REGION

    Returns: (dataframe) one row per group plus 'All', sorted by number of
      scraped runners, or None if group_col does not exist
    '''

    if group_col not in scraped_status.columns:
        return None

    counts = (scraped_status.groupby([group_col, MATCH_STATUS]).size()
              .unstack(fill_value=0))
    counts.loc['All'] = counts.sum()

    table = pd.DataFrame({'scraped': counts.sum(axis=1)})
    table['assigned'] = counts.reindex(columns=mn.ASSIGNED,
                                       fill_value=0).sum(axis=1)
    table['pct_dropped'] = 100 * (1 - table['assigned'] / table['scraped'])
    for status in counts.columns.drop(mn.ASSIGNED, errors='ignore'):
        table[f'pct_{status}'] = 100 * counts[status] / table['scraped']

    table = table.sort_values('scraped', ascending=False)

    return table.rename_axis(group_col).round(2)


# Task 4b
def get_drop_rate_near_round_numbers(scraped_status, group_col,
                                     ref_points=cc.TABLE3_POINTS):
    '''
    Purpose: compare drop rates inside and outside the bunching regions.
      Bunching packs runners into the same seconds, so keys collide more
      there; if drops rise inside the bunching regions, the matched sample
      understates bunching for that group.

    Inputs:
        scraped_status (dataframe): from get_scraped_status
        group_col (str colname): column to group by
        ref_points (list of int): round numbers in minutes

    Returns: (dataframe) percent dropped and runners, inside and outside
      the bunching regions, one row per group, or None if group_col does
      not exist
    '''

    if group_col not in scraped_status.columns:
        return None

    bins = cc.to_time_bins(scraped_status[TIME_SEC].astype(float) / 60)
    in_bunch = pd.Series(False, index=scraped_status.index)
    for point in ref_points:
        in_bunch |= bins.between(point - cc.BUNCH_REGION, point)
    region = in_bunch.map({True: 'bunching', False: 'outside'})

    dropped = ~scraped_status[MATCH_STATUS].isin(mn.ASSIGNED)
    grouping = dropped.groupby([scraped_status[group_col], region])
    table = pd.DataFrame({'pct_dropped': 100 * grouping.mean(),
                          'scraped': grouping.size()}).unstack()
    table.columns = [f'{stat}_{where}' for stat, where in table.columns]

    return table.round(2)


# Task 5
def run_placebo_matches(boston, time_sources, shifts=PLACEBO_SHIFTS):
    '''
    Purpose: shift every scraped time by a few seconds and match again.
      Any nationality assigned this way comes from a key that lines up by
      chance, which is what happens when a study runner is missing from
      the scrape but another runner shares the key.

    Inputs:
        boston (dataframe): from read_boston_nationality
        time_sources (dict): {year: time column}
        shifts (list of int): seconds added to the scraped times

    Returns: (dataframe) one row per (year, shift): study rows, rows
      assigned by the placebo, and how many of those disagree with the
      real match
    '''

    rows = []
    for year, time_col in time_sources.items():
        race = boston[boston[YEAR] == year]
        study = add_match_keys(race)
        scraped = rb.load_scraped_year(year, time_col)

        for shift in shifts:
            placebo = scraped.copy()
            placebo[TIME_SEC] = placebo[TIME_SEC] + shift
            matched = mn.attach_country(study, placebo, COUNTRY_RES)
            resolved = matched[matched[MATCH_STATUS].isin(mn.ASSIGNED)]

            real = race.loc[resolved[STUDY_ROW], NATIONALITY].to_numpy()
            has_real = pd.notna(real)
            fake = resolved[COUNTRY_RES].to_numpy()
            rows.append({YEAR: year,
                         'shift_sec': shift,
                         'study_rows': len(study),
                         'placebo_assigned': len(resolved),
                         'compared': int(has_real.sum()),
                         'wrong_nationality': int(
                             (fake[has_real] != real[has_real]).sum())})

    return pd.DataFrame(rows)


# Task 6
def estimate_matching_error(placebo, report):
    '''
    Purpose: estimate how many assigned nationalities are wrong.

      A study row is matched wrongly only if its own runner is missing
      from the scrape and the key lines up with someone else. Let a be the
      number of study rows whose runner is missing and s the chance-match
      rate from the placebo. Then a * (1 - s) rows are seen as unmatched
      and a * s are matched by mistake, so the false matches are
      unmatched * s / (1 - s). Only a share w of those (the placebo rate
      of disagreeing with the real nationality) get the wrong nationality.

    Inputs:
        placebo (dataframe): from run_placebo_matches
        report (dataframe): from get_match_report

    Returns: (dataframe) one row per year plus 'All years'
    '''

    by_year = placebo.groupby(YEAR)[['study_rows', 'placebo_assigned',
                                     'compared', 'wrong_nationality']].sum()
    by_year.index = by_year.index.astype(str)
    by_year.loc['All years'] = by_year.sum()

    chance = by_year['placebo_assigned'] / by_year['study_rows']
    wrong_share = by_year['wrong_nationality'] / by_year['compared']
    unmatched = (report[f'pct_{NOT_IN_SCRAPE}'] +
                 report[f'pct_{mn.COUNT_MISMATCH}']) / 100 * \
        report['study_rows']
    unmatched = unmatched.reindex(by_year.index)

    false_matches = unmatched * chance / (1 - chance)
    wrong = false_matches * wrong_share
    assigned = report['assigned'].reindex(by_year.index)

    error = pd.DataFrame({'pct_chance_match': 100 * chance,
                          'pct_chance_wrong_nationality': 100 * wrong_share,
                          'unmatched_rows': unmatched,
                          'est_false_matches': false_matches,
                          'est_wrong_nationality': wrong,
                          'est_pct_assigned_wrong': 100 * wrong / assigned})

    return error.rename_axis(YEAR).round(3)


# Task 7
def compare_samples(boston, ref_points=cc.TABLE3_POINTS,
                    min_finishers=MIN_FINISHERS_REGION):
    '''
    Purpose: check that dropping unmatched rows does not change the
      clustering: excess mass for all Boston study rows, the rows that got
      a nationality, and the dropped rows

    Inputs:
        boston (dataframe): from read_boston_nationality
        ref_points (list of int): round numbers in minutes
        min_finishers (int): minimum finishers for a sample to be kept

    Returns: (dataframe) Table 3 style, one row per sample
    '''

    has_nat = boston[NATIONALITY].notna()
    samples = pd.concat([
        boston.assign(**{SAMPLE: 'All study rows'}),
        boston[has_nat].assign(**{SAMPLE: 'Nationality assigned'}),
        boston[~has_nat].assign(**{SAMPLE: 'Dropped'})])

    return cc.make_excess_mass_table(samples, SAMPLE, ref_points,
                                     min_finishers)


def save_and_print(table, name, title):
    '''
    Purpose: write a table to output/ and print it

    Inputs:
        table (dataframe)
        name (str): file name without extension
        title (str): heading to print
    '''

    table.to_csv(os.path.join(OUTPUT_DIR, f'{name}.csv'))
    print(f'\n{title}')
    print(table.to_string())


if __name__ == '__main__':
    boston = read_boston_nationality(MATCHED_FILE, cc.DATA_FILE)
    time_sources = read_time_sources(MATCH_SUMMARY_FILE)
    if boston is None or time_sources is None:
        raise SystemExit('Run run_boston_match.py first.')

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    pd.set_option('display.width', 220)
    pd.set_option('display.max_columns', 30)
    boston.to_csv(NATIONALITY_FILE)

    # Matching and drops
    report = get_match_report(boston)
    save_and_print(report, 'boston_nationality_match_report',
                   'Study rows given a nationality, by year '
                   '(percent of study rows)')

    scraped_status = get_scraped_status(boston, time_sources)
    scraped_status[NAT_REGION] = scraped_status[COUNTRY_RES].map(
        nationality_region, na_action='ignore')
    by_region = get_drop_rate_by_group(scraped_status, NAT_REGION)
    save_and_print(by_region, 'boston_nationality_drops_by_region',
                   'Scraped runners dropped, by nationality region '
                   '(percent of scraped runners)')
    by_nat = get_drop_rate_by_group(scraped_status, COUNTRY_RES)
    by_nat.to_csv(os.path.join(OUTPUT_DIR,
                               'boston_nationality_drops_by_country.csv'))
    print('\nScraped runners dropped, by nationality (100+ runners)')
    print(by_nat[by_nat['scraped'] >= 100].to_string())

    near = get_drop_rate_near_round_numbers(scraped_status, NAT_REGION)
    save_and_print(near, 'boston_nationality_drops_near_round_numbers',
                   'Percent of scraped runners dropped, inside vs outside '
                   'the bunching regions (3:00, 4:00, 5:00)')

    placebo = run_placebo_matches(boston, time_sources)
    placebo.to_csv(os.path.join(OUTPUT_DIR,
                                'boston_nationality_placebo_matches.csv'),
                   index=False)
    error = estimate_matching_error(placebo, report)
    save_and_print(error, 'boston_nationality_match_error',
                   'Estimated wrong nationalities (placebo shifts '
                   f'{PLACEBO_SHIFTS} seconds)')

    samples = compare_samples(boston)
    save_and_print(samples, 'boston_nationality_sample_check',
                   'Excess mass: all study rows vs matched vs dropped')

    # Clusters by nationality
    matched = boston[boston[NATIONALITY].notna()].copy()
    for col, min_n in [(NAT_REGION, MIN_FINISHERS_REGION),
                       (NATIONALITY, MIN_FINISHERS_NATIONALITY)]:
        matched[col] = matched[col].astype('category')
        sizes = matched[col].value_counts()
        groups = sizes[sizes >= min_n].index
        in_groups = matched[matched[col].isin(groups)]

        save_and_print(cc.get_group_summary(in_groups, col).round(1),
                       f'boston_summary_by_{col}',
                       f'Boston finishers by {col} (min {min_n})')

        minute = cc.get_minute_before_after(in_groups, col).round(1)
        save_and_print(minute, f'boston_minute_before_after_by_{col}',
                       'Percent more finishers in the minute before vs '
                       'after')

        long_results = cc.compute_group_excess_mass(
            matched, col, cc.REFERENCE_POINTS, min_n)
        long_results.round(3).to_csv(
            os.path.join(OUTPUT_DIR, f'boston_excess_mass_by_{col}_long.csv'))

        table = cc.make_excess_mass_table(matched, col, cc.TABLE3_POINTS,
                                          min_n)
        save_and_print(table, f'boston_excess_mass_by_{col}',
                       f'Excess mass by {col} (Boston, min {min_n} '
                       'finishers)')
