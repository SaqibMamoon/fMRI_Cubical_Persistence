#!/usr/bin/env python3
#
# Analyses the variability of representations (either summary statistic
# curves or persistence images) *across* cohorts for the data set.

import argparse
import json

import matplotlib.pyplot as plt

import numpy as np
import pandas as pd

from tqdm import tqdm


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('INPUT', type=str, help='Input file')

    parser.add_argument(
        '-a', '--annotate',
        action='store_true',
        help='If set, overlays the plot with annotations.',
    )

    parser.add_argument(
        '-s', '--statistic',
        help='Summary statistic to use. If not set, defaults to assuming a '
             'persistence image data structure.',
        type=str,
        default='',
    )

    parser.add_argument(
        '-r', '--rolling',
        help='If set, uses a rolling window to smooth data.',
        type=int,
        default=0
    )

    # TODO: this should be made configurable
    parser.add_argument(
        '-d', '--drop',
        action='store_true',
        help='If set, drops measurements unrelated to the movie'
    )

    args = parser.parse_args()

    with open(args.INPUT) as f:
        data = json.load(f)

    X = []

    for subject in tqdm(sorted(data.keys()), desc='Subject'):

        # Check whether we are dealing with a proper subject, or an
        # information key in the data.
        try:
            _ = int(subject)
        except ValueError:
            continue

        # Deal with a persistence image structure, direct extraction is
        # possible.
        if not args.statistic:

            # Remove data from the relevant statistic if so desired by
            # the client. This makes sense if not all time steps are
            # relevant for the experiment.
            #
            # TODO: make extent of drop configurable
            if args.drop:
                x = data[subject][7:]
            else:
                x = data[subject]

            if args.rolling == 0:
                X.append(x)
            else:
                df = pd.DataFrame(x)
                df = df.rolling(args.rolling, axis=0, min_periods=1).mean()

                X.append(df.to_numpy())

        # Deals with a summary statistic, requires a proper selection
        # first.
        else:

            # Remove data from the relevant statistic if so desired by
            # the client. This makes sense if not all time steps are
            # relevant for the experiment.
            #
            # TODO: make extent of drop configurable
            if args.drop:
                x = data[subject][args.statistic][7:]
            else:
                x = data[subject][args.statistic]

            if args.rolling == 0:
                X.append(x)
            else:
                df = pd.Series(x)
                df = df.rolling(args.rolling, axis=0, min_periods=1).mean()

                X.append(df.to_numpy())

    # This is a tensor of shape (n, m, f) or (n, m), where $n$ represents
    # the number of subjects, $m$ the number of time steps, and $f$ the
    # number of features. In case summary statistics are being used, this
    # tensor will only be 2D because there is only a single feature.
    X = np.array(X)
    df_groups = pd.read_csv('../data/participant_groups.csv')
    cohorts = df_groups['cluster'].values

    assert len(cohorts) == X.shape[0]

    # Will become the cohort-based data frame
    df = []

    for cohort in sorted(set(cohorts)):
        cohort_mean = np.mean(X[cohorts == cohort], axis=0)

        # Have another axis to summarise, so let's do this in order to
        # obtain a scalar representation.
        #
        # Notice that we are calculating the *maximum* here; this is in
        # line with the 'infinity norm' calculation.
        if len(cohort_mean.shape) == 2:
            cohort_mean = np.max(cohort_mean, axis=-1)

        # Make sure that the cohort mean representation *over time* is
        # normalised between [0, 1] as we do not want to penalise if a
        # certain cohort has higher activation values on average.
        cohort_mean = (cohort_mean - cohort_mean.min())
        cohort_mean /= (cohort_mean.max() - cohort_mean.min())

        for t, value in enumerate(cohort_mean):
            # TODO: make the time shift configurable
            if args.drop:
                t += 7

            df.append(
                {
                    'mean': value,
                    'cohort': cohort,
                    'time': t
                }
            )

    plt.figure(figsize=(6, 3))

    df = pd.DataFrame(df)
    df.groupby('time')['mean'].agg(np.std).plot()

    print(
        df.groupby('time')['mean']
          .agg(np.std)
          .reset_index()
          .to_csv(index=False, index_label='time')
    )

    if args.annotate:
        df_annot = pd.read_excel('../data/annotations.xlsx')

        # Get the salience values; it is perfectly justified to replace NaN
        # values by zero because those salience values will not be counted.
        salience = df_annot['Boundary salience (# subs out of 22)'].values
        salience = np.nan_to_num(salience)

        # These are the detected event boundaries, according to Tristan's
        # analysis. Note that since the index has been shifted above, the
        # dropping operation does *not* have to be considered here!
        salience_indices, = np.nonzero(salience >= 7)

        for index in salience_indices:
            plt.axvline(index, ls='dashed', c='r')

    plt.tight_layout()
    plt.show()
