import inspect
from functools import wraps


def autocast_args(you_forgot_brackets=None, fail_on_errors=True, cast_none=False):
    """
    Try to convert method arguments to the ones specified in the annotation.
    Only works with the new style annotations - in the def string, e.g.:

    def test(s: str='test'):
        ...

    you_forgot_brackets: wraps the func as if this is argumentless decorator.
    fail_on_error: in case there were errors during conversion - fail.
    # todo: how does this work with typing.Union etc?

    cast_none: whether to convert None

    # todo: cast defaults as well
    """

    def cast_arg(arg, arg_sig, func_name):
        try:
            if (arg_sig.annotation is not inspect.Parameter.empty) and (cast_none or arg is not None):
                return arg_sig.annotation(arg)
        except Exception as e:
            if fail_on_errors:
                raise TypeError(
                    f"Failed to cast argument {arg_sig.name} of funciton {func_name} "
                    f"to type {arg_sig.annotation}, error message: {e}"
                )
        return arg

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            signature = inspect.signature(func)
            casted_args = []
            args = [cast_arg(arg, arg_sig, func.__name__) for arg, arg_sig in zip(args, signature.parameters.values())]
            kwargs = {key: cast_arg(val, signature.parameters[key], func.__name__) for key, val in kwargs.items()}

            return func(*args, **kwargs)

        return wrapper

    if you_forgot_brackets is not None:
        return decorator(you_forgot_brackets)
    return decorator
