"""Basic sanity checks on data pulled from the GHO API, before it is saved."""

import datetime

import pandas as pd

REQUIRED_COLUMNS = {"SpatialDim", "TimeDim", "NumericValue"}
MIN_YEAR = 1950
MAX_YEAR = datetime.date.today().year + 1


class ValidationError(Exception):
    pass


def validate(df: pd.DataFrame) -> None:
    """Raise ValidationError if the data doesn't look like usable GHO output."""
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
