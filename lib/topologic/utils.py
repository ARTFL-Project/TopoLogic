#!/usr/bin/env python3


def max_year_normalizer(max_year, interval):
    """Round year up"""
    if interval == 1:
        return max_year
    if interval == 10:
        max_year = int(f"{str(max_year)[:-2]}{int(str(max_year)[-2])+1}0")
    elif interval == 25:
        max_year_in_century = int(str(max_year)[-2:])
        if max_year_in_century <= 25:
            max_year = int(f"{str(max_year)[:-2]}25")
        elif max_year_in_century > 25 and max_year_in_century <= 50:
            max_year = int(f"{str(max_year)[:-2]}50")
        elif max_year_in_century > 50 and max_year_in_century < 75:
            max_year = int(f"{str(max_year)[:-2]}75")
        else:
            max_year = int(f"{str(max_year)[:-3]}{int(str(max_year)[-3])+1}00")
    elif interval == 50:
        max_tens = int(str(max_year)[-2])
        if max_tens < 5:
            max_year = int(f"{str(max_year)[:-2]}50")
        else:
            if max_year < 100:
                max_year = 100
            else:
                max_year = int(f"{str(max_year)[:-3]}{int(str(max_year)[-3])+1}00")
    elif interval == 100:
        if max_year <= 100:
            max_year = 100
        else:
            max_year = int(f"{str(max_year)[:-3]}{int(str(max_year)[-3])+1}00")
    return max_year


def year_normalizer(year, interval):
    """Round year down"""
    if interval == 1:
        return year
    if interval == 10:
        year = int(f"{str(year)[:-1]}0")
    elif interval == 25:
        year_in_century = int(str(year)[-2:])
        if year_in_century < 25:
            year = int(f"{str(year)[:-2]}00")
        elif year_in_century >= 25 and year_in_century < 50:
            year = int(f"{str(year)[:-2]}25")
        elif year_in_century >= 50 and year_in_century < 75:
            year = int(f"{str(year)[:-2]}50")
        else:
            year = int(f"{str(year)[:-2]}75")
    elif interval == 50:
        tens = int(str(year)[-2])
        if tens < 5:
            year = int(f"{str(year)[:-2]}00")
        else:
            year = int(f"{str(year)[:-2]}50")
    elif interval == 100:
        year = int(f"{str(year)[:-2]}00")
    return year
