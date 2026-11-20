'''
Clustering of New York City Marathon finishing times at round-number
reference points, grouped by runner NATIONALITY (citizenship, the NYRR
'iaaf' code) and by country of residence.

Uses the pipeline in country_clusters.py (Allen, Dechow, Pope and Wu 2017
excess-mass estimate) with the columns attached by run_nyc_match.py, under
two assignments: exact (a shared key gets a country only if all its runners
share it; mixed keys are dropped) and fractional (mixed keys are split
across countries by their shares; see
match_nationality.attach_country_shares). Exact assignment drops more
runners where finishers pile up, so it understates bunching; fractional
assignment does not. Also reports how well the matching worked: study rows given a nationality and
why the rest were dropped, drop rates by nationality, and an estimate of
how many assigned nationalities are wrong.

NYC 1999-2005 are not included: NYRR lists only gun times for those years
while the study has chip times, so they cannot be matched.

Run scrape_nyc.py and run_nyc_match.py first.

Sam Salin (svsalin, xx-salin)
'''

import os
import pandas as pd
import boston_nationality_clusters as bnc
import country_clusters as cc
import match_nationality as mn
import run_nyc_match as rn
import scrape_nyc as sn

# Defined constants for column names
YEAR = cc.YEAR
MARATHON = cc.MARATHON
NATIONALITY = cc.NATIONALITY
NAT_STATUS = rn.NAT_STATUS
COUNTRY_RES = sn.COUNTRY_RES
RES_STATUS = rn.RES_STATUS
NAT_REGION = 'nationality_region'
RES_REGION = 'residence_region'
STATUS = 'status'
STUDY_ROW = mn.STUDY_ROW
TIME_SEC = mn.TIME_SEC

MATCHED_FILE = rn.MATCHED_FILE
OUTPUT_DIR = os.path.join(cc.OUTPUT_DIR, 'nyc')
NATIONALITY_FILE = os.path.join(sn.SCRAPE_DIR,
                                'nyc_study_with_nationality.csv')

# Code fixes in the NYRR data
CODE_FIXES = {'U.S': 'USA'}
# NYRR has no IRL code; NIR (Northern Ireland) holds about 3,300 runners a
# year-set, far more than Northern Ireland sends, so it is almost surely
# Ireland. The code is kept and labelled here.
CODE_LABELS = {'NIR': 'NIR (likely Ireland)'}

# NYRR uses ISO-style three-letter codes (DEU, NLD, CHE, ...) plus ENG and
# NIR for parts of the U.K.
EUROPE = {'ALB', 'AND', 'AUT', 'BEL', 'BGR', 'BIH', 'BLR', 'CHE', 'CYP',
          'CZE', 'DEU', 'DNK', 'ENG', 'ESP', 'EST', 'FIN', 'FRA', 'FRO',
          'GBR', 'GIB', 'GRC', 'HRV', 'HUN', 'ISL', 'ITA', 'LIE', 'LTU',
          'LUX', 'LVA', 'MCO', 'MDA', 'MKD', 'MLT', 'NIR', 'NLD', 'NOR',
          'POL', 'PRT', 'ROM', 'RUS', 'SCG', 'SMR', 'SRB', 'SVK', 'SVN',
          'SWE', 'TUR', 'UKR'}

# Statuses used in the match report (study side)
NOT_IN_SCRAPE = bnc.NOT_IN_SCRAPE
NEAR_ASSIGNED = 'pm1s_assigned'
NEAR_UNRESOLVED = 'pm1s_unresolved'
NO_COUNTRY = 'no_country_listed'
REPORT_STATUSES = [mn.UNIQUE, mn.GROUP_SAME, NEAR_ASSIGNED, mn.GROUP_MIXED,
                   mn.COUNT_MISMATCH, NEAR_UNRESOLVED, NO_COUNTRY,
                   NOT_IN_SCRAPE]
ASSIGNED_STATUSES = [mn.UNIQUE, mn.GROUP_SAME, NEAR_ASSIGNED]

MIN_FINISHERS_NATIONALITY = 2000
MIN_FINISHERS_REGION = 1000

