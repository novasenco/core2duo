# -*- coding: utf-8 -*-

from core2 import plugin_utils as utils

# def init():
#     pass

@utils.owner_host
@utils.command("!reload")
def reload(server, msg, umsg, cmd, re_args):
    errors = server._event_handler.load_hooks()
    server.notice(msg.channel, f"reloaded successfully with {errors} error{'' if errors == 1 else 's'}")

@utils.owner_host
@utils.command("!raw")
def raw(server, msg, umsg, cmd, re_args):
    server.send_raw(umsg.split(None, 1)[1])

@utils.owner_host
@utils.command("!join")
def join(server, msg, umsg, cmd, re_args):
    server.send_join(umsg.split(None, 1)[1])

@utils.owner_host
@utils.command("!part")
def part(server, msg, umsg, cmd, re_args):
    _, *chans = umsg.split(None, 1)
    if not chans:
        chans = msg.channel
    server.send_part(chans)

@utils.owner_host
@utils.command("!say")
def say(server, msg, umsg, cmd, re_args):
    _, m = umsg.split(None, 1)
    if m[0] in {"#", "&"}:
        chans, m = m.split(None, 1)
    else:
        chans = msg.channel
    server.say(chans, m)

@utils.owner_host
@utils.command("!me")
def me(server, msg, umsg, cmd, re_args):
    _, m = umsg.split(None, 1)
    if m[0] in {"#", "&"}:
        chans, m = m.split(None, 1)
    else:
        chans = msg.channel
    server.me(chans, m)

@utils.owner_host
@utils.command("!notice")
def notice(server, msg, umsg, cmd, re_args):
    _, m = umsg.split(None, 1)
    if m[0] in {"#", "&"}:
        chans, m = m.split(None, 1)
    else:
        chans = msg.channel
    server.notice(chans, m)

