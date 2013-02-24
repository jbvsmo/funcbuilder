FuncBuilder and Py_Dot environment:
===================================

* Author:    João Bernardo Oliveira ([@jbvsmo](http://twitter.com/jbvsmo))
* Version:   2.0
* GitHub:    <https://github.com/jbvsmo/funcbuilder>
* Wiki:      <https://github.com/jbvsmo/funcbuilder/wiki>


FuncBuilder
===========

FuncBuilder is a class to create functions on the fly by accessing it using
operators (always assuming `f = FuncBuilder()`)

```python
>>> g = f ** 2 - 1
>>> g(10)
99
```

The FuncBuilder objects can add inimaginable flexibily to creation of function
by the help of its methods. It is supposed to be used in places where normally
one would be using a `lambda`, like on `key` attributes of functions like `sorted`,
`min`, `max`, `groupby` and others.

The FuncBuilder class is the core of the project with some side classes and tools
to add other functionalities. Those are `FuncOperation`, `ApplyHelper`, `holder` and
some metaclasses used to create the classes.


Py_Dot
======

Py_Dot is an experimental environment to emulate the writing of classes and functions
using only the `getattr` syntax, that is, the dot operator: `foo.bar`

The idea is that a chain of function calls on attributes can create amazing structures
that would never be possible inside a python *expression*. For readability, the code should
be divided into many lines with backslash (or using parenthesis).

Code inside the `def_` or `Function` blocks must use `FuncBuilder` objects to avoid being
evaluated at definition time. The `var` object is a `FuncBuilder` instance that will provide
the local namespace for that to happen.

```python
from funcbuilder.py_dot import Environment, var

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
	                                  \
	def_(foo = ('self', 'x'))        .\
        if_(var.x)                   .\
            ret(var.x + var.self.x)  .\
        elif_(var.x == None)         .\
            ret(var.self.x + 1)      .\
        else_                        .\
            ret(var.self.x)          .\
        end                          .\
    end                              .\
	                                  \
	def_(bar = ('self', 'y'))        .\
        set(w = 0)                   .\
        for_(i = var.y)              .\
            set(w = var.w + var.i)   .\
        end                          .\
        ret(var.w + var.self.x)      .\
    end                              .\
end

# Now let's try the class!
f = Foo(42)
print(f)
print(f.foo(10))
print(f.bar([1,2,3]))
```

When setting attributes of objects, it's necessary to have a special syntax because keyword
arguments must be valid Python identifiers. So, inspired by Django, using two underscores will
be interpreted as an attribute:

`set(self__x = 10)`  =>  `self.x = 10`

Althought is seems "interesting" to write code that way, many Python statements will not be possible:

 * Cannot write `if..elif..else` blocks or `for_` loops inside `Environment` or 
   `Class` (only inside `Functions`) because of when execution happens.
 * Still not possible to have defaults for function arguments
 * Cannot put FuncBuilder objects (var.thing) inside function calls or containers!

 While the Wiki is not completed, reading the doctests of `funcbuilder.__init__` and the tests inside
 `funcbuilders.py_dot` is recomended to understand how to use the module.
 