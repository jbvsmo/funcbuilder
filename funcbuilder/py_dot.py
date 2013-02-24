# coding: utf-8
"""
Expressions Only!

Author: João Bernardo Oliveira - @jbvsmo
"""

import functools
import itertools
import re

import funcbuilder

__all__ = 'Environment', 'Function', 'Lambda', 'Class', 'var'

class UdefType:
    """ Better be undefined than none (sometimes).
    """
    __slots__ = ()
    def __repr__(self):
        return 'udef'

udef = UdefType()
var = funcbuilder.FuncBuilder()

class Repr:
    """ Represent your object like
            ClassName<some_attr, ['other', 'attr']>
        by overriding `_repr_args` with the desired attributes names.
    """
    _repr_args = ()

    def __repr__(self):
        t = type(self)
        args = ', '. join(str(getattr(self, x)) for x in t._repr_args)
        return '%s<%s>' % (t.__name__, args)


###########################################################################
#   Code Objects and iterating them
###########################################################################

class Code(Repr):
    """ Piece of code to be executed depending on `opcode` name
        The data can be Function, Condition, Loop.
        When the action is to just "update" the environment, the data
        can be anything (including var expressions).
    """
    _repr_args = 'opcode', 'data'
    
    def __init__(self, opcode, data=udef):
        self.opcode = opcode
        self.data = data

    def __iter__(self):
        yield self.opcode
        yield self.data


class CodeIter:
    def __init__(self, code):
        self.code = InsertIter(code)
        self.loop = None
    
    def __iter__(self):
        while True:
            try:
                for loop in self.loop:
                    for obj in loop:
                        yield iter(obj)

            except TypeError:
                self.loop = None

            yield next(self.code)

    def insert(self, code):
        self.code.insert(code)

    def create_loop(self, loop):
        self.loop = loop


class InsertIter:
    def __init__(self, seq):
        self.seq = iter(seq)

    def insert(self, seq):
        self.seq = itertools.chain(seq, self.seq)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.seq)

###########################################################################
#   Fixing things to allow function call evaluation
###########################################################################


def calculate(data, environ):
    while isinstance(data, funcbuilder.FuncBuilder):
        #XXX .do is broken because var_cnt is wrong sometimes
        # so `if` became `while`
        #Check: var.x + var.y * var.z
        #maybe .do could have an while loop
        #BTW this is important for when data is not FuncBuilder!
        data = data.do(environ)
    return data


def fix_self(args, kw=None):
    """
        Self cannot be an argument name because of the `set` method of
        environments... Maybe that should be fixed insted..
        In the meanwhile: renamed `self` to `$`

        `kw` is fixed in-place. `args` must be reassigned
    """

    args = tuple(x if x != 'self' else '$' for x in args)

    #If you add self as kw argument, then f**k you
    if kw is not None:
        x = kw.pop('self', udef)
        if x is not udef:
            kw['$'] = x

    return args


###########################################################################
#   Functions, Loops, Conditions
###########################################################################

