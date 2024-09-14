import datetime
import pytz
import time

DEFAULT_TIMEZONE = pytz.timezone("Europe/Moscow")


def to_date(ts):
    if type(ts) == datetime.date:
        return ts
    elif type(ts) == datetime.datetime:
        return ts.date()
    elif isinstance(ts, float) and ts / 500 < time.time() < ts * 500:
        # also handle time.time()
        date = datetime.date.fromtimestamp(ts)
        # todo: check that date is reasonable?
        return date
    else:
        raise ValueError(f"Unable to convert timestamp {ts} to date")


def get_current_datetime(timezone=None):
    timezone = timezone or DEFAULT_TIMEZONE
    return datetime.datetime.now(tz=timezone)


def get_current_date(timezone=None):
    timezone = timezone or DEFAULT_TIMEZONE
    return datetime.datetime.now(tz=timezone).date()


def format_date(ts):
    return ts.strftime('%Y-%m-%d')
