"""Quantify the shape of oscillatory waveforms on a cycle-by-cycle basis."""

import pandas as pd

from bycycle.features.shape import compute_shape_features
from bycycle.features.burst import compute_burst_features
from bycycle.burst import detect_bursts_cycles, detect_bursts_df_amp

###################################################################################################
###################################################################################################


def compute_features(sig, fs, f_range, center_extrema='peak', burst_detection_method='cycles',
                     burst_detection_kwargs=None, find_extrema_kwargs=None,
                     hilbert_increase_n=False, return_samples=True):
    """Compute shape and burst features for each cycle.

    Parameters
    ----------
    sig : 1d array
        Voltage time series.
    fs : float
        Sampling rate, in Hz.
    f_range : tuple of (float, float)
        Frequency range for narrowband signal of interest (Hz).
    center_extrema : {'peak', 'trough'}
        The center extrema in the cycle.

        - 'peak' : cycles are defined trough-to-trough
        - 'trough' : cycles are defined peak-to-peak

    burst_detection_method : string, optional, default: 'cycles'
        Method for detecting bursts.

        - 'cycles': detect bursts based on the consistency of consecutive periods & amplitudes
        - 'amplitude': detect bursts using an amplitude threshold

    burst_detection_kwargs : dict, optional, default: None
        Keyword arguments defined in either:

        - :func:`~.detect_bursts_cycles` for consistency burst detection
          (i.e. when burst_detection_method == 'cycles')
        - :func:`~.detect_bursts_df_amp` and :func:`~.compute_burst_fraction` for dual
          amplitude threshold burst detection (i.e. when burst_detection_method == 'amplitude').

    find_extrema_kwargs : dict, optional, default: None
        Keyword arguments for function to find peaks an troughs (:func:`~.find_extrema`)
        to change filter Parameters or boundary. By default, it sets the filter length to three
        cycles of the low cutoff frequency (``f_range[0]``).
    hilbert_increase_n : bool, optional, default: False
        Corresponding kwarg for :func:`~neurodsp.timefrequency.hilbert.amp_by_time` for determining
        ``band_amp``. If true, this zero-pads the signal when computing the Fourier transform, which
        can be necessary for computing it in a reasonable amount of time.
    return_samples : bool, optional, default: True
        Returns samples indices of cyclepoints used for determining features if True.

    Returns
    -------
    df_features : pandas.DataFrame
        A dataframe containing shape and burst features for each cycle. Columns:

        - ``period`` : period of the cycle
        - ``time_decay`` : time between peak and next trough
        - ``time_rise`` : time between peak and previous trough
        - ``time_peak`` : time between rise and decay zero-crosses
        - ``time_trough`` : duration of previous trough estimated by zero-crossings
        - ``volt_decay`` : voltage change between peak and next trough
        - ``volt_rise`` : voltage change between peak and previous trough
        - ``volt_amp`` : average of rise and decay voltage
        - ``volt_peak`` : voltage at the peak
        - ``volt_trough`` : voltage at the last trough
        - ``time_rdsym`` : fraction of cycle in the rise period
        - ``time_ptsym`` : fraction of cycle in the peak period
        - ``band_amp`` : average analytic amplitude of the oscillation computed using narrowband
          filtering and the Hilbert transform. Filter length is 3 cycles of the low cutoff
          frequency. Average taken across all time points in the cycle.

        When consistency burst detection is used (i.e. burst_detection_method == 'cycles'):

        - ``amplitude_fraction`` : normalized amplitude
        - ``amplitude_consistency`` : difference in the rise and decay voltage within a cycle
        - ``period_consistency`` : difference between a cycle’s period and the period of the
          adjacent cycles
        - ``monotonicity`` : fraction of instantaneous voltage changes between consecutive
          samples that are positive during the rise phase and negative during the decay phase

        When dual threshold burst detection is used (i.e. burst_detection_method == 'amplitude'):

        - ``burst_fraction`` : fraction of a cycle that is bursting

    df_samples : pandas.DataFrame, optional, default: True
        An optionally returned dataframe containing cyclepoints for each cycle.
        Columns (listed for peak-centered cycles):

        - ``sample_peak`` : sample of 'sig' at which the peak occurs
        - ``sample_zerox_decay`` : sample of the decaying zero-crossing
        - ``sample_zerox_rise`` : sample of the rising zero-crossing
        - ``sample_last_trough`` : sample of the last trough
        - ``sample_next_trough`` : sample of the next trough

    """

    # Compute shape features for each cycle.
    df_shape_features, df_samples = \
        compute_shape_features(sig, fs, f_range, center_extrema=center_extrema,
                               find_extrema_kwargs=find_extrema_kwargs,
                               hilbert_increase_n=hilbert_increase_n)

    # Ensure required dual thresh kwargs are set for calculating amplitude consistency features
    if burst_detection_method == 'amplitude':

        dual_threshold_kwargs = {}
        dual_threshold_kwargs['fs'] = fs
        dual_threshold_kwargs['f_range'] = f_range
        dual_threshold_kwargs['amp_threshes'] = burst_detection_kwargs.pop('amp_threshes', (1, 2))
        dual_threshold_kwargs['filter_kwargs'] = burst_detection_kwargs.pop('filter_kwargs', None)
        dual_threshold_kwargs['n_cycles_min'] = burst_detection_kwargs['n_cycles_min']  if \
            'n_cycles_min' in burst_detection_kwargs else 3

    else:

        dual_threshold_kwargs = None

    # Compute burst features for each cycle.
    df_burst_features = compute_burst_features(df_shape_features, df_samples, sig,
                                               dual_threshold_kwargs=dual_threshold_kwargs)

    # Concatenate shape and burst features
    df_features = pd.concat((df_shape_features, df_burst_features), axis=1)

    # Allow argument unpacking
    burst_detection_kwargs = {} if not isinstance(burst_detection_kwargs, dict) else \
        burst_detection_kwargs

    # Define whether or not each cycle is part of a burst
    if burst_detection_method == 'cycles':
        df_features = detect_bursts_cycles(df_features, **burst_detection_kwargs)
    elif burst_detection_method == 'amplitude':
        df_features = detect_bursts_df_amp(df_features, **burst_detection_kwargs)
    else:
        raise ValueError('Invalid argument for "burst_detection_method".'
                         'Either "cycles" or "amplitude" must be specified."')

    if return_samples:
        return df_features, df_samples

    return df_features
