'''
Clustering of marathon finishing times at round-number reference points,
grouped by country.

Replicates the excess-mass (bunching) estimate in Allen, Dechow, Pope and
Wu (2017), "Reference-Dependent Preferences: Evidence from Marathon
Runners," Management Science 63(6), which adapts Chetty, Friedman, Olsen
and Pistaferri (2011). The authors' Stata code is in
original_data/mnsc.2-15-2417-SM-data-do/ (see_boot2.do and
bootstrap_excessmass.do).

The grouping column is a parameter everywhere, so the same pipeline runs on
runner nationality once that column is scraped and merged in.

Sam Salin (svsalin, xx-salin)
'''

import os
import numpy as np
import pandas as pd

# Defined constants for column names
AGE = 'age'
GENDER = 'gender'
CHIPTIME = 'chiptime'
YEAR = 'year'
MARATHON = 'marathon'
MARATHON_YEAR = 'marathon2'
COUNTRY = 'country'
REGION = 'region'
BIN_TIME = 'bin_time'
NATIONALITY = 'nationality'  # not in the released data; added after scraping
# Optional row weight. When a match key is shared by runners of different
# nationalities, each study row is split across those nationalities with
# weights equal to their shares (see match_nationality.attach_country_shares).
# Every function below counts finishers as the sum of WEIGHT when the column
# is present, and as rows otherwise.
WEIGHT = 'weight'

# Repository root (this file lives in src/)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(
    ROOT_DIR, 'original_data',
    'mnsc.2015-2417-SM-data-master_marathom', 'master_marathon.csv')
OUTPUT_DIR = os.path.join(ROOT_DIR, 'output')
# Replication of the paper by race location (this file's own results)
REPLICATION_DIR = os.path.join(OUTPUT_DIR, 'replication')

COL_TYPES = {AGE: float,
             GENDER: str,
             CHIPTIME: float,
             YEAR: int,
             MARATHON: str,
             MARATHON_YEAR: str,
             COUNTRY: str,
             'us': int,
             'canada': int,
             'europe': int,
             'other': int}

# Region dummies in the released data, labelled as in Table 3 of the paper
REGION_LABELS = {'us': 'U.S.', 'europe': 'Europe',
                 'canada': 'Canada', 'other': 'Other'}

CATEGORICAL_COLS = [GENDER, MARATHON, COUNTRY, REGION]

# Chetty et al. (2011) settings as used by Allen et al. (all in minutes)
BIN_WIDTH = 0.25     # 15-second bins
BUNCH_REGION = 4     # bunching region: the 4 minutes up to the round number
WINDOW = 8           # counterfactual fit uses 8 minutes either side
# The paper's text says cubic, and a cubic reproduces Table 2 on this data
# (e.g. 24.2% vs 24.6% at 3:00, 6.0% vs 6.2% at 3:10). The shipped
# see_boot2.do fits a 5th-degree polynomial, which does not match Table 2.
POLY_DEGREE = 3
N_BOOT = 500         # bootstrap replications reported in the paper
SEED = 30121

# Round numbers tested in Table 2 of the paper (3:00 ... 6:00)
REFERENCE_POINTS = [180, 190, 200, 210, 240, 270, 300, 360]
# Round numbers shown in Table 3 (robustness by region, year, size, age)
TABLE3_POINTS = [180, 240, 300]

# Groups smaller than this are dropped before estimating
MIN_FINISHERS = 5000


def to_time_bins(times, bin_width=BIN_WIDTH):
    '''
    Purpose: assign finishing times to 15-second bins the way the Stata
      code does: round(chiptime + .125, .25). Each bin is labelled by its
      upper edge, so a 3:59:45 to 3:59:59 finish lands in the 4:00 bin.

    Inputs:
        times (series of float): finishing times in minutes
        bin_width (float): bin width in minutes

    Returns: (series of float) the bin label for each time
    '''

    steps = np.floor(np.round(times / bin_width, 6)) + 1

    return steps * bin_width


def format_minutes(minutes):
    '''
    Purpose: format a time in minutes as H:MM (e.g. 240 -> '4:00')

    Inputs:
        minutes (int)

    Returns: (str) the formatted time
    '''

    return f'{int(minutes) // 60}:{int(minutes) % 60:02d}'


def finisher_weights(df):
    '''
    Purpose: the weight each row counts for: WEIGHT if present, else 1

    Inputs:
        df (dataframe)

    Returns: (series of float) aligned with df
    '''

    if WEIGHT in df.columns:
        return df[WEIGHT].astype(float)

    return pd.Series(1.0, index=df.index)