class Function(Repr):
    """
        Basically a list of Code to be executed. On definition it may accept
        Loops, Conditions, bindings etc that will "only be evaluated" on function
        call.

        Functions cannot have default arguments yet.

        Be aware of the proper `var.name` syntax on code when not setting a name:

        >>> set(a = b)          # Invalid because `b` is being evaluated at definition
        >>> set(a = var.b)      # OK
        >>> set(a = var.a * 2)  # OK

        `var` is a `FuncBuilder` object and attribute lookup may clash with already
        defined attributes from the object itself. If you have an attribute with the
        same name of a builtin function or `call`, `do`, `get` and a few others, use:

        >>> var.attr('the_attr_name')
        >>> var.attr('call')

        You *cannot* make function calls or put `var` objects inside containers. These
        objects are functions and were meant to be used with only operators.

        >>> str(var)  # BAD - will convert `var` object to string
        >>> var.str   # OK - use the builtins provided as attributes

        >>> [var.x, var.y]  # BAD - functions inside container = useless
        There's actually no solution for this case right now!

        Note that execution may load data from parent enviroment (closure) but the
        execution (i.e. name binding) is *always* in the local environment!
    """
    _repr_args = 'name', 'args', 'code'
    
    def __init__(self, name, *args, unpack=None, environ=None):
        """ Unpack is a poor-man copy of the unpacking ability from Py2k
            >>> def foo(a, (b,c)):
            ...    print a, b, c

            But in this case, `b` and `c` must always be the last arguments
        """
        if unpack is not None:
            try:
                unpack = tuple(unpack)
            except TypeError:
                unpack = (unpack,)

        self.environ = self.parent = environ
        self.name = name
        self.args = fix_self(args)
        self.unpack = unpack
        self.code = []

    def __call__(self, *args, **kw):
        args = fix_self(args, kw)

        e = Environment().set(__parent__ = self.environ)
        if self.unpack is not None:
            *args, unpack_args = args
            
            lsu, lu = len(self.unpack), len(unpack_args)
            if lsu != lu:
                raise TypeError('Expected %s values to unpack, got %s' % (lsu, lu))
            
            e.set(**dict(zip(self.unpack, unpack_args)))

        la, lsa = len(args), len(self.args)
        la += len(kw)
        if lsa != la:
            raise TypeError('Expected %s arguments, got %s' % (lsa, la))

        e.set(**dict(zip(self.args, args)))
        e.set(**kw)
        
        stack = []
        code = CodeIter(self.code)
        for opc, data in code:
            if opc == 'update':
                e.set(**{k: calculate(v, e) for k, v in data.items()})
            elif opc == 'push':
                stack.append(calculate(data, e))
            elif opc == 'ret':
                return stack.pop()
            elif opc == 'condition':
                code.insert(data.code_to_exec(e))
            elif opc == 'loop':
                code.create_loop(data.block_to_exec(e))
            else:
                raise ValueError('Unknown opcode: %s' % opc)

        return None

    def call(self, *args, **kw):
        """ Semi-deprecated function to call a function and save the value in the parent.
        """
        self.environ.last = self(*args, **kw)
        return self.environ

    def set(self, **kw):
        """ Variables to be set at execution time.
            The right side can be made of expressions using `var`.
        """
        self.code.append(Code('update', kw))
        return self

    def ret(self, expr):
        """ Expression (w or w/o var) to be returned at execution time.
        """
        self.code.append(Code('push', expr))
        self.code.append(Code('ret'))
        return self

    def if_(self, expr):
        """ Condition to be evaluated at execution time. May contain any Code.
        """
        cond = Condition(expr, self)
        self.code.append(Code('condition', cond))
        return cond

    def for_(self, **kw):
        """ Loop with one variable to run at execution time. May contain any Code.
        """
        loop = Loop(kw, self)
        self.code.append(Code('loop', loop))
        return loop

    @property
    def end(self):
        """ Go back to parent if any or self.
        """
        return self.parent if self.parent is not None else self

    def __get__(self, instance, owner):
        """ Work as method just like any function object would.
        """
        if instance is None:
            return self
        return functools.partial(self, instance)


class Lambda(Function):
    """ Lambdas are functions without names. Nothing special.
    """
    _repr_args = 'args', 'code'

    def __init__(self, *args, unpack=None):
        super().__init__('<Lambda>', *args, unpack=unpack)


class Condition(Function):
    """ Depending on expressions given on `if` and `elif` blocks, will
        execute the underlying code. Fallback to the `else` block, if defined.

        This is just a function, so any function stuff can be used.
    """
    _repr_args = 'name',

    def __init__(self, expression, parent):
        super().__init__('if-elif-else')
        self.parent = parent
        self.expr_if = [expression]
        self.code_if = [[]]
        self.code_else = []
        self.code = self.code_if[0]

    def elif_(self, expr):
        """ One more expression to be evaluated in case the first one fails.
            May contain any Code and can be defined multiple times for more
            conditions.
        """
        code = []
        self.code = code
        self.code_if.append(code)
        self.expr_if.append(expr)
        return self

    @property
    def else_(self):
        """ A block to be execute when nothing evaluates to True.
            May contain any Code.
        """
        self.code = self.code_else
        return self

    def code_to_exec(self, environ):
        self.environ = environ
        for expr, code in zip(self.expr_if, self.code_if):
            if calculate(expr, environ):
                return code
        return self.code_else

    @property
    def end(self):
        self.code = [] # The block should not be executed
        return super().end


