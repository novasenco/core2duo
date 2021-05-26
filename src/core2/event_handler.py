#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from core2.hook import Hook
from importlib import util as imp
from types import FunctionType
import logging
import pathlib


# module setup {{{

ROOT = pathlib.Path(__file__).parent

# logging {{{

LOG_FILE = ROOT/"logs/server.log"

LOG_FILE.parent.mkdir(exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

ch = logging.FileHandler(LOG_FILE)
ch.setLevel(logging.DEBUG)
fmtr = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s", "%Y-%m-%d  %H:%M:%S")
ch.setFormatter(fmtr)
logger.addHandler(ch)

# }}}

# }}}


class EventHandler:
    """
    test event handler
    """

    def __init__(self, hook_dirs) -> None:
        """ EventHandler initializer

            :param hook_dirs: {@}
        """
        self.load_hooks(hook_dirs)

    def load_hooks(self, hook_dirs=None) -> int:
        """ load_hooks

            :returns: the number of errors
        """
        if hook_dirs is None:
            hook_dirs = self._hook_dirs
        self._hook_dirs = []
        for hook_dir in hook_dirs:
            path = pathlib.Path(hook_dir)
            if not path.is_dir():
                continue
            self._hook_dirs.append(path)
        self._hooks = {}
        errors = 0
        for hook_dir in self._hook_dirs:
            for module_file in hook_dir.glob("*.py"):
                if module_file.match("__*"):
                    continue
                module_name = module_file.stem
                try:
                    spec = imp.spec_from_file_location(module_name, module_file)
                    module = imp.module_from_spec(spec)
                    spec.loader.exec_module(module)
                except Exception as e:
                    logger.error(e)
                    errors += 1
                    continue
                if getattr(module, "__no_load__", False):
                    # __no_load__=True: module does not wish to be loaded
                    continue
                if hasattr(module, "init") and isinstance(module.init, FunctionType):
                    # module has init(): call it
                    module.init()
                for attr in dir(module):
                    if attr.startswith("__") or attr == "init":
                        continue  # private or init()
                    func = getattr(module, attr)
                    if not isinstance(func, FunctionType):
                        continue  # not function type
                    if func.__module__ != module_name:
                        continue  # importted function/module
                    hook = Hook(f"{module_name}*{attr}", func)
                    if hook.match_count == 0:
                        logger.warning(f"hook {hook.name!r} has no matches; discarding")
                        errors += 1
                        continue
                    self._hooks[hook.name] = hook
                    logger.debug(f"hook {hook.name!r} successfully loaded")
        return errors

    def rm_hook(self, hook_name):
        if hook_name in self._hooks:
            del self._hooks[hook_name]
            return True
        return False

    def process(self, server, msg):
        if msg.command.symbolic == "NOTICE":
            return
        usr_msg = msg.params[-1]
        usr_msg_cmd = usr_msg.split()[0]
        for hook_name, hook in self._hooks.items():
            hook.process(server, msg, usr_msg, usr_msg_cmd)

# vim: foldmethod=marker foldmarker={{{,}}} foldlevel=0:
