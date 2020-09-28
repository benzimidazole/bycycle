"""Compute burst features for individual cycles."""

import numpy as np
import pandas as pd

from bycycle.utils.checks import check_param
from bycycle.burst import detect_bursts_dual_threshold

###################################################################################################
###################################################################################################

def compute_burst_features(df_shape_features, df_samples, sig,
                           burst_method='cycles', burst_kwargs=None):
    """Compute burst features for each cycle.

    Parameters
    ----------
    df_shape_features : pandas.DataFrame
        Shape parameters for each cycle, determined using :func:`~.compute_shape_features`.
    df_samples : pandas.DataFrame
        Indices of cyclepoints returned from :func:`~.compute_cyclepoints`.
    sig : 1d array
        Voltage time series used for determining monotonicity.
    burst_method : string, optional, default: 'cycles'
        Method for detecting bursts.

        - 'cycles': detect bursts based on the consistency of consecutive periods & amplitudes
        - 'amp': detect bursts using an amplitude threshold

    burst_kwargs : dict, optional, default: None
        Additional arguments required for amplitude burst detection. Defined in
        :func:`~.compute_burst_fraction`, keys include:

        - ``fs`` : required for dual amplitude threshold burst detection
        - ``f_range`` : required for dual amplitude threshold burst detection
        - ``amp_threshes`` : optional, default: (1, 2)
        - ``min_n_cycles`` : optional, default: 3
        - ``filter_kwargs`` : optional, default: None

    Returns
    -------
    df_burst_features : pandas.DataFrame
        Dataframe containing burst features. Each row is one cycle. Columns:

        When cycle consistency burst detection is used (i.e. burst_method == 'cycles'):

        - ``amp_fraction`` : normalized amplitude
        - ``amp_consistency`` : difference in the rise and decay voltage within a cycle
        - ``period_consistency`` : difference between a cycle’s period and the period of the
          adjacent cycles
        - ``monotonicity`` : fraction of instantaneous voltage changes between consecutive
          samples that are positive during the rise phase and negative during the decay phase

        When dual threshold burst detection is used (i.e. burst_method == 'amp'):

        - ``burst_fraction`` : fraction of a cycle that is bursting
    """

    df_burst_features = pd.DataFrame()

    # Use feature consistency burst detection
    if burst_method == 'cycles':

        # Custom feature functions may be inserted here as long as an array is returned
        #   with length equal to the number of cycles, or rows in df_shapes
        df_burst_features['amp_fraction'] = compute_amp_fraction(df_shape_features)

        df_burst_features['amp_consistency'] = \
                compute_amp_consistency(df_shape_features, df_samples)

        df_burst_features['period_consistency'] = compute_period_consistency(df_shape_features)
        df_burst_features['monotonicity'] = compute_monotonicity(df_samples, sig)

    # Use dual threshold burst detection
    elif burst_method == 'amp':

        fs = burst_kwargs.pop('fs', None)
        f_range = burst_kwargs.pop('f_range', None)

        if fs is None or f_range is None:
            raise ValueError("'fs' and 'f_range' must be defined in 'burst_kwargs' "
                             "when 'burst_method' is 'amp'.")

        df_burst_features['burst_fraction'] = \
            compute_burst_fraction(df_samples, sig, fs, f_range, **burst_kwargs)

    else:
        raise ValueError("Unrecognized 'burst_method'.")

    return df_burst_features


def compute_amp_fraction(df_shape_features):
    """Compute the amplitude fraction of each cycle.

    Parameters
    ----------
    df_shape_features : pandas.DataFrame
        Shape features for each cycle, determined using :func:`~.compute_shape_features`.

    Returns
    -------
    amp_fract : 1d array
        The amplitude fraction of each cycle.
    """

    return df_shape_features['volt_amp'].rank() / len(df_shape_features)


def compute_amp_consistency(df_shape_features, df_samples):
    """Compute amplitude consistency for each cycle.

    Parameters
    ----------
    df_shape_features : pandas.DataFrame
        Shape features for each cycle, determined using :func:`~.compute_shape_features`.
    df_samples : pandas.DataFrame
        Indices of cyclepoints returned from :func:`~.compute_cyclepoints`.

    Returns
    -------
    amp_consist : 1d array
        The amplitude consistency of each cycle.
    """

    # Compute amplitude consistency
    cycles = len(df_shape_features)
    amp_consistency = np.ones(cycles) * np.nan
    rises = df_shape_features['volt_rise'].values
    decays = df_shape_features['volt_decay'].values

    for cyc in range(1, cycles-1):

        consist_current = np.min([rises[cyc], decays[cyc]]) / np.max([rises[cyc], decays[cyc]])

        if 'sample_peak' in df_samples.columns:
            consist_last = np.min([rises[cyc], decays[cyc-1]]) / np.max([rises[cyc], decays[cyc-1]])
            consist_next = np.min([rises[cyc+1], decays[cyc]]) / np.max([rises[cyc+1], decays[cyc]])

        else:
            consist_last = np.min([rises[cyc-1], decays[cyc]]) / np.max([rises[cyc-1], decays[cyc]])
            consist_next = np.min([rises[cyc], decays[cyc+1]]) / np.max([rises[cyc], decays[cyc+1]])

        amp_consistency[cyc] = np.min([consist_current, consist_next, consist_last])

    return amp_consistency