class Loop(Function):
    """
        Some code to be executed over and over until the provided iterator is exhausted.
        No support for break or continue. Yet.

        Only one variable per loop:
        >>> ...for_(x = range(10))

        This is just a function, so any function stuff can be used.

        Note that iterators provided in declaration time may only work the first time used!
    """
    def __init__(self, data, parent):
        super().__init__('for')
        self.parent = parent
        self.data = data

    def block_to_exec(self, environ):
        name, value = next(iter(self.data.items()))
        value = calculate(value, environ)
        return LoopIter(name, value, self.code)


class LoopIter:
    """ Get the next item from iterator and repeat the Loop code
    """
    def __init__(self, name, value, code):
        self.name = name
        self.iterator = iter(value)
        self.code = code

    def __iter__(self):
        return self

    def __next__(self):
        set_name = [Code('update', {self.name: next(self.iterator)})]
        return itertools.chain(set_name, self.code)


###########################################################################
#    The real_attribute functionality
###########################################################################

def real_attribute(dic, attr, value=None, do_set=False):
    """
        Set attributes in django-like keyword style to a dictionary object
        # set = some_environment.set
        >>> set(a = 1)         # dic['a'] = 1
        >>> set(_a = 1)        # dic['_a'] = 1
        >>> set(a__b = 1)      # dic['a'].b = 1
        >>> set(a__b___c = 1)  # dic['a'].b._c = 1
        >>> set(_a__b = 1)     # dic['_a'].b = 1
        >>> set(__foo__ = 1)   # dic['__foo__'] = 1

        # Would be an invalid attribute name otherwise. Same bypass of `__foo__`:
        >>> set(__f__o__o__ = 1)   # dic['__f__o__o__'] = 1
    """
    if attr == 'self':
        attr = '$'
    names = re.findall(r'\w+?(?=__|$)', attr)

    # For "__cases__", "cases", and self as "$"
    if attr == '$' or (names[0].startswith('__') and names[-1] == '__') or len(names) == 1:
        if do_set:
            dic[attr] = value  #special names will not be checked! E.g.: __init__
            return
        else:
            return dic[attr]

    obj, *names = names

    if obj == 'self':
        obj = '$'
    obj = dic[obj]

    fixed_names = []
    it = iter(names)

    for x in it:
        name = re.sub(r'^__', '', x)

        # "a___b" is parsed as ['a', '_', '__b'] and results in "a._b"
        while x == '_':
            x = next(it)
            name += re.sub(r'^__', '', x)

        fixed_names.append(name)

    *getters, setter = fixed_names

    obj_to_handle = obj
    for name in getters:
        obj_to_handle = getattr(obj_to_handle, name)

    if do_set:
        setattr(obj_to_handle, setter, value)
    else:
        return getattr(obj_to_handle, setter)


###########################################################################
#           Environments and Class Definitions
#
#   It is *not* possible to create conditions/loops inside them because
#   environments evaluate things during "declaration", unlike functions.
#
###########################################################################

class Environment(Repr):
    """ Just a fancy wrapper around a dictionary to set and get attributes with
        special syntax.

        Note there's no setattr <-> getattr relation to not mess with the dictionary
        by accident. *** Use the `set` method to assign attributes. ***

        Use `def_`, `class_` to create Function and Class objects that will be used
        until `end` is issued on them. Try indenting the body of their "code" to
        better fake the experience.

        You may also use `Function` and `Class` directly and bind the resulting
        object to a name.
    """

    _repr_args = 'd',

    def __init__(self, dic=None):
        """ Give me an environment or I shall create one for myself
        """
        self.d = {} if dic is None else dic

        # Somewhat deprecated... Still thinking of an use for it
        self.last = udef

    def __getattr__(self, name):
        """ Try to find an attribute inside the environment or its parent.
            This uses the `real_attribute` syntax
        """
        try:
            return real_attribute(self.d, name)
        except KeyError:
            parent = self.d.get('__parent__')
            if parent is not None:
                return getattr(parent, name)
            raise AttributeError(name)

    def set(self, **kw):
        """ Set attributes wit the `real_attribute` syntax.
            Use this function instead of __setattr__ to save things to the
            environment dict instead of the environment itself.
        """
        for k, v in kw.items():
            real_attribute(self.d, k, v, do_set=True)

        return self

    def def_(self, **kw):
        """ Create a Function object with parent set to self instance.
            Use the `end` attribute to go back in this instance.
        """
        if len(kw) > 1:
            raise TypeError('"fun" can have 1 kw arg only')
        name, args = next(iter(kw.items()))
        fn = Function(name, *args, environ=self)
        self.d[name] = fn
        return fn

    def class_(self, name=None, **kw):
        """ Create a Class object with parent set to self instance.
            Use the `end` attribute to go back in this instance.
        """
        if name and kw:
            raise TypeError('Supply one name only')
        if len(kw) > 1:
            raise TypeError('"fun" can have 1 kw arg only')
        if name is None and not kw:
            raise TypeError('Supply a name')

        if name:
            bases = ()
        else:
            name, bases = next(iter(kw.items()))

        return Class(name, bases, self)

    def print(self, *args, **kw):
        """ A print function that doesn't mess with the workflow by
            printing stuff.

            When there's no arguments, t uses the somewhat deprecated
            `last` attribute (i.e. the result of last function call
            with the `call` call!)
        """
        if not args:
            if self.last is udef:
                raise RuntimeError('Nothing to retrieve!')
            print(self.last, **kw)
        else:
            print(*args, **kw)
        return self



