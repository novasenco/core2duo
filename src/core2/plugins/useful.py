# -*- coding: utf-8 -*-

from core2 import plugin_utils as utils
import pathlib
from subprocess import getoutput
import re

RE_EMPTY_LINE = re.compile(r'^\s*(#.*)?#')

@utils.command(".code")
def code(server, msg, umsg, cmd, re_args):
    sloc = 0
    pyfs = 0
    for fname in pathlib.Path(__file__).parent.parent.glob("**/*.py"):
        cloc = 0
        with open(str(fname), "r") as f:
            for line in f:
                if re.match(RE_EMPTY_LINE, line):
                    continue
                cloc += 1
        sloc += cloc
        if cloc > 0:
            pyfs += 1
    server.say(msg.channel, f"I am located at {getoutput('git ls-remote --get-url origin').rstrip('.git')}, and I contain {sloc} lines of code in {pyfs} python files")


@utils.owner_host
@utils.command("hi,")
def hi_master(server, msg, umsg, cmd, re_args):
    if umsg.split()[1] == server.nick:
        server.say(msg.channel, f"Hello, master {msg.prefix.name}")
