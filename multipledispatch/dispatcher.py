import inspect
from .conflict import ordering
from .utils import expand_tuples
from .variadic import Variadic, isvariadic
import itertools as itl

def variadic_signature_matches_iter(types, full_signature):
    """Check if a set of input types matches a variadic signature."""
    sigiter = iter(full_signature)
    sig = next(sigiter)
    for typ in types:
        matches = issubclass(typ, sig)
        yield matches
        if not isvariadic(sig):
            # we're not matching a variadic argument, so move to the next
            # element in the signature
            sig = next(sigiter)
    else:
        try:
            sig = next(sigiter)
        except StopIteration:
            assert isvariadic(sig)
            yield True
        else:
            # We have signature items left over, so all of our arguments
            # haven't matched
            yield False


def variadic_signature_matches(types, full_signature):
    # No arguments always matches a variadic signature
    assert full_signature
    return all(variadic_signature_matches_iter(types, full_signature))


class Dispatcher(object):
    __slots__ = '__name__', 'name', 'funcs', '_ordering', '_cache', 'doc'

    def __init__(self, name, doc=None):
        self.name = self.__name__ = name
        self.funcs = {}
        self.doc = doc

        self._cache = {}

    def register(self, *types, **kwargs):
        """ Register different functions

        >>> f = Dispatcher('f')
        >>> @f.register(int)
        ... def inc(x): ...

        >>> @f.register(float)
        ... def dec(x): ...

        """
        def _df(func):
            self.add(types, func, **kwargs)
            return func
        return _df

    @classmethod
    def get_func_params(cls, func):
        if hasattr(inspect, "signature"):
            sig = inspect.signature(func)
            return sig.parameters.values()

    @classmethod
    def get_func_annotations(cls, func):
        params = cls.get_func_params(func)
        if params:
            Parameter = inspect.Parameter

            params = (param for param in params
                      if param.kind in
                      (Parameter.POSITIONAL_ONLY,
                       Parameter.POSITIONAL_OR_KEYWORD))

            annotations = tuple(
                param.annotation
                for param in params)

            if all(ann is not Parameter.empty for ann in annotations):
                return annotations

    def add(self, signature, func):
        """ Add new types/method pair to dispatcher

        >>> D = Dispatcher('add')
        >>> D.add((int, int), lambda x, y: x + y)
        >>> D.add((float, float), lambda x, y: x + y)
        """
        # Handle annotations
        if not signature:
            annotations = self.get_func_annotations(func)
            if annotations:
                signature = annotations

        # Handle union types
        if any(isinstance(typ, tuple) for typ in signature):
            for typs in expand_tuples(signature):
                self.add(typs, func)
            return

        new_signature = []

        for index, typ in enumerate(signature, start=1):
            if not isinstance(typ, (type, list)):
                str_sig = ', '.join(c.__name__ if isinstance(c, type)
                                    else str(c) for c in signature)
                raise TypeError("Tried to dispatch on non-type: %s\n"
                                "In signature: <%s>\n"
                                "In function: %s" %
                                (typ, str_sig, self.name))

            # handle variadic signatures
            if isinstance(typ, list):
                if index != len(signature):
                    raise TypeError(
                        'Variadic signature must be the last element'
                    )

                if len(typ) != 1:
                    raise TypeError(
                        'Variadic signature must contain exactly one element. '
                        'To use a variadic union type place the desired types '
                        'inside of a tuple, e.g., [(int, str)]'
                    )
                raise Exception(f"Dispatcher.add(sig, func) | I want to deprecate | {self = }, {sig = }, {func = }")
                new_signature.append(Variadic[typ[0]])
            else:
                new_signature.append(typ)

        self.funcs[tuple(new_signature)] = func
        self._cache.clear()

        try:
            del self._ordering
        except AttributeError:
            pass

    @property
    def ordering(self):
        try:
            return self._ordering
        except AttributeError:
            return self.reorder()

    def reorder(self):
        raise Exception(f"Dispatcher.reorder() | I want to deprecate | self = {self}")
        self._ordering = od = ordering(self.funcs)
        return od

    def __call__(self, *args, **kwargs):
        types = tuple([type(arg) for arg in args])
        try:
            func = self._cache[types]
        except KeyError:
            func = self.dispatch(*types)
            if not func:
                raise NotImplementedError(
                    'Could not find signature for %s: <%s>' %
                    (self.name, str_signature(types)))
            self._cache[types] = func
        return func(*args, **kwargs)


    def __str__(self):
        return "<dispatched %s>" % self.name
    __repr__ = __str__

    def dispatch(self, *types):
        if types in self.funcs:
            return self.funcs[types]

        try:
            return next(self.dispatch_iter(*types))
        except StopIteration:
            return None

    def dispatch_iter(self, *types):
        n = len(types)
        for signature in self.ordering:
            if len(signature) == n and all(map(issubclass, types, signature)):
                result = self.funcs[signature]
                yield result
            elif len(signature) and isvariadic(signature[-1]):
                raise Exception(f"Dispatcher.dispatch_iter(*types) | I want to deprecate | {self = }, {types = }")
                if variadic_signature_matches(types, signature):
                    result = self.funcs[signature]
                    yield result

    def __getstate__(self):
        return {'name': self.name,
                'funcs': self.funcs}

    def __setstate__(self, d):
        self.name = d['name']
        self.funcs = d['funcs']
        self._ordering = ordering(self.funcs)
        self._cache = dict()

    @property
    def __doc__(self):
        docs = ["Multiply dispatched method: %s" % self.name]

        if self.doc:
            docs.append(self.doc)

        other = []
        for sig in self.ordering[::-1]:
            func = self.funcs[sig]
            if func.__doc__:
                s = 'Inputs: <%s>\n' % str_signature(sig)
                s += '-' * len(s) + '\n'
                s += func.__doc__.strip()
                docs.append(s)
            else:
                other.append(str_signature(sig))

        if other:
            docs.append('Other signatures:\n    ' + '\n    '.join(other))

        return '\n\n'.join(docs)

    def _help(self, *args):
        return self.dispatch(*map(type, args)).__doc__

    def help(self, *args, **kwargs):
        """ Print docstring for the function corresponding to inputs """
        print(self._help(*args))

    def _source(self, *args):
        func = self.dispatch(*map(type, args))
        if not func:
            raise TypeError("No function found")
        return source(func)

    def source(self, *args, **kwargs):
        """ Print source code for the function corresponding to inputs """
        print(self._source(*args))


def source(func):
    s = 'File: %s\n\n' % inspect.getsourcefile(func)
    s = s + inspect.getsource(func)
    return s


class MethodDispatcher(Dispatcher):
    """ Dispatch methods based on type signature """
    __slots__ = ('obj', 'cls')

    @classmethod
    def get_func_params(cls, func):
        if hasattr(inspect, "signature"):
            sig = inspect.signature(func)
            return itl.islice(sig.parameters.values(), 1, None)

    def __get__(self, instance, owner):
        self.obj = instance
        self.cls = owner
        return self

    def __call__(self, *args, **kwargs):
        types = tuple([type(arg) for arg in args])
        func = self.dispatch(*types)
        if not func:
            raise NotImplementedError('Could not find signature for %s: <%s>' %
                                      (self.name, str_signature(types)))
        return func(self.obj, *args, **kwargs)


def str_signature(sig):
    return ', '.join(cls.__name__ for cls in sig)
