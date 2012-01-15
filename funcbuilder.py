"""
    Function generator with operator calls
    Author: João Bernardo Oliveira - @jbvsmo

    License: BSD
    
    Python 3.0+ only.

[Tests]

Basic Operations
    >>> g = f + 1
    >>> g(10)
    11
    >>> (f ** 2 - 1)(10)
    99
    >>> g = -f + 3
    >>> g
    <var ['neg', ('add', 3)]>
    >>> g(5)
    -2
    >>> g += 1
    >>> g(5)
    -1

Extended Call
    >>> g = f + f
    >>> g(2)(2)
    4
    >>> g(2, 2)
    4
    >>> g.do(2)
    4
    >>> sorted([5,-4,3,-2,1], key=f**2)
    [1, -2, 3, -4, 5]
    >>> sorted([5,-4,3,-2,1], key=(f*f).do)
    [1, -2, 3, -4, 5]

Get item
    >>> sorted(zip([1,2,3],[3,2,1]), key=f[1])
    [(3, 1), (2, 2), (1, 3)]
    >>> sorted(zip([1,2,3],[3,2,1]), key=f.get(1))
    [(3, 1), (2, 2), (1, 3)]
    >>> sorted(zip([3,2,1],[1,1,1]), key=f.get(1,0))
    [(1, 1), (2, 1), (3, 1)]

Get attribute
    >>> g = f.real  #atrributes not already used in the class
    >>> g(5 + 3j)
    5.0
    >>> g = f.attr('imag')
    >>> g(8 + 2j)
    2.0

Call Method
    >>> g = (f * 2).call('strip')
    >>> g(' a ')
    'a  a'
    >>> g = f.call('sort', reverse=True)
    >>> x = [1, 2, 3]
    >>> g(x)
    >>> x 
    [3, 2, 1]

"""

__author__ = 'João Bernardo Oliveira'
__version__ = '1.3.8'
__all__ = ['FuncBuilder', 'f']

import operator
import itertools as it
import functools

operator.pow = pow
if 'callable' not in globals():
     def callable(x):
         return hasattr('__call__', x)

def function(f, make_lambda=True):
    """ Decorate methods from FuncBuilder to return a new FuncBuilder instance
        Methods must return [function, operation]
    """
    def FuncBuilderDecorator(self, *args, **kw):
        out, op = f(self, *args, **kw)
        out_fnc = (lambda x: out(self(x))) if make_lambda else out
        return type(self)(out_fnc, op, self)

    functools.update_wrapper(FuncBuilderDecorator, f)
    return FuncBuilderDecorator

def function_final(f):
    """ Avoid creation of extra lambda object if method function
        already calls `self(argument)` in it's body.
        If that's not true and this decorator is used, other
        function calls are lost!
    """
    return function(f, False)


def function_replacement(f):
    """ Apply builtin functions to FuncBuilder object
        as property. Those can be daisy-chained to produce
        straigth forward function calls:
        >>> g = f.str.call('strip').float.int ** -1
        >>> g('  5.001e2  ')
        0.002
    """
    func = lambda self: (lambda x: f(self(x)), f.__name__)
    return property(function_final(func))


