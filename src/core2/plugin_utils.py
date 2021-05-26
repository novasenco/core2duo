# -*- coding: utf-8 -*-

from functools import wraps

def equal(hook_type, hook_arg):
    def deco(func):
        @wraps(func)
        def wrapper(*args):
            func(*args)
        # for attr in vars(func):
        #     setattr(wrapper, attr, getattr(func, attr))
        setattr(wrapper, hook_type, hook_arg)
        return wrapper
    return deco

def glob(hook_type, hook_arg):
    def deco(func):
        @wraps(func)
        def wrapper(*args):
            func(*args)
        # for attr in vars(func):
        #     setattr(wrapper, attr, getattr(func, attr))
        setattr(wrapper, f"{hook_type}_glob", hook_arg)
        return wrapper
    return deco

def regex(hook_type, hook_arg):
    def deco(func):
        @wraps(func)
        def wrapper(*args):
            func(*args)
        # for attr in vars(func):
        #     setattr(wrapper, attr, getattr(func, attr))
        setattr(wrapper, f"{hook_type}_regex", hook_arg)
        return wrapper
    return deco

def owner(owner_type="", owner_arg=True):
    def deco(func):
        @wraps(func)
        def wrapper(*args):
            func(*args)
        # for attr in vars(func):
        #     setattr(wrapper, attr, getattr(func, attr))
        setattr(wrapper, f"is_owner{'_' if owner_type else ''}{owner_type}", hook_arg)
        return wrapper
    return deco

def command(message_command):
    def deco(func):
        @wraps(func)
        def wrapper(*args):
            func(*args)
        # for attr in vars(func):
        #     setattr(wrapper, attr, getattr(func, attr))
        wrapper.command = "PRIVMSG"  # assume privmsg
        wrapper.message_command = message_command
        return wrapper
    return deco

def message(message):
    def deco(func):
        @wraps(func)
        def wrapper(*args):
            func(*args)
        # for attr in vars(func):
        #     setattr(wrapper, attr, getattr(func, attr))
        wrapper.command = "PRIVMSG"  # assume privmsg
        wrapper.message = message
        return wrapper
    return deco

def privmsg(func):
    @wraps(func)
    def wrapper(*args):
        func(*args)
    # for attr in vars(func):
    #     setattr(wrapper, attr, getattr(func, attr))
    wrapper.command = "PRIVMSG"
    return wrapper

def owner_host(func):
    @wraps(func)
    def wrapper(*args):
        func(*args)
    # for attr in vars(func):
    #     setattr(wrapper, attr, getattr(func, attr))
    wrapper.is_owner_host = True
    return wrapper
