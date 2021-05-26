# -*- coding: utf-8 -*-

from copy import copy
from fnmatch import fnmatchcase as fnmatch
import logging
import pathlib
import re
from threading import Thread


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


HANDLED_MATCHES = {
    "raw"            : str,  # Message.raw
    "command"        : str,  # Message.command.orig
    "numeric"        : int,  # Message.command.numeric
    "symbolic"       : str,  # Message.command.symbolic
    "message_command": str,  # Message.params[-1].split()[0]
    "message"        : str,  # Message.params[-1]
    "message_len"    : int,  # len(message.split())
    "message_len_min": int,  # min message_len
    "message_len_max": int,  # max message_len
    "prefix"         : str,  # Message.prefix.raw
    "nick"           : str,  # Message.prefix.name
    "user"           : str,  # Message.prefix.user
    "host"           : str,  # Message.prefix.host
    "serverhost"     : str,  # Server.host
    "servername"     : str,  # Server.authority
    "serveruri"      : str,  # Server.uri
}

for match_name, match_type in list(HANDLED_MATCHES.items()):
    HANDLED_MATCHES[match_name] = match_type
    if match_type == str:
        # add _glob and _regex capabilities for each match that can match a str
        HANDLED_MATCHES[f"{match_name}_glob"] = str
        HANDLED_MATCHES[f"{match_name}_regex"] = str
    # add _iter to all elements if the hook match uses lists/tuples
    HANDLED_MATCHES[f"{match_name}_iter"] = match_type

class Hook(object):
    """
    Event Hook
    """

    def __init__(self, name: str, callback: callable) -> None:
        """ Hook initializer

            :param name: {@}
            :param callback: {@}
        """
        self._name = name
        self._callback = callback
        self._thread_callback = bool(getattr(callback, 'thread', True))
        self._check_owner = (lambda v: bool(v) if v is not None else v)(getattr(callback, 'is_owner', None))
        self._check_owner_nick = (lambda v: bool(v) if v is not None else v)(getattr(callback, 'is_owner_nick', self._check_owner))
        self._check_owner_user = (lambda v: bool(v) if v is not None else v)(getattr(callback, 'is_owner_user', self._check_owner))
        self._check_owner_host = (lambda v: bool(v) if v is not None else v)(getattr(callback, 'is_owner_host', self._check_owner))
        self._matches = {
            "other": {},  # matches that don't match any keys in HANDLED_MATCHES
            "equal": {},  # matches that match any str/int type (not glob/regex)
            "glob" : {},  # matches _glob matches
            "regex": {},  # matches _regex matches
            "int"  : {},  # numeric, message_len, etc
        }

        for attr_name in vars(callback):
            match = getattr(callback, attr_name)
            if isinstance(match, (tuple, list, set)):
                # make set if tuple/list/set
                match = set(match)
            else:
                # make set with 1 str otherwise
                match = {str(match)}
            match_name = attr_name
            if attr_name not in HANDLED_MATCHES:
                match_type = "other"
            else:
                typ = HANDLED_MATCHES[attr_name]
                if typ == str:
                    if attr_name.endswith("_glob"):
                        match_name = match_name[:-5]
                        match_type = "glob"
                    elif attr_name.endswith("_regex"):
                        match_name = match_name[:-6]
                        match_type = "regex"
                    else:
                        match_type = "equal"
                elif typ == int:
                    match = set(int(m) for m in match if isinstance(m, int) or isinstance(m, str) and m.isdigit())
                    match_type = "int"
            self._matches[match_type][match_name] = match


    @property
    def match_count(self):
        return sum(len(v) for v in self._matches.values())

    @property
    def name(self):
        return self._name

    def process(self, server, msg, usr_msg, usr_msg_cmd):
        split_usr_msg = usr_msg.split()
        re_args = None
        for match_type, match in self._matches.items():
            for match_name, match_msg in match.items():
                live_msg = {
                    "raw"             : msg.command.raw,
                    "command"         : msg.command.orig,
                    "numeric"         : msg.command.numeric,
                    "symbolic"        : msg.command.symbolic,
                    "message_command" : usr_msg_cmd,
                    "message"         : usr_msg,
                    "prefix"          : msg.prefix.raw,
                    "nick"            : msg.prefix.name,
                    "user"            : msg.prefix.user,
                    "host"            : msg.prefix.host,
                    "serverhost"      : server.host,
                    "servername"      : server.authority,
                    "serveruri"       : server.uri,
                }.get(match_name)
                if match_type == "equal":
                    if live_msg not in match_msg:
                        return # failed
                elif match_type == "glob":
                    for mm in match_msg:
                        if not fnmatch(live_msg, mm):
                            return # failed
                elif match_type == "regex":
                    for mm in match_msg:
                        if not re.match(mm, live_msg):
                            return # failed
                elif match_type == "int":
                    for mm in match_msg:
                        if not live_msg.isdigit() or int(live_msg) != mm:
                            return # failed
        if self._check_owner_nick is not None:
            if bool(msg.prefix.name in server.owner_name) != lf._check_owner_nick:
                return # failed
        if self._check_owner_user is not None:
            if bool(msg.prefix.user in server.owner_user) != self._check_owner_user:
                return # failed
        if self._check_owner_host is not None:
            if bool(msg.prefix.host in server.owner_host) != self._check_owner_host:
                return # failed
        # success
        if self._thread_callback:
            Thread(target=self._callback_wrapper, args=(server, msg, usr_msg, usr_msg_cmd, re_args)).start()
        else:
            self._callback_wrapper(server, msg, usr_msg, usr_msg_cmd, re_args)

    def _callback_wrapper(self, server, msg, usr_msg, usr_msg_cmd, re_args):
        try:
            self._callback(server, msg, usr_msg, usr_msg_cmd, re_args)
        except Exception as e:
            logger.error('error in Hook ({}) function: {}'.format(self._name, e), 'error')
            server.notice(msg.channel, 'error in Hook ({}) function: {}'.format(self._name, e))

# vim: foldmethod=marker foldmarker={{{,}}} foldlevel=0:
