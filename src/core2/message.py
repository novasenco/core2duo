
from core2.meta import freeze
from typing import List, Optional, Tuple, Union
import json
import logging
import pathlib
import re


""" Message and other components for messaging in irc

@see https://tools.ietf.org/html/rfc2812#section-2.3.1
"""


# module setup {{{

ROOT = pathlib.Path(__file__).parent

# logging {{{

LOG_FILE = ROOT/f"logs/{__name__}.log"
LOG_FILE.parent.mkdir(exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

ch = logging.FileHandler(LOG_FILE)
ch.setLevel(logging.DEBUG)
fmtr = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s", "%Y-%m-%d  %H:%M:%S")
ch.setFormatter(fmtr)
logger.addHandler(ch)

# }}}

# compiled regex matching multiiple spaces for splitting messages
RE_SPACE = re.compile(r" +")

# numerics
with open(ROOT/"numerics.json", "r") as f:
    NUMERICS = json.load(f)
    NUMERICS, NUMERICS_VERSION = NUMERICS["values"], NUMERICS["version"]

NUMERIC_TO_SYMBOLIC = dict((int(numeric["numeric"]), numeric["name"])
        for numeric in NUMERICS
        if not (numeric.get("obsolete", False) or numeric.get("numeric_dup", False)))

SYMBOLIC_TO_NUMERIC = dict((numeric["name"], int(numeric["numeric"]))
        for numeric in NUMERICS
        if not (numeric.get("obsolete", False) or numeric.get("name_dup", False)))

# }}}


@freeze
class Prefix:
    def __init__(self, name: Optional[str] = None, user: Optional[str] = None,
            host: Optional[str] = None, orig: Optional[str] = None) -> None:
        self.name = name
        self.user = user
        self.host = host
        if self.name:
            self.raw = ":{}{}{}".format(self.name, f"!{self.user}" if self.user else "",
                    f"@{self.host}" if self.host else "")
        else:
            self.raw = ""
        self.orig = self.raw if orig is None else orig

    @classmethod
    def from_raw(cls, raw: str) -> "Prefix":
        name = raw
        user = None
        host = None
        if "!" in name:
            name, user = name.split("!")
            if "@" in user:
                user, host = user.split("@")
        elif "@" in name:
            name, host = name.split("@")
        return cls(name, user, host, orig=raw)

    def __repr__(self) -> str:
        return f"Prefix.from_raw({self.raw!r})"

    def __str__(self) -> str:
        return self.raw

    def __bool__(self) -> bool:
        return bool(self.name) or bool(self.user) or bool(self.host)

    def __eq__(self, other) -> bool:
        if other is None:
            return self.name is None
        elif isinstance(other, Prefix):
            oprefix = other
        elif isinstance(other, str):
            oprefix = Prefix.from_raw(other)
        else:
            return False
        return self.name == oprefix.name and self.user == oprefix.user and self.host == oprefix.host


@freeze
class Command:
    def __init__(self, orig: Union[str,int]):
        self.numeric: Optional[int]
        self.symbolic: Optional[str]
        self.orig = orig
        orig = str(orig)
        if orig.isdigit():
            self.numeric = int(orig)
            self.symbolic = NUMERIC_TO_SYMBOLIC.get(self.numeric)
            self.recognized = bool(self.symbolic)
        else:
            orig = orig.upper()
            self.symbolic = orig
            self.numeric = SYMBOLIC_TO_NUMERIC.get(orig)
            self.recognized = bool(self.symbolic)
        if self.numeric:
            self.raw = f"{self.numeric:03d}"
        elif self.symbolic:
            self.raw = self.symbolic
        else:
            self.raw = orig

    def try_symbolic(self) -> str:
        return self.symbolic if self.symbolic else self.raw

    def try_numeric(self) -> str:
        return f"{self.numeric:03d}" if self.symbolic else self.raw

    def __repr__(self) -> str:
        return f"Command({self.orig!r})"

    def __str__(self) -> str:
        return self.raw

    def __bool__(self) -> bool:
        return self.recognized

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Command):
            return bool(self.numeric == other.numeric and self.symbolic == other.symbolic)
        other = str(other)
        return bool(self.symbolic and self.symbolic == other or self.numeric and str(self.numeric) == other.lstrip('0'))

    def __hash__(self) -> int:
        return hash(self.raw)


@freeze
class Message:
    """
    IRC Message

    - prefix: (optional) has {name,user,host,orig}
    - command: has {numeric,symbolic}
    - params: tuple of str

    """

    def __init__(self, command: Command, *params: Optional[str], prefix: Optional[Prefix] = None, orig: Optional[str] = None):
        self.command = command
        self.params = params
        if prefix is None:
            self.prefix = Prefix()
        else:
            self.prefix = prefix
        last = None
        if params:
            *params, last = params
        builder = [ self.prefix.raw, self.command.raw, *filter(None, params) ]
        if last:
            if last[0] == ":" or " " in last:
                last = f":{last}"
            builder.append(last)
        ignores = {None, ""}
        self.raw = " ".join(filter(lambda x: x not in ignores, builder))
        self.orig = self.raw if orig is None else orig
        if self.command.symbolic in {"PRIVMSG", "NOTICE", "JOIN"}:
            self.channel = self.params[0]
        else:
            self.channel = None

    @classmethod
    def from_raw(cls, raw: str) -> "Message":
        """ parse a raw irc message https://tools.ietf.org/html/rfc2812#section-2.3.1
        """
        prefix: Optional[Prefix]
        command: Command
        params: List[str]
        orig: str = raw
        tmpraw: str
        end: List[str]
        # ----------------------
        if raw[0] == ":":
            # first word is a prefix
            tmpraw, raw = re.split(RE_SPACE, raw[1:], 1)
            prefix = Prefix.from_raw(tmpraw)
        else:
            prefix = None
        tmpraw, *end = re.split(RE_SPACE, raw, 1)
        command = Command(tmpraw)
        params = []
        for i in range(14):
            if not end:
                break
            raw = end[0]
            if raw[0] == ":":
                params.append(raw[1:])
                end = []
                break
            param, *end = re.split(RE_SPACE, raw, 1)
            params.append(param)
        if end:
            raw = end[0]
            params.append(raw[1:] if raw[0] == ":" else raw)
        return cls(command, *params, orig=orig, prefix=prefix)

    @classmethod
    def build(cls, cmd: str, *params: Optional[str], prefix: Union[Prefix,str,None] = None) -> "Message":
        if isinstance(prefix, str):
            prefix = Prefix.from_raw(prefix)
        return cls(Command(cmd), *params, prefix=prefix)

    def __repr__(self) -> str:
        params = f", {', '.join(repr(p) for p in self.params)}" if self.params else ""
        prefix = f", prefix={self.prefix!r}" if self.prefix else ""
        orig = f", orig={self.orig!r}" if self.orig else ""
        return f"Message({self.command!r}{params}{prefix}{orig})"

    def __str__(self) -> str:
        return self.raw

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Message):
            omessage = other
        elif isinstance(other, str):
            omessage = Message.from_raw(other)
        else:
            return False
        return self.prefix == omessage.prefix and self.params == omessage.params

# vim: foldmethod=marker foldmarker={{{,}}} foldlevel=0:
