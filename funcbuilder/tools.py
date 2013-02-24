"""
    Tools using metaclasses provided by funcbuilder
"""
import functools
from funcbuilder import OperatorMachinery, FuncBuilder

__all__ = 'ApplyHelper', 'use', 'make_class', 'holder'


class ApplyHelper(metaclass=OperatorMachinery):
    """ Function to work with normal objects as they were FuncBuilder objects.
        Builtin Functions are usable as arguments.
        To restore the result, just call the object with no arguments.
        
        The execution is not delayed unless used with FuncBuilder objects.
        This can be used to mock some FuncBuilder objects.
    """
    def __init__(self, op=None):
        self.operand = op

    def __call__(self, *args):
        """ Generate a new object if `data` is not empty or return the value
            held.
        """
        if callable(self.operand):
            self.operand = self.operand(*args)
        return self.operand

    def __getattr__(self, attr):
        """ Apply the FuncBuilder attribute on `self.operand`
            The same is done with the operators at the metaclass.
        """
        obj = getattr(FuncBuilder, attr)
        if not callable(obj):
            obj = getattr(FuncBuilder(), attr)
        return functools.partial(obj, self.operand)

    def __repr__(self):
        return '<%s>' % repr(self.operand)

ApplyHelper.apply_operators()


try:
    lru_cache = functools.lru_cache
except NameError:
    def lru_cache(maxsize):
        """ Dummy decorator for Py3.0 and Py3.1.
        """
        def decorator(fn):
            return fn
        return decorator


@lru_cache(maxsize=1000)
def make_class(type_x):
    """ Define a (memoized) class to hold an object keeping its properties.
        It adds __call__ method to the object.
    """
    class HolderHelper(type_x, metaclass=OperatorMachinery):
        def __call__(self, *args, **kw):
            return self.__data__(*args, **kw)
        def __repr__(self):
            return repr(self.__data__)
        def __str__(self):
            return str(self.__data__)
        def __getattr__(self, x):
            return getattr(self.__data__, x)

    def func(self, *n, oper=None):
        return oper(self.__data__, *n)
    def rfunc(self, n, oper=None):
        return oper(n, self.__data__)

    HolderHelper.apply_operators([func, rfunc])
    
    return HolderHelper


def holder(x):
    """ Wrap an object with a HolderHelper.
    """
    h = make_class(type(x))()
    h.__data__ = x
    return h