PLACEBO_SHIFTS = bnc.PLACEBO_SHIFTS
# Shifts used to measure chance matches in the +-1 second pass
NEAR_PLACEBO_SHIFTS = [-60, -30, 30, 60]


def save_and_print(table, name, title):
    '''
    Purpose: write a table to output/nyc/ and print it

    Inputs:
        table (dataframe)
        name (str): file name without extension
        title (str): heading to print
    '''

    bnc.save_and_print(table, name, title, OUTPUT_DIR)


def nationality_region(code):
    '''
    Purpose: map an NYRR country code to the paper's regions

    Inputs:
        code (str): three-letter country code

    Returns: (str) 'U.S.', 'Canada', 'Europe' or 'Other'
    '''

    if code == 'USA':
        return cc.REGION_LABELS['us']
    if code == 'CAN':
        return cc.REGION_LABELS['canada']
    if code in EUROPE:
        return cc.REGION_LABELS['europe']

    return cc.REGION_LABELS['other']


def simplify_status(status, has_country):
    '''
    Purpose: collapse exact and +-1 second statuses into report statuses

    Inputs:
        status (str or NaN): match status from run_nyc_match.py
        has_country (bool): whether the row got a country

    Returns: (str) one of REPORT_STATUSES
    '''

    if pd.isna(status):
        return NOT_IN_SCRAPE
    if status.endswith('s'):
        return NEAR_ASSIGNED if has_country else NEAR_UNRESOLVED
    if status in mn.ASSIGNED and not has_country:
        return NO_COUNTRY

    return status


def chip_years():
    '''
    Purpose: list the NYC years that were matched (NYRR has chip times)

    Returns: (list of int)
    '''

    return [year for year in sn.EVENT_CODES
            if rn.load_scraped_year(year, sn.NET_SEC) is not None
            and rn.has_chip_time(year)]


# Task 1
def read_nyc_nationality(matched_file, data_file, years):
    '''
    Purpose: take every NYC study row in the matched years and attach
      nationality, residence and their match statuses. Rows that could not
      be matched stay in, with nationality missing, so drops can be counted.

    Inputs:
        matched_file (str): nyc_matched_all_years.csv
        data_file (str): master_marathon.csv
        years (list of int): matched race years

    Returns: (dataframe) processed NYC study rows indexed by original row
      number, or None if either file does not exist
    '''

    if not (os.path.exists(matched_file) and os.path.exists(data_file)):
        return None

    marathons = cc.read_and_process_marathons(data_file)
    nyc = marathons[(marathons[MARATHON] == rn.NYC) &
                    marathons[YEAR].isin(years)].copy()
    nyc = nyc.rename_axis(STUDY_ROW)

    cols = [STUDY_ROW, NATIONALITY, NAT_STATUS, COUNTRY_RES, RES_STATUS]
    matched = pd.read_csv(matched_file, usecols=cols)
    matched[[NATIONALITY, COUNTRY_RES]] = matched[
        [NATIONALITY, COUNTRY_RES]].replace(CODE_FIXES)
    nyc = nyc.join(matched.set_index(STUDY_ROW))

    nyc[STATUS] = [simplify_status(status, pd.notna(country))
                   for status, country in zip(nyc[NAT_STATUS],
                                              nyc[NATIONALITY])]
    nyc[NAT_REGION] = nyc[NATIONALITY].map(nationality_region,
                                           na_action='ignore')
    nyc[RES_REGION] = nyc[COUNTRY_RES].map(nationality_region,
                                           na_action='ignore')

    return nyc


# Task 2
def get_match_report(nyc):
    '''
    Purpose: for each year, how many study rows got a nationality and why
      the others were dropped

    Inputs:
        nyc (dataframe): from read_nyc_nationality

    Returns: (dataframe) one row per year plus 'All years'
    '''

    counts = (nyc.groupby([YEAR, STATUS]).size().unstack(fill_value=0)
              .reindex(columns=REPORT_STATUSES, fill_value=0))
    counts.index = counts.index.astype(str)
    counts.loc['All years'] = counts.sum()

    report = pd.DataFrame({'study_rows': counts.sum(axis=1)})
    report['assigned'] = counts[ASSIGNED_STATUSES].sum(axis=1)
    report['dropped'] = report['study_rows'] - report['assigned']
    report['pct_assigned'] = 100 * report['assigned'] / report['study_rows']
    report['pct_dropped'] = 100 - report['pct_assigned']

    pct = 100 * counts.div(report['study_rows'], axis=0)
    pct.columns = [f'pct_{status}' for status in pct.columns]

    return report.join(pct).rename_axis(YEAR).round(2)


