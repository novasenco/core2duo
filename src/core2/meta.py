
from collections import OrderedDict
from typing import Any, Set

"""
some meta programming fun
"""

# create temps for Empty and NotEmpty (mandatory)
Empty = None
NotEmpty = None

class Emptiness:
    """ Convenience class used to create the one & only instance of Empty

        >>> from core2.meta import Empty, NotEmpty
        >>> assert Empty is Empty() is type(Empty)() is ~NotEmpty
    """
    def __new__(cls, *args, **kwargs): return super().__new__(cls) if Empty is None else Empty
    def __str__(self): return "Empty"
    def __repr__(self): return "Empty"
    def __eq__(self, other): return self is other
    def __ne__(self, other): return self is not other
    def __bool__(self): return False
    def __hash__(self): return hash(None) - 2
    def __call__(self, *args, **kwargs): return Empty
    def __invert__(self): return NotEmpty
    def __pos__(self): return Empty
    def __neg__(self): return NotEmpty

class NotEmptiness:
    """ Convenience class used to create the one & only instance of NotEmpty

        >>> from core2.meta import Empty, NotEmpty
        >>> assert NotEmpty == +NotEmpty(Empty) == -Empty()()()
    """
    def __new__(cls, *args, **kwargs): return super().__new__(cls) if NotEmpty is None else NotEmpty
    def __str__(self): return "NotEmpty"
    def __repr__(self): return "NotEmpty"
    def __eq__(self, other): return self is other
    def __ne__(self, other): return self is not other
    def __bool__(self): return True
    def __hash__(self): return hash(None) - 1
    def __call__(self, *args, **kwargs): return NotEmpty
    def __invert__(self): return Empty
    def __pos__(self): return NotEmpty
    def __neg__(self): return Empty


# create singleton Empty and NotEmpty (similar to None)
Empty = Emptiness()
NotEmpty = NotEmptiness()


# used to temporarily set frozen attributes during Frozen instance construction
INFANTS: Set[int] = set()


# raised when trying to set a frozen attribute
class FrozenTypeError(TypeError): pass


def frozen_setattr(self, name, val):
    if id(self) not in INFANTS:
        raise FrozenTypeError(f"cannot set {name!r} for Frozen instance {self.__class__.__name__}")
    object.__setattr__(self, name, val)


class Var():
    """ Used to construct variables for @freeze

    When a class member is set to an instance of Var during a @freeze, this instructs the freeze
    wrapper to add the variable to the instance's member. If the default is set, then it is used to
    populate the instance's member variable if either there are not enough parameters passed when
    constructing an instance or `Empty` is passed as one of the parameters.

    Note that when Var has default set to Empty and either Empty is passed as the parameter or not
    enough parameters are passed, then a TypeError will be thrown.
    """
    def __init__(self, default=Empty):
        self.default = default


def freeze(cls):
    """ meta decorator to freeze an object s.t. its instances' properties are immutable

        You can construct member variables either in the class namespace or inside __init__. This
        decorator carefully extracts all of the parameters passed to the inner wrapper, constructs
        a new object only with __new__ (__init__ is skipped temporarily), the parameters are used to
        set all class members that are an instance of Var, kwargs are then used to set some
        additional instance members, and finally __init__ is called with the remaining positional
        parameters not used by the class members.

        This means that, although it is slightly confusing, it is very flexible and more powerful
        than, for example, attrs in some respects.

        @throws TypeError if there are insufficient parameters to the decorator or __init__

        >>> from core2.meta import freeze
        >>> 
        >>> @freeze
        >>> class Foo:
        ...     foo = Var("foo default")
        ...     def __init__(self, bar="bar default"):
        ...         self.bar = bar
        ...     @property
        ...     def all(self):
        ...         return f"{self.foo} :: {self.bar}"
        ...
        >>> f = Foo("foo", "bar")
        >>> f.all
        ... 'foo :: bar'
        >>> f.foo = "not foo"
            ...
        core2.meta.FrozenTypeError: cannot set 'foo' for Frozen instance Foo
        >>> 
        >>> Foo().all
        ... 'foo default :: bar default'
    """
    clsvars = OrderedDict()
    # store all class members that are instances of Var in clsvars
    for key in vars(cls):
        val = cls.__dict__[key]
        if not isinstance(val, Var):
            continue
        clsvars[key] = val
    # since frozen, set __setattr__ to frozen_setattr
    setattr(cls, "__setattr__", frozen_setattr)
    # convert clsvars.items() to tuple for slicing
    vtups = tuple(clsvars.items())
    clsinit = cls.__init__
    def init(obj, *args, **kwargs):
        objid = id(obj)
        INFANTS.add(objid)  # temporarily disable __setattr__ raising FrozenTypeError
        empties = []  # keep track of keys that point to Empty values
        # set all member variables based on clsvars.keys()
        for key, arg in zip(clsvars, args):
            if arg is Empty:
                # Empty explicitly passed (weird but ok)
                default = clsvars[key].default  # use params's default as value
                setattr(obj, key, default)
                empties.append(key)
            else:
                setattr(obj, key,  arg)
        for key, val in vtups[len(args):]:
            default = val.default
            if default is Empty:
                # not set in args and default is Empty
                empties.append(key)
            setattr(obj, key, default)
        initdict = {}  # kwargs for __init__ (don't match any keys in classvars)
        # add all kwargs to members (throw type error if not Empty) or add to initdict
        for key, val in kwargs.items():
            if key in clsvars:
                if key in empties:
                    setattr(obj, key, val)
                    empties.remove(key)
                else:
                    raise TypeError(f"{cls.__name__}() got multiple values for argument {key!r}")
            else:
                initdict[key] = val
        if hasattr(obj, "__init__"):
            # newcls.__init__(obj, *args[len(vtups):], **initdict)
            clsinit(obj, *args[len(vtups):], **initdict)
        lempties = []  # list of keys that still point to empty values after __init__
        for key in empties:
            if getattr(obj, key, Empty) is Empty:
                lempties.append(key)
        if lempties:
            num = len(lempties)
            if num == 2:
                out = f"{lempties[0]!r} and {lempties[1]!r}"
            else:
                out = ", ".join(repr(empty) for empty in lempties)
            raise TypeError(f"{cls.__name__}() missing {num} required positional argument{'s' if num > 1 else ''}: {out}")
        for key, val in clsvars.items():
            if val is Empty:
                raise TypeError(f"Invalid number of arguments for {cls.__name__}")
        INFANTS.remove(objid)
    setattr(cls, "__init__", init)
    return cls