# Task 1
def read_and_process_marathons(csv_file):
    '''
    Purpose: read in master_marathon.csv and add the columns needed for
      the clustering analysis.

    Inputs:
        csv_file (string): path to the csv file to open

    Returns: (dataframe): a processed dataframe,
      or None if the file does not exist
    '''

    if not os.path.exists(csv_file):
        return None

    df = pd.read_csv(csv_file, usecols=list(COL_TYPES), dtype=COL_TYPES,
                     encoding='latin-1')

    df[BIN_TIME] = to_time_bins(df[CHIPTIME])

    dummies = df[list(REGION_LABELS)]
    df[REGION] = dummies.idxmax(axis=1).map(REGION_LABELS)
    df = df.drop(columns=list(REGION_LABELS))

    df[CATEGORICAL_COLS] = df[CATEGORICAL_COLS].astype('category')

    return df


# Task 2a
def apply_val_filters(df, filter_info):
    '''
    Purpose: apply a value filter to a dataframe

    Inputs:
        df (dataframe)
        filter_info (dict): of the form {'column_name':
            ['value1', 'value2', ...]}

    Returns: (dataframe) filtered dataframe,
      or None if a specified column does not exist
    '''

    filtered_df = df
    for col, vals in filter_info.items():

        if col not in filtered_df:
            return None

        filtered_df = filtered_df[filtered_df[col].isin(vals)]

    return filtered_df


# Task 2b
def apply_range_filters(df, filter_info):
    '''
    Purpose: apply a range filter to a dataframe (bounds inclusive)

    Inputs:
        df (dataframe)
        filter_info (dict): of the form {'column_name': [low, high]}

    Returns: (dataframe) filtered dataframe,
      or None if a specified column does not exist
    '''

    filtered_df = df
    for col, vals in filter_info.items():

        if col not in filtered_df:
            return None

        filtered_df = filtered_df[filtered_df[col].between(*vals)]

    return filtered_df


# Task 3
def get_group_summary(df, group_col):
    '''
    Purpose: describe each group the way the left side of Table 3 does:
      number of marathon-years, mean finishing time, number of finishers.

    Inputs:
        df (dataframe)
        group_col (str colname): column to group by (e.g. country)

    Returns: (dataframe) one row per group, sorted by number of finishers,
      or None if group_col does not exist
    '''

    if group_col not in df.columns:
        return None

    weights = finisher_weights(df)
    weighted = df.assign(_weight=weights, _time=df[CHIPTIME] * weights)
    grouping = weighted.groupby(group_col, observed=True)
    summary = grouping.agg(n_marathon_years=(MARATHON_YEAR, 'nunique'),
                           _time=('_time', 'sum'),
                           n_finishers=('_weight', 'sum'))
    summary.insert(1, 'mean_time', summary.pop('_time') /
                   summary['n_finishers'])

    return summary.sort_values('n_finishers', ascending=False)


# Task 4
def get_bin_counts(df, group_col, low=None, high=None,
                   bin_width=BIN_WIDTH):
    '''
    Purpose: count finishers in each 15-second bin for each group. This is
      the clustered finishing-time distribution the estimates work from.

    Inputs:
        df (dataframe): must contain BIN_TIME
        group_col (str colname): column to group by
        low, high (float): first and last bin to keep, in minutes;
          defaults to the window around the reference points
        bin_width (float): bin width in minutes

    Returns: (dataframe) groups as rows, bins as columns, empty bins as 0,
      or None if group_col does not exist
    '''

    if group_col not in df.columns:
        return None

    if low is None:
        low = min(REFERENCE_POINTS) - WINDOW
    if high is None:
        high = max(REFERENCE_POINTS) + WINDOW

    in_range = df[df[BIN_TIME].between(low, high)]
    in_range = in_range.assign(_weight=finisher_weights(in_range))
    counts = (in_range.groupby([group_col, BIN_TIME], observed=True)
              ['_weight'].sum().unstack(fill_value=0))

    all_bins = np.arange(low, high + bin_width / 2, bin_width)

    return counts.reindex(columns=all_bins, fill_value=0)