def load_scraped(years):
    '''
    Purpose: read the scraped runners for the matched years

    Inputs:
        years (list of int)

    Returns: (dataframe) year, nationality, residence and net time bin
    '''

    frames = []
    for year in years:
        scraped = rn.load_scraped_year(year, sn.NET_SEC)
        frames.append(scraped[[YEAR, sn.NATIONALITY, COUNTRY_RES,
                               sn.NET_SEC]])
    scraped = pd.concat(frames, ignore_index=True)
    scraped[[NATIONALITY, COUNTRY_RES]] = scraped[
        [NATIONALITY, COUNTRY_RES]].replace(CODE_FIXES)
    scraped[NAT_REGION] = scraped[NATIONALITY].map(nationality_region,
                                                   na_action='ignore')
    scraped[cc.BIN_TIME] = cc.to_time_bins(
        scraped[sn.NET_SEC].astype(float) / 60)

    return scraped


# Task 3
def get_drop_rate_by_group(nyc, scraped, group_col, fractional=None):
    '''
    Purpose: percent of scraped runners in each nationality (or region)
      whose nationality did not reach the study data. Every assigned study
      row corresponds to one scraped runner of the same nationality, so
      the drop rate is 1 - assigned / scraped. With fractional assignment
      the assigned count is the sum of weights.

    Inputs:
        nyc (dataframe): from read_nyc_nationality
        scraped (dataframe): from load_scraped
        group_col (str colname): NATIONALITY or NAT_REGION
        fractional (dataframe): from read_fractional, optional

    Returns: (dataframe) one row per group plus 'All', sorted by number of
      scraped runners
    '''

    table = pd.DataFrame({'scraped': scraped.groupby(group_col).size(),
                          'assigned': nyc.groupby(group_col).size()})
    if fractional is not None:
        table['assigned_fractional'] = fractional.groupby(group_col)[
            cc.WEIGHT].sum()
    table = table.fillna(0)
    table.loc['All'] = table.sum()
    table['pct_dropped'] = 100 * (1 - table['assigned'] / table['scraped'])
    if fractional is not None:
        table['pct_dropped_fractional'] = 100 * (
            1 - table['assigned_fractional'] / table['scraped'])

    return table.sort_values('scraped', ascending=False).round(2)


def bunching_flag(bins, ref_points=cc.TABLE3_POINTS):
    '''
    Purpose: label time bins as inside or outside the bunching regions

    Inputs:
        bins (series of float): bin labels in minutes
        ref_points (list of int): round numbers in minutes

    Returns: (series of str) 'bunching' or 'outside'
    '''

    flag = pd.Series(False, index=bins.index)
    for point in ref_points:
        flag |= bins.between(point - cc.BUNCH_REGION, point)

    return flag.map({True: 'bunching', False: 'outside'})


# Task 3b
def get_drop_rate_near_round_numbers(nyc, scraped, group_col,
                                     fractional=None):
    '''
    Purpose: compare drop rates inside and outside the bunching regions
      (see boston_nationality_clusters.get_drop_rate_near_round_numbers),
      for exact and, if given, fractional assignment

    Inputs:
        nyc (dataframe), scraped (dataframe), fractional (dataframe): as in
          get_drop_rate_by_group
        group_col (str colname): column to group by

    Returns: (dataframe) runners scraped and percent dropped, inside and
      outside the bunching regions, one row per group
    '''

    scraped_n = scraped.groupby(
        [scraped[group_col], bunching_flag(scraped[cc.BIN_TIME])]).size()
    assigned = nyc[nyc[group_col].notna()]
    assigned_n = assigned.groupby(
        [assigned[group_col].astype(str),
         bunching_flag(assigned[cc.BIN_TIME].astype(float))]).size()

    table = pd.DataFrame({'scraped': scraped_n,
                          'pct_dropped': 100 * (1 - assigned_n / scraped_n)})
    if fractional is not None:
        weights = fractional[cc.WEIGHT].groupby(
            [fractional[group_col],
             bunching_flag(fractional[cc.BIN_TIME].astype(float))]).sum()
        table['pct_dropped_fractional'] = 100 * (1 - weights / scraped_n)
    table = table.unstack()
    table.columns = [f'{stat}_{where}' for stat, where in table.columns]

    return table.round(2)


