import inspect

from .dispatcher import Dispatcher, MethodDispatcher

global_namespace = dict()


def dispatch(*types):
    """
    >>> @dispatch(int)
    ... def f(x):
    ...     return x + 1

    >>> @dispatch(float)
    ... def f(x):
    ...     return x - 1

    >>> f(3)
    4
    >>> f(3.0)
    2.0

    """
    namespace = global_namespace

    types = tuple(types)

    def _df(func):
        name = func.__name__

        if ismethod(func):
            dispatcher = inspect.currentframe().f_back.f_locals.get(
                name,
                MethodDispatcher(name),
            )
        else:
            if name not in namespace:
                namespace[name] = Dispatcher(name)
            dispatcher = namespace[name]

        dispatcher.add(types, func)
        return dispatcher
    return _df


def ismethod(func):
    if hasattr(inspect, "signature"):
        signature = inspect.signature(func)
        return signature.parameters.get('self', None) is not None
    else:

        spec = inspect.getfullargspec(func)
        return spec and spec.args and spec.args[0] == 'self'