# Task 5
def get_minute_before_after(df, group_col, ref_points=REFERENCE_POINTS):
    '''
    Purpose: the paper's simple bunching measure (Section 4.1): percent
      more finishers in the minute before a round number (e.g. 3:59:00 to
      3:59:59) than in the minute after it (4:00:00 to 4:00:59).

    Inputs:
        df (dataframe)
        group_col (str colname): column to group by
        ref_points (list of int): round numbers in minutes

    Returns: (dataframe) groups as rows, round numbers as columns, values
      in percent, or None if group_col does not exist
    '''

    if group_col not in df.columns:
        return None

    minute = np.floor(np.round(df[CHIPTIME], 6)).to_numpy()
    weights = finisher_weights(df).to_numpy()
    groups = df[group_col]
    rows = {}
    for point in ref_points:
        before = pd.Series(weights * (minute == point - 1),
                           index=df.index).groupby(groups,
                                                   observed=True).sum()
        after = pd.Series(weights * (minute == point),
                          index=df.index).groupby(groups,
                                                  observed=True).sum()
        rows[format_minutes(point)] = 100 * (before / after - 1)

    return pd.DataFrame(rows)


def window_bins(bunchpoint, window=WINDOW, bin_width=BIN_WIDTH):
    '''
    Purpose: list the bins in the fit window around a round number

    Inputs:
        bunchpoint (float): round number in minutes
        window (float): minutes on each side
        bin_width (float): bin width in minutes

    Returns: (array of float) bin labels from bunchpoint - window to
      bunchpoint + window
    '''

    n_bins = int(round(2 * window / bin_width)) + 1

    return np.linspace(bunchpoint - window, bunchpoint + window, n_bins)


# Task 6
def estimate_excess_mass(counts, bins, bunchpoint,
                         bunch_region=BUNCH_REGION, degree=POLY_DEGREE):
    '''
    Purpose: Chetty et al. (2011) excess mass at one round number, as in
      see_boot2.do. Fit a polynomial to the bin counts outside the
      bunching region, shift it up so it holds the same number of
      finishers as the actual counts over the whole window, then compare
      actual and fitted finishers inside the bunching region.

    Inputs:
        counts (array): bin counts, shape (n_bins,) or (n_bins, n_samples)
          so bootstrap draws can be estimated in one pass
        bins (array of float): bin labels matching the rows of counts
        bunchpoint (float): round number in minutes
        bunch_region (float): minutes before the round number counted as
          bunching
        degree (int): polynomial degree

    Returns: (tuple of arrays) actual finishers, counterfactual finishers,
      excess finishers, excess percent; one value per sample
    '''

    counts = np.asarray(counts, dtype=float)
    if counts.ndim == 1:
        counts = counts[:, None]

    # Centre and scale time so the polynomial fit is well conditioned;
    # fitted values are the same as with raw times.
    x = (bins - bunchpoint) / (bins.max() - bunchpoint)
    design = np.vander(x, degree + 1)

    in_region = (bins >= bunchpoint - bunch_region) & (bins <= bunchpoint)
    coefs = np.linalg.lstsq(design[~in_region], counts[~in_region],
                            rcond=None)[0]
    fitted = design @ coefs
    fitted += (counts.sum(axis=0) - fitted.sum(axis=0)) / len(bins)

    actual = counts[in_region].sum(axis=0)
    counterfactual = fitted[in_region].sum(axis=0)
    excess = actual - counterfactual

    with np.errstate(divide='ignore', invalid='ignore'):
        excess_pct = np.where(counterfactual > 0,
                              100 * excess / counterfactual, np.nan)

    return actual, counterfactual, excess, excess_pct


# Task 7
def bootstrap_excess_mass(counts, bins, bunchpoint, reps=N_BOOT, rng=None,
                          bunch_region=BUNCH_REGION, degree=POLY_DEGREE):
    '''
    Purpose: excess mass at one round number with a bootstrap standard
      error. Resampling finishers in the window with replacement is the
      same as a multinomial draw of the bin counts, which is what Stata's
      bootstrap command does in bootstrap_excessmass.do.

    Inputs:
        counts (array): bin counts in the window, shape (n_bins,)
        bins (array of float): bin labels matching counts
        bunchpoint (float): round number in minutes
        reps (int): bootstrap replications
        rng (numpy Generator): random number generator
        bunch_region (float), degree (int): see estimate_excess_mass

    Returns: (dict) n_window, actual, counterfactual, excess, excess_pct,
      se (of excess_pct) and t_stat
    '''

    if rng is None:
        rng = np.random.default_rng(SEED)

    counts = np.asarray(counts, dtype=float)
    # Weighted counts can be fractional; resample the rounded number of
    # finishers with the weighted bin shares
    n_window = int(round(counts.sum()))

    actual, counterfactual, excess, excess_pct = estimate_excess_mass(
        counts, bins, bunchpoint, bunch_region, degree)

    se = np.nan
    if n_window > 0 and reps > 1:
        draws = rng.multinomial(n_window, counts / counts.sum(),
                                size=reps).T
        boot_pct = estimate_excess_mass(draws, bins, bunchpoint,
                                        bunch_region, degree)[3]
        if np.isfinite(boot_pct).sum() > 1:
            se = np.nanstd(boot_pct, ddof=1)

    # Tiny groups can give the same estimate in every draw (se ~ 0)
    t_stat = excess_pct[0] / se if se > 1e-9 else np.nan

    return {'n_window': n_window,
            'actual': actual[0],
            'counterfactual': counterfactual[0],
            'excess': excess[0],
            'excess_pct': excess_pct[0],
            'se': se,
            't_stat': t_stat}


