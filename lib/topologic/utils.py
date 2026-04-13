#!/usr/bin/env python3

import math


def max_year_normalizer(max_year, interval):
    """Round year up to the next interval boundary."""
    if interval == 1:
        return max_year
    return math.ceil(max_year / interval) * interval


def year_normalizer(year, interval):
    """Round year down to the previous interval boundary."""
    if interval == 1:
        return year
    return math.floor(year / interval) * interval