# Task 4
def run_placebo_matches(nyc, years, shifts=PLACEBO_SHIFTS):
    '''
    Purpose: exact-match placebo, as in
      boston_nationality_clusters.run_placebo_matches: shift every scraped
      time by a few seconds and count nationalities assigned by chance

    Inputs:
        nyc (dataframe): from read_nyc_nationality
        years (list of int): matched years
        shifts (list of int): seconds added to the scraped times

    Returns: (dataframe) one row per (year, shift)
    '''

    rows = []
    for year in years:
        race = nyc[nyc[YEAR] == year]
        study = bnc.add_match_keys(race)
        keys = rn.match_keys(race)
        scraped = rn.load_scraped_year(year, sn.NET_SEC)

        for shift in shifts:
            placebo = scraped.assign(**{TIME_SEC: scraped[TIME_SEC] + shift})
            matched = mn.attach_country(study, placebo, sn.NATIONALITY, keys)
            resolved = matched[matched[mn.MATCH_STATUS].isin(mn.ASSIGNED)
                               & matched[sn.NATIONALITY].notna()]

            real = race.loc[resolved[STUDY_ROW], NATIONALITY].to_numpy()
            has_real = pd.notna(real)
            fake = resolved[sn.NATIONALITY].replace(CODE_FIXES).to_numpy()
            rows.append({YEAR: year,
                         'shift_sec': shift,
                         'study_rows': len(study),
                         'placebo_assigned': len(resolved),
                         'compared': int(has_real.sum()),
                         'wrong_nationality': int(
                             (fake[has_real] != real[has_real]).sum())})

    return pd.DataFrame(rows)


# Task 5
def estimate_near_match_error(nyc, years, shifts=NEAR_PLACEBO_SHIFTS):
    '''
    Purpose: estimate how many +-1 second matches are chance matches by
      running the same second pass at shifts far from 1 second

    Inputs:
        nyc (dataframe): from read_nyc_nationality
        years (list of int): matched years
        shifts (list of int): placebo shifts in seconds

    Returns: (dataframe) one row per year plus 'All years': +-1 second
      matches, average placebo matches per shift, and the estimated share
      of +-1 second matches that are chance
    '''

    rows = []
    for year in years:
        race = nyc[nyc[YEAR] == year]
        study = bnc.add_match_keys(race)
        keys = rn.match_keys(race)
        scraped = rn.load_scraped_year(year, sn.NET_SEC)

        placebo = []
        for shift in shifts:
            matched = rn.near_match(study, scraped, sn.NATIONALITY, keys,
                                    [shift])
            placebo.append(matched[sn.NATIONALITY].notna().sum())
        rows.append({YEAR: str(year),
                     'pm1s_assigned': int((race[STATUS] ==
                                           NEAR_ASSIGNED).sum()),
                     'placebo_per_shift': sum(placebo) / len(placebo)})

    table = pd.DataFrame(rows).set_index(YEAR)
    table.loc['All years'] = table.sum()
    table['est_pct_chance'] = (100 * table['placebo_per_shift'] /
                               table['pm1s_assigned'].where(
                                   table['pm1s_assigned'] > 0))

    return table.round(2)


def estimate_matching_error(placebo, report, near_error):
    '''
    Purpose: combine the exact-match placebo (see
      boston_nationality_clusters.estimate_matching_error) with the
      chance share of +-1 second matches

    Inputs:
        placebo (dataframe): from run_placebo_matches
        report (dataframe): from get_match_report
        near_error (dataframe): from estimate_near_match_error

    Returns: (dataframe) one row per year plus 'All years'
    '''

    exact = bnc.estimate_matching_error(placebo, report)
    near_wrong = (near_error['placebo_per_shift'] *
                  exact['pct_chance_wrong_nationality'] / 100)
    exact['est_wrong_pm1s'] = near_wrong.reindex(exact.index)
    total_wrong = exact['est_wrong_nationality'] + exact['est_wrong_pm1s']
    exact['est_pct_assigned_wrong'] = (100 * total_wrong /
                                       report['assigned'].reindex(
                                           exact.index))

    return exact.round(3)


