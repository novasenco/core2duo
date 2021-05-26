
from functools import wraps
from types import FunctionType


class Empty:
    """ Empty Frozen value

    if this isn't set during class instantiation, then it defaults to None in __get__

    When __set__ is called, and a Frozen value is Empty, then it is set one time. Then, it
    cannot be set again
    """


class Skip:
    """ Skip required Frozen class variables during class instantiation

    for instance, if Foo has 1 class variable and 1 mandatory parameter to __init__, you can
    use Foo(Skip, "init param") to set the mandatory init parameter
    """


class Value:
    def __init__(self, val=Empty):
        self.val = val


class Frozen():
    """ A frozen descriptor for frozen variables """

    def __init__(self, name):
        self.name = name

    def __get__(self, obj, objtype):
        if obj is None:
            return self
        val = obj.__dict__[self.name]
        if val == Empty:
            # raise AttributeError(f"{objtype.__name__!r} object has unset Frozen attribute {self.name!r}")
            # print(f"{objtype.__name__!r} object has unset Frozen attribute {self.name!r}")
            pass
        # Note: returns `Empty` when object is not initialized
        return val

    def __set__(self, obj, val):
        if obj.__dict__[self.name] is Empty:
            obj.__dict__[self.name] = val
            return
        # raise TypeError(f"Frozen {obj.__class__.__name__!r} object does not support item assigment for {self.name!r}")
        # print(f"Frozen {obj.__class__.__name__!r} object does not support item assigment for {self.name!r}")
        # silently handle attempting to set frozen attribute?

    def __set_name__(self, objtype, name):
        self.name = name

    def __delete__(self, obj):
        # silently ignore member deletion
        pass

def freeze(cls):
    """ meta class wrapper to freeze class variables as member variables of each instance

    eg::
        @freeze
        class Foo():
            foo1: int  # frozen
            foo2: str  # frozen
            def __init__(self, fooinit1, fooinit2):
                self.fooinit1 = fooinit1  # not frozen
                self.fooinit2 = fooinit2  # not frozen

        f = Foo("foo one", "foo two", "foo init1", "foo init2")
        g = Foo(Skip, Skip, None, None)
    """
    keys = []
    vals = []
    # store all all properties that don't start with "_" and are not @property's
    # then, set each to Frozen descriptor
    for key, val in vars(cls).items():
        if (key[:1] == "_" or isinstance(val, property) or isinstance(val, classmethod)
                or isinstance(val, staticmethod) or isinstance(val, FunctionType)):
            continue
        keys.append(key)
        vals.append(val)
        setattr(cls, key, Frozen(key))
    # look through all of the cls.__annotations__ and add their Frozen descriptors
    # this lets people use `foo: int` and it defaults to `Empty`
    for key, val in getattr(cls, "__annotations__", {}).items():
        if (key in keys or key[:1] == "_" or isinstance(val, property)
                or isinstance(val, classmethod) or isinstance(val, staticmethod)
                or isinstance(val, FunctionType)):
            continue
        keys.append(key)
        vals.append(Empty)
        setattr(cls, key, Frozen(key))
    @wraps(cls)
    def wrapper(*args, **kwargs):
        count = min(len(args), len(keys))  # args[count:] are the args passed to init
        init_kwargs = {}  # kwargs passed to init__
        new_kwargs = {}
        for key, val in kwargs.items():
            if key in keys:
                new_kwargs[key] = val
            else:
                init_kwargs[key] = val
        obj = cls(*args[count:], **init_kwargs)
        extras = {}
        print(keys, vals)
        for key, val in zip(keys, vals):
            if val == Skip:
                continue
            obj.__dict__[key] = val
        for key, val in zip(keys[:count], args[:count]):
            if val == Skip:
                continue
            obj.__dict__[key] = val
        for key, val in new_kwargs.items():
            if key in keys:
                obj.__dict__[key] = val
            else:
                extras[key] = val
        if hasattr(obj, "__post_init__"):
            obj.__post_init__()
        # for key, val in obj.__dict__.items():
        #     if val is Empty:
        #         print("unitialized variable:", key)
        return obj
    return wrapper