# Task 8
def compute_group_excess_mass(df, group_col, ref_points=REFERENCE_POINTS,
                              min_finishers=MIN_FINISHERS, reps=N_BOOT,
                              seed=SEED):
    '''
    Purpose: run the excess-mass estimate for every group and every round
      number.

    Inputs:
        df (dataframe)
        group_col (str colname): column to group by (country now,
          nationality after scraping)
        ref_points (list of int): round numbers in minutes
        min_finishers (int): minimum finishers for a group to be kept
        reps (int): bootstrap replications
        seed (int): random seed, so results are reproducible

    Returns: (dataframe) one row per (group, round number), or None if
      group_col does not exist or no group meets min_finishers
    '''

    if group_col not in df.columns:
        return None

    sizes = finisher_weights(df).groupby(df[group_col], observed=True).sum()
    keep = sizes[sizes >= min_finishers].sort_values(ascending=False).index
    if len(keep) == 0:
        return None

    kept_df = df[df[group_col].isin(keep)]
    low = min(ref_points) - WINDOW
    high = max(ref_points) + WINDOW
    counts = get_bin_counts(kept_df, group_col, low, high)

    rng = np.random.default_rng(seed)
    rows = []
    for group in keep:
        for point in ref_points:
            bins = window_bins(point)
            result = bootstrap_excess_mass(counts.loc[group, bins].to_numpy(),
                                           bins, point, reps, rng)
            result[group_col] = group
            result['ref_point'] = format_minutes(point)
            rows.append(result)

    results = pd.DataFrame(rows).set_index([group_col, 'ref_point'])

    return results


# Task 9
def make_excess_mass_table(df, group_col, ref_points=TABLE3_POINTS,
                           min_finishers=MIN_FINISHERS, reps=N_BOOT,
                           seed=SEED):
    '''
    Purpose: build a Table 3 style summary: group description followed by
      percent excess finishers and t-statistic at each round number.

    Inputs:
        df (dataframe)
        group_col (str colname): column to group by
        ref_points (list of int): round numbers in minutes
        min_finishers (int), reps (int), seed (int): see
          compute_group_excess_mass

    Returns: (dataframe) one row per group, or None if group_col does not
      exist or no group meets min_finishers
    '''

    results = compute_group_excess_mass(df, group_col, ref_points,
                                        min_finishers, reps, seed)
    if results is None:
        return None

    wide = results[['excess_pct', 't_stat']].unstack('ref_point')
    wide = wide.swaplevel(axis=1)
    labels = [format_minutes(p) for p in ref_points]
    wide = wide.reindex(columns=[(label, stat) for label in labels
                                 for stat in ['excess_pct', 't_stat']])
    wide.columns = [f'{stat}_{label}' for label, stat in wide.columns]

    summary = get_group_summary(df, group_col)
    table = summary.join(wide, how='inner')

    return table.sort_values('n_finishers', ascending=False).round(2)


if __name__ == '__main__':
    marathons = read_and_process_marathons(DATA_FILE)
    if marathons is None:
        raise SystemExit(f'Data file not found: {DATA_FILE}')

    os.makedirs(REPLICATION_DIR, exist_ok=True)
    pd.set_option('display.width', 200)

    for col in [REGION, COUNTRY]:
        long_results = compute_group_excess_mass(marathons, col)
        long_results.round(3).to_csv(
            os.path.join(REPLICATION_DIR, f'excess_mass_by_{col}_long.csv'))

        table = make_excess_mass_table(marathons, col)
        table.to_csv(os.path.join(REPLICATION_DIR,
                                  f'excess_mass_by_{col}.csv'))
        print(f'\nExcess mass by {col} (min {MIN_FINISHERS} finishers)')
        print(table.to_string())