# Task 6
def read_fractional(nyc, country_col):
    '''
    Purpose: read the fractional assignment written by run_nyc_match.py
      and attach the study columns the clustering needs

    Inputs:
        nyc (dataframe): from read_nyc_nationality
        country_col (str colname): NATIONALITY or COUNTRY_RES

    Returns: (dataframe) one row per (study row, country) with WEIGHT and
      the matching region column, or None if the file does not exist
    '''

    path = rn.FRACTIONAL_FILES[country_col]
    if not os.path.exists(path):
        return None

    frac = pd.read_csv(path, usecols=[STUDY_ROW, country_col, cc.WEIGHT])
    frac[country_col] = frac[country_col].replace(CODE_FIXES)
    study_cols = [YEAR, cc.CHIPTIME, cc.BIN_TIME, cc.MARATHON_YEAR]
    frac = frac.merge(nyc[study_cols], left_on=STUDY_ROW, right_index=True)
    region_col = NAT_REGION if country_col == NATIONALITY else RES_REGION
    frac[region_col] = frac[country_col].map(nationality_region)

    return frac.reset_index(drop=True)


# Task 7
def compare_samples(nyc, fractional, ref_points=cc.TABLE3_POINTS,
                    min_finishers=MIN_FINISHERS_REGION):
    '''
    Purpose: check whether each assignment method changes the clustering:
      excess mass for all NYC study rows, exact assignment only, fractional
      assignment, and the rows exact assignment drops

    Inputs:
        nyc (dataframe): from read_nyc_nationality
        fractional (dataframe): from read_fractional
        ref_points (list of int): round numbers in minutes
        min_finishers (int): minimum finishers for a sample to be kept

    Returns: (dataframe) Table 3 style, one row per sample
    '''

    has_nat = nyc[NATIONALITY].notna()
    cols = [YEAR, cc.CHIPTIME, cc.BIN_TIME, cc.MARATHON_YEAR]
    samples = pd.concat([
        nyc[cols].assign(**{bnc.SAMPLE: 'All study rows'}),
        nyc.loc[has_nat, cols].assign(**{bnc.SAMPLE: 'Exact assignment'}),
        fractional[cols + [cc.WEIGHT]].assign(
            **{bnc.SAMPLE: 'Fractional assignment'}),
        nyc.loc[~has_nat, cols].assign(
            **{bnc.SAMPLE: 'Dropped by exact assignment'})],
        ignore_index=True)
    samples[cc.WEIGHT] = samples[cc.WEIGHT].fillna(1.0)

    return cc.make_excess_mass_table(samples, bnc.SAMPLE, ref_points,
                                     min_finishers)


def cluster_tables(matched, col, min_n, label):
    '''
    Purpose: group summary, minute before/after and excess-mass tables for
      one grouping column, written to output/

    Inputs:
        matched (dataframe): study rows with col filled in
        col (str colname): grouping column
        min_n (int): minimum finishers per group
        label (str): name used in file names and headings
    '''

    matched = matched[matched[col].notna()].copy()
    matched[col] = matched[col].replace(CODE_LABELS).astype('category')
    sizes = cc.finisher_weights(matched).groupby(matched[col],
                                                 observed=True).sum()
    in_groups = matched[matched[col].isin(sizes[sizes >= min_n].index)]

    save_and_print(cc.get_group_summary(in_groups, col).round(1),
                       f'nyc_summary_by_{label}',
                       f'NYC finishers by {label} (min {min_n})')
    save_and_print(cc.get_minute_before_after(in_groups, col).round(1),
                       f'nyc_minute_before_after_by_{label}',
                       'Percent more finishers in the minute before vs after')

    long_results = cc.compute_group_excess_mass(
        matched, col, cc.REFERENCE_POINTS, min_n)
    long_results.round(3).to_csv(
        os.path.join(OUTPUT_DIR, f'nyc_excess_mass_by_{label}_long.csv'))
    table = cc.make_excess_mass_table(matched, col, cc.TABLE3_POINTS, min_n)
    save_and_print(table, f'nyc_excess_mass_by_{label}',
                       f'Excess mass by {label} (NYC, min {min_n} '
                       'finishers)')