class Class(Environment):
    """ A class is just an environment that gets executed
        and becomes a *real* class after the end of definition.
        Probably the only real thing in this entire module...
    """
    def __init__(self, name, bases=(), parent=None):
        super().__init__()
        self.name = name
        self.bases = bases
        self.parent = parent

    @property
    def end(self):
        cls = type(self.name, self.bases, self.d)
        if self.parent is not None:
            self.parent.set(**{self.name: cls})
        return self.parent if self.parent is not None else cls


# Shortcut
env = Environment(globals())


# Tests!
if __name__ == '__main__':

# Simple environment with function
    e = Environment();e                  .\
                                          \
    set(a = 1)                           .\
    set(b = e.a + 1)                     .\
                                          \
    def_(foo = ('x', 'y'))               .\
       set(a = var.b)                    .\
       ret(var.x + var.a * var.y)        .\
    end                                  .\
                                          \
    set(z = e.foo(10, 16))               .\
    print('func0:', e.z)                 .\
                                          \
    foo.call(10, 16)                     .\
    print('func1:', end=' ')             .\
    print()


# Look ma no hands -- globals
    env                                  .\
                                          \
    set(a = 1)                           .\
    set(b = a + 1)                       .\
                                          \
    def_(foo = ('x', 'y'))               .\
       set(a = var.b)                    .\
       ret(var.x + var.a * var.y)        .\
    end


    print(' glob:', foo(10, 16))


# LAMBDA with unpack assignment
    data = [(1, 2), (2, 3), (-1, 4), (99, 99),
            (6, 3), (2, 9), (8, 3), (0, 0)]

    s = sorted(data, key=
        Lambda(unpack=('x', 'y'))        .
            set(a = 1)                   .
            set(z = var.x ** 2 + var.a)  .
            ret(var.y + var.z)           .
        end
    )[:-1]

    print(' lamb:', sum(sum(i) for i in s))


# IF, ELIF and ELSE clauses
    foo = Function('foo', 'x', 'y')      .\
        if_(var.x)                       .\
            ret(var.x + var.y)           .\
        elif_(var.x == None)             .\
            ret(var.y + 1)               .\
        else_                            .\
            ret(var.y)                   .\
        end                              .\
    end

    print('   if:', foo(30, 12))
    print(' elif:', foo(None, 41))
    print(' else:', foo([], 42))


# FOR loop
    bar = Function('bar', 'x')           .\
        set(w = 0)                       .\
        for_(i = var.x)                  .\
            set(w = var.w + var.i ** 2)  .\
        end                              .\
        ret(var.w + 12)                  .\
    end

    print('  for:', bar([1, 2, 3, 4]))


# CLASS support

    Environment(globals())               .\
                                          \
    class_('Foo')                        .\
        def_(__init__ = ('self', 'x'))   .\
            set(self__x = var.x)         .\
        end                              .\
                                          \
        def_(__repr__ = ('self',))       .\
            ret(var.self.x.str)          .\
        end                              .\
    end

    print('class:', Foo(42))
