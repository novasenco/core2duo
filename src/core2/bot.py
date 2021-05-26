#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from core2.server import Server, ServerManager
import threading


def main():
    servers = [
        Server("core2bot1", "irc.libera.chat", 6667, username="bot",
                realname="core 2 duo", ssl=False,
                owner_host={"user/nova", "gateway/tor-sasl/nova"},),
        Server("core2bot2", "irc.libera.chat", 6667, username="bot",
                realname="core 2 duo", ssl=False,
                owner_host={"user/nova", "gateway/tor-sasl/nova"},),
    ]
    with ServerManager(servers) as sm:
        sm.run()


if __name__ == "__main__":
    main()