if __name__ == '__main__':
    years = chip_years()
    nyc = read_nyc_nationality(MATCHED_FILE, cc.DATA_FILE, years)
    if nyc is None:
        raise SystemExit('Run run_nyc_match.py first.')

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    pd.set_option('display.width', 220)
    pd.set_option('display.max_columns', 30)
    nyc.to_csv(NATIONALITY_FILE)
    frac_nat = read_fractional(nyc, NATIONALITY)
    frac_res = read_fractional(nyc, COUNTRY_RES)
    if frac_nat is None or frac_res is None:
        raise SystemExit('Run run_nyc_match.py first.')
    row_sums = frac_nat.groupby(STUDY_ROW)[cc.WEIGHT].sum()
    print(f'Fractional: {len(row_sums)} study rows '
          f'({100 * len(row_sums) / len(nyc):.2f}%), weights per row sum to '
          f'1 within {abs(row_sums - 1).max():.1e}')

    # Matching and drops
    report = get_match_report(nyc)
    save_and_print(report, 'nyc_nationality_match_report',
                       'Study rows given a nationality, by year '
                       '(percent of study rows)')

    scraped = load_scraped(years)
    by_region = get_drop_rate_by_group(nyc, scraped, NAT_REGION, frac_nat)
    save_and_print(by_region, 'nyc_nationality_drops_by_region',
                       'Scraped runners dropped, by nationality region')
    by_nat = get_drop_rate_by_group(nyc, scraped, NATIONALITY, frac_nat)
    by_nat.to_csv(os.path.join(OUTPUT_DIR,
                               'nyc_nationality_drops_by_country.csv'))
    print('\nScraped runners dropped, by nationality (2,000+ runners)')
    print(by_nat[by_nat['scraped'] >= 2000].to_string())

    near = get_drop_rate_near_round_numbers(nyc, scraped, NAT_REGION,
                                            frac_nat)
    save_and_print(near, 'nyc_nationality_drops_near_round_numbers',
                       'Percent dropped, inside vs outside the bunching '
                       'regions (3:00, 4:00, 5:00)')

    placebo = run_placebo_matches(nyc, years)
    placebo.to_csv(os.path.join(OUTPUT_DIR,
                                'nyc_nationality_placebo_matches.csv'),
                   index=False)
    near_error = estimate_near_match_error(nyc, years)
    save_and_print(near_error, 'nyc_nationality_pm1s_error',
                       'Chance matches in the +-1 second pass '
                       f'(placebo shifts {NEAR_PLACEBO_SHIFTS} s)')
    error = estimate_matching_error(placebo, report, near_error)
    save_and_print(error, 'nyc_nationality_match_error',
                       'Estimated wrong nationalities')

    samples = compare_samples(nyc, frac_nat)
    save_and_print(samples, 'nyc_nationality_sample_check',
                   'Excess mass: all study rows vs exact vs fractional '
                   'assignment')

    # Clusters by citizenship and by residence
    cluster_tables(nyc, NAT_REGION, MIN_FINISHERS_REGION,
                   'nationality_region')
    cluster_tables(nyc, RES_REGION, MIN_FINISHERS_REGION, 'residence_region')
    cluster_tables(nyc, NATIONALITY, MIN_FINISHERS_NATIONALITY,
                   'nationality')

    # Same, with fractional assignment of mixed-country keys
    cluster_tables(frac_nat, NAT_REGION, MIN_FINISHERS_REGION,
                   'nationality_region_fractional')
    cluster_tables(frac_res, RES_REGION, MIN_FINISHERS_REGION,
                   'residence_region_fractional')
    cluster_tables(frac_nat, NATIONALITY, MIN_FINISHERS_NATIONALITY,
                   'nationality_fractional')