class MetaFuncBuilder(type):
    """ Add customized operators to class
        upon initialization
    """
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        attr = '__{0}{1}__'

        #add any operator found on operator module
        for op in (x for x in dir(operator) if not x.startswith('__')):
            oper = getattr(operator, op)
            op = op.rstrip('_') #special case for keywords: and_, or_

            def func(self, *n, oper=oper):
                """ Wrapper to handle unary, binary or n-ary operations
                    If second other operands are FuncBuilder objects, increase
                    the var_cnt of new object.
                """
                name = oper.__name__
                if n:
                    attr = (n[0] if len(n) == 1 else n)
                obj = type(self)(lambda x: oper(self.func(x), *n),
                                 (name, attr) if n else name,
                                 self)
                if n and isinstance(n[0], type(self)):
                    obj.var_cnt += 1
                return obj

            def rfunc(self, n, *, oper=oper):
                """ Wrapper to handle only binary operations as
                    second operand. Will not work with ternary operations
                    as second operand. I.e. `pow(1, obj, 5)` won't work
                    because of limitation of starred assignment
                """
                return type(self)(lambda x: oper(n, self.func(x)),
                                  (n, oper.__name__),
                                  self)
            
            setattr(self, attr.format('', op), func)
            setattr(self, attr.format('r', op), rfunc)

        #Add attributes for functions with only one argument as properties
        for i in [abs, all, any, ascii, bin, bool, bytearray, bytes, callable,
                  chr, complex, dict, divmod, enumerate, eval, float, format,
                  frozenset, hasattr, hash, hex, id, int, iter, len, list,
                  max, min, next, oct, open, ord, print, range, repr, reversed,
                  round, set, sorted, str, sum, tuple, type, vars, zip]:
            
            setattr(self, i.__name__, function_replacement(i))
        


class FuncBuilder(metaclass=MetaFuncBuilder):
    """ Create objects supporting almost any operation
        to replace lambda functions.

        FuncBuilder objects can't be used to build functions
        inside function calls unless the function just access
        __operators__ attributes.

        abs(obj)    # <var ['abs']>
        range(obj)  # Type error

        Don't iterate a FuncBuilder object because that's really slow
        and it's a infinite iterator!
    """

    def __init__(self, func=None, op=None, parent=None):
        self.func = func if func else lambda x: x
        self.var_cnt = parent.var_cnt if parent else 1
        self.op = list(parent.op) if parent else []
        if op is not None:
            self.op.append(op)

    def __repr__(self):
        return '<var %s>' % self.op

    def __call__(self, *args):
        """ Call the inner function with the first argument, if exists
            Than call the resulting object with other arguments
            (obj + obj)(1, 2) == (obj + obj)(1)(2)
        """
        if not args:
            return self.func() #unary operators
        
        required, *args = args
        out = self.func(required)
        return out(*args) if args else out

    def do(self, arg, n=None, cycle=False):
        """ Apply function call with same argument `n` times.
            If `n` is not defined, the internal counter is used.
            If cycle is True, arg must be iterable and the values will
            be rotated `n` times.

            This method can be passed to a function expecting only one argument
            to fill more than one obj
        """
        if n is None:
            n = self.var_cnt

        if cycle:
            return self(*it.islice(it.cycle(arg), n))

        return self(*it.repeat(arg, n))

    @function
    def get(self, *args):
        """ Same as `operator.itemgetter` and a little better than
            the __getitem__ syntax because can check multiple indexes.
            obj[1] == obj.get(1)
            obj.get(1,2,3)
        """
        return operator.itemgetter(*args), ('get', args)

    @function
    def attr(self, name):
        """ Same as `operator.attrgetter` and is used by default
            on __getattr__ of missing attributes.
            obj.attr('x') == obj.x
        """
        return operator.attrgetter(name), ('attr', name)
    __getattr__ = attr

    @function
    def call(self, name, *args, **kw):
        """ Used to call a method inside the object.
            obj.call('strip', '-')('--hai--') -> hai
        """
        return (operator.methodcaller(name, *args, **kw),
                ('call', '{0}{1}{2}'.format(name, args, kw if kw else '')))

    @function_final
    def count(self, arg):
        """ Return a counter of some argument inside a sequence.
        """
        return lambda x: operator.countOf(self(x), arg), ('count', arg)

    @function_final
    def has(self, arg):
        """ Check if a sequence contains an argument.
            The `in` operator must return a boolean object so it will not
            work with this class. Use  `obj.has(x)` instead of `x in obj`
        """
        return lambda x: operator.contains(self(x), arg), ('has', arg)


f = FuncBuilder()

#Run doctest from module
if __name__ == "__main__":
    import doctest
    doctest.testmod()
