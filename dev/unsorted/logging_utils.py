import logging

DEFAULT_LEVEL = logging.INFO
DEFAULT_SEP = " ~~ "
DEFAULT_FORMAT_COMPONENTS = ['%(asctime)-15s', '%(name)s', '%(levelname)s', '%(message)s']


def get_personal_logger(name, level=None, sep=None, format_components=None):
    level = level or DEFAULT_LEVEL
    sep = sep or DEFAULT_SEP
    format_components = format_components or DEFAULT_FORMAT_COMPONENTS
    import logging
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(fmt=sep.join(format_components))
        handler.setFormatter(formatter)
        # add the handlers to the logger
        logger.addHandler(handler)
    return logger