def compute_period_consistency(df_shape_features):
    """Compute the period consistency of each cycle.

    Parameters
    ----------
    df_shape_features : pandas.DataFrame
        Shape features for each cycle, determined using :func:`~.compute_shape_features`.

    Returns
    -------
    period_consistency : 1d array
        The period consistency of each cycle.
    """

    # Compute period consistency
    cycles = len(df_shape_features)
    period_consistency = np.ones(cycles) * np.nan
    periods = df_shape_features['period'].values

    for cyc in range(1, cycles-1):

        consist_last = np.min([periods[cyc], periods[cyc-1]]) / \
            np.max([periods[cyc], periods[cyc-1]])
        consist_next = np.min([periods[cyc+1], periods[cyc]]) / \
            np.max([periods[cyc+1], periods[cyc]])

        period_consistency[cyc] = np.min([consist_next, consist_last])

    return period_consistency


def compute_monotonicity(df_samples, sig):
    """Compute the monotonicity of each cycle.

    Parameters
    ----------
    df_samples : pandas.DataFrame
        Indices of cyclepoints returned from :func:`~.compute_cyclepoints`.
    sig : 1d array
        Time series.

    Returns
    -------
    monotonicity : 1d array
        The monotonicity of each cycle.
    """

    # Compute monotonicity
    cycles = len(df_samples)
    monotonicity = np.ones(cycles) * np.nan

    for idx, row in df_samples.iterrows():

        if 'sample_peak' in df_samples.columns:
            rise_period = sig[int(row['sample_last_trough']):int(row['sample_peak'])]
            decay_period = sig[int(row['sample_peak']):int(row['sample_next_trough'])]

        else:
            decay_period = sig[int(row['sample_last_peak']):int(row['sample_trough'])]
            rise_period = sig[int(row['sample_trough']):int(row['sample_next_peak'])]

        decay_mono = np.mean(np.diff(decay_period) < 0)
        rise_mono = np.mean(np.diff(rise_period) > 0)
        monotonicity[idx] = np.mean([decay_mono, rise_mono])

    return monotonicity


def compute_burst_fraction(df_samples, sig, fs, f_range, amp_threshes=(1, 2),
                           min_n_cycles=3, filter_kwargs=None):
    """Compute the proportion of each cycle that is bursting using a dual threshold algorithm.

    Parameters
    ----------
    df_samples : pandas.DataFrame
        Indices of cyclepoints returned from :func:`~.compute_cyclepoints`.
    sig : 1d array
        Time series.
    fs : float
        Sampling rate, Hz.
    f_range : tuple of (float, float)
        Frequency range (Hz) for oscillator of interest.
    amp_threshes : tuple (low, high), optional, default: (1, 2)
        Threshold values for determining timing of bursts.
        These values are in units of amplitude (or power, if specified) normalized to
        the median amplitude (value 1).
    min_n_cycles : int, optional, default: 3
        Minimum number of cycles to be identified as truly oscillating needed in a row in
        order for them to remain identified as truly oscillating.
    filter_kwargs : dict, optional, default: None
        Keyword arguments to :func:`~neurodsp.filt.filter.filter_signal`.

    Returns
    -------
    burst_fraction : 1d array
        The proportion of each cycle that is bursting.

    Notes
    -----
    If a cycle contains three samples and the corresponding section of `is_burst` is
    np.array([True, True, False]), the burst fraction is 0.66 for that cycle.
    """

    # Ensure arguments are within valid ranges
    check_param(fs, 'fs', (0, np.inf))
    check_param(amp_threshes[0], 'lower amp_threshes', (0, amp_threshes[1]))
    check_param(amp_threshes[1], 'upper amp_threshes', (amp_threshes[0], np.inf))

    filter_kwargs = {} if filter_kwargs is None else filter_kwargs

    # Detect bursts using the dual amplitude threshold approach
    is_burst = detect_bursts_dual_threshold(sig, fs, amp_threshes, f_range,
                                            min_n_cycles=min_n_cycles, **filter_kwargs)

    # Convert the boolean array to binary
    is_burst = is_burst.astype(int)

    # Determine cycle sides
    side_e = 'trough' if 'sample_peak' in df_samples.columns else 'peak'

    # Compute fraction of each cycle that's bursting
    burst_fraction = []
    for _, row in df_samples.iterrows():
        fraction_bursting = np.mean(is_burst[int(row['sample_last_' + side_e]):
                                             int(row['sample_next_' + side_e] + 1)])
        burst_fraction.append(fraction_bursting)

    return burst_fraction