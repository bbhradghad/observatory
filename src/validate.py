"""Sanity checks on data pulled from the GHO API, before it is saved.

With indicator selection now open (any WHO GHO code, not just the curated
shortlist), these checks are what stand between an arbitrary indicator code
and a broken report: they catch indicators with no usable Saudi data, and
indicators that need a dimension choice (e.g. sex, age group) before they
collapse to one row per year.
"""

import datetime

import pandas as pd

REQUIRED_COLUMNS = {"SpatialDim", "TimeDim", "NumericValue"}
MIN_YEAR = 1950
MAX_YEAR = datetime.date.today().year + 1
MIN_DISTINCT_YEARS = 2  # a trend needs at least two data points

# Dim1 values that represent an unambiguous "total" for a given breakdown
# type, so select_dimension() can pick them without asking the user.
TOTAL_DIM1_VALUES = {"SEX": "SEX_BTSX"}


class ValidationError(Exception):
    pass


def select_dimension(df: pd.DataFrame, indicator_code: str) -> pd.DataFrame:
    """If rows are broken down by Dim1 (e.g. sex, age group), narrow to a
    single breakdown - the combined/total one when there's an unambiguous
    choice (e.g. SEX_BTSX for a sex breakdown), otherwise ask the user
    interactively which breakdown to use. Returns df unchanged if there's no
    real breakdown (no Dim1 column, or only one distinct value present).
    """
    if "Dim1" not in df.columns:
        return df

    with_dim = df[df["Dim1"].notna()]
    if with_dim.empty:
        return df

    distinct = sorted(with_dim["Dim1"].unique().tolist())
    if len(distinct) <= 1:
        return df

    dim1_type = None
    if "Dim1Type" in with_dim.columns and with_dim["Dim1Type"].notna().any():
        dim1_type = with_dim["Dim1Type"].dropna().iloc[0]

    total_value = TOTAL_DIM1_VALUES.get(dim1_type)
    if total_value and total_value in distinct:
        print(f"'{indicator_code}' is broken down by {dim1_type.lower()}; using the combined total ({total_value}).")
        return df[df["Dim1"] == total_value]

    print(
        f"\n'{indicator_code}' is broken down by {dim1_type or 'a dimension'}, "
        "with no single combined total. Available breakdowns:"
    )
    for i, val in enumerate(distinct, start=1):
        print(f"  {i}. {val}")
    try:
        choice = input(f"Select a breakdown [1-{len(distinct)}]: ").strip()
    except EOFError:
        raise ValidationError("No breakdown selected (non-interactive session) - re-run interactively to choose one.")
    try:
        selected = distinct[int(choice) - 1]
    except (ValueError, IndexError):
        raise ValidationError("Invalid breakdown selection.")
    return df[df["Dim1"] == selected]


def validate(df: pd.DataFrame) -> None:
    """Raise ValidationError if the data doesn't look like a usable,
    multi-year series (the country filter is already applied by the API
    call itself, via gho_client's $filter=SpatialDim eq '<code>')."""
    if df.empty:
        raise ValidationError(
            "No data returned by the API for this indicator/country combination."
        )

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValidationError(f"Missing expected columns: {sorted(missing)}")

    years = pd.to_numeric(df["TimeDim"], errors="coerce")
    if years.isna().any():
        raise ValidationError("TimeDim contains non-numeric year values.")
    if not years.between(MIN_YEAR, MAX_YEAR).all():
        bad = sorted(years[~years.between(MIN_YEAR, MAX_YEAR)].unique())
        raise ValidationError(f"TimeDim contains implausible years: {bad}")

    values = pd.to_numeric(df["NumericValue"], errors="coerce")
    if values.isna().all():
        raise ValidationError("NumericValue column has no valid numeric data.")

    usable_years = years[values.notna()].unique()
    if len(usable_years) < MIN_DISTINCT_YEARS:
        raise ValidationError(
            f"Only {len(usable_years)} year(s) of numeric data available for "
            f"this indicator/country - need at least {MIN_DISTINCT_YEARS} to "
            "compute a trend."
        )
