
from core2.event_handler import EventHandler
from core2.message import Message, Prefix
from fnmatch import fnmatchcase as fnmatch
from typing import List, Optional, Union
import json
import logging
import pathlib
import socket
import sys
import threading
import traceback
import urllib.parse


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

def query_valid(obj, attname, comp):
    """ validate an attribute for an object

        Uses fnmatch to match glob-like patterns for all strings
        @see https://docs.python.org/3/library/fnmatch.html?highlight=fnmatch#fnmatch.fnmatch
    """
    attr = getattr(obj, attname, None)
    if attr is None:
        return False
    if type(attr) == str:
        return fnmatch(attr, comp)
    return attr == comp

# used to validate selfqueries for `Server#uri()`
VALID_SELFQUERIES = {"authority", "nick", "username", "realname", "host", "port", "ssl",
        "autoconnect", "connected", "online", "disconnected"}

# }}}


class Server():
    """
    Server object capable of connecting to an irc server, maintaining a connection by replying to
    pings, receiving and parsing messages, and sending various messages

    Each server is also capable of utilizing URIs. Note that a URI is comprised of
    `scheme:[//authority]path[?query][#fragment]`. The authority should be able to uniquely identify
    a resource. Therefore, the authority for each server is "{nick}@{host}:{port}". Although URLs
    have reserved this, it will still work well here to uniquely identify servers. Note that two
    servers with the same nick and host but with different ports are technically differenent but
    this is still invalid since a irc server must have unique nicks. Also, note that even though the
    hosts may be different, since irc is composed of a distributed series of nodes, there may be two
    servers with different hosts connected to the same server network. This means that if there
    could be a nick collision there, also.

    For these reasons, Server URIs should *not* be used to *validate* the state of servers but
    rather to find non-identical servers. The ServerManager class below takes advantage of these
    URIs inside of the `get_servers()` generator. It yields a list of servers (using globbing with
    fnmatch) to find servers matching a certain pattern.

    This server URI stuff quite experimental. We'll see how it goes...

    .. General URI schematics::

        URI = scheme:[//authority]path[?query][#fragment]

        authority = [userinfo@]host[:port]

        }}--{scheme}--[:]--.----------------------------------------------------------------,--.
                            `--[//]--.---------------------,--{host}--.-----------------,--'    |
                                      `--{userinfo}--[@]--'            `--[:]--{port}--'        |
                                                                                                |
           ,-----------------------------------------------------------------------------------'
          |
           '--{path}--.------------------,--.---------------------,--{}
                       `--[?]--{query}--'    `--[#]--{fragment}--'


    .. Specific URI used for Server::

        URI = irc://authority[?query]

        authority = nick@host:port  ; note: all fields for authority are required

        }}--{irc}--[:]--[//]--{nick}--[@]--{host}--[:]--{port}--.------------------,--{}
                                                                 `--[?]--{query}--'
    """

    def __init__(self, nick: str, host: str, port: int, *, username: str = "bot",
            realname: str = "", ssl: bool = False, autoconnect: bool = True,
            owner_name: Optional[str] = None, owner_user: Optional[str] = None,
            owner_host: Optional[str] = None) -> None:
        """ Server constructor

            :param nick: nick when connecting (sets `_pre_nick`)
            :param host: host to connect to (eg, "chat.freenode.net")
            :param port: port (eg, 6667 or 6697 for ssl)
            :param kwargs: can set username, realname, ssl, and autoconnect
            :param username: set username for bot (user in nick!user@host)
            :param realname: extra name description
            :param ssl: indicates if should connect via ssl
            :param autoconnect: indicates if should autoconnect on bot startup
        """
        self._pre_nick = nick       # before "connected", this is the nick for the server
        self._nick: Optional[str] = None  # when "connected", this is the bot's nick
        self._username = username   # username used when connecting (static after "connected")
        self._realname = realname   # realname used when connecting (static after "connected")
        self._host = host           # host (static; eg: "chat.freenode.net")
        self._port = port           # port (static; eg: 6667)
        # TODO: make this work
        self._ssl = ssl             # use ssl? (static; True/False)
        self._autoconnect = autoconnect  # autoconnect (used in ServerManager for instance)
        self._connected = False     # True when "connected"; False otherwise
        self._disconnected = False  # True when "disconnected" by server or connection closed
        self._online = False        # True when msg 004 receieved; False when "disconnected"
        self._socket: Optional[socket.socket] = None  # socket connected to `host` on `port`
        self._manager: Optional["ServerManager"] = None  # ServerManager for all servers
        self._event_handler: Optional["EventHandler"] = None  # EventHandler to process messages
        self._owner_name = owner_name
        self._owner_user = owner_user
        self._owner_host = owner_host

    @classmethod
    def from_authority(cls, authority: str) -> "Optional[Server]":
        """ create server based on authority URI

            Yes. I know. Cool. You can set all of the config based on the URI-encoded form of the server
        """
        if "@" in authority:
            nick, host = authority.split("@")
        else:
            logger.error(f"Unable to create server from invalid URI {authority!r}: Nick must be specified. Use '{{nick}}{{@host}}:{{port}}'.\n")
            return None
        if ":" in host:
            host, strport = host.split(":")
            if strport.isdigit():
                port = int(strport)
            else:
                logger.error(f"Unable to create server from invalid URI {authority!r}: Port must be an int.\n")
        else:
            logger.error(f"Unable to create server from invalid URI {authority!r}: Host must be specified. Use '{{nick}}{{@host}}:{{port}}'.\n")
        server = cls(nick, host, port)
        return server

    def uri(self, *selfqueries: str, **queries: str) -> str:
        """ get uri for server

            :param args: strings to add as queries from this server's attributes  TODO: add
            :param kwargs: dict of additional (external potentially) queries
        """
        return urllib.parse.urlunparse(("ircs" if self._ssl else "irc", self.authority, "", "",
                urllib.parse.urlencode(queries), ""))

    def __hash__(self) -> int:
        return hash(self.authority)

    def __str_(self) -> str:
        return self.uri()

    def __repr__(self) -> str:
        return f"Server.from_authority({self.authority!r})"

    def _debug(self, msg):
        msg = msg.rstrip("\r\n")
        logger.debug(f"{self.authority}: {msg}")

    def _info(self, msg):
        msg = msg.rstrip("\r\n")
        logger.info(f"{self.authority}: {msg}")

    def _warn(self, msg):
        msg = msg.rstrip("\r\n")
        logger.warning(f"{self.authority}: {msg}")

    def _error(self, msg):
        msg = msg.rstrip("\r\n")
        logger.error(f"{self.authority}: {msg}")

    def _set_connected(self, connected: bool, **kwargs) -> None:
        """ set various members when for connection and disconnection

            :param connected: indicates if currently connected or not

            :param kwargs: if "connected", use optional "online" key to determine if online;
                        if not `connected`, use optional "disconnected" key to determine if
                        disconnected

            If "connected" is True::
                - connected = True
                - disconnected = False
                - online = kwargs.get("online", False)
                - nick = ... None if not online else unchanged (if not None; else set to pre_nick)

            If NOT "connected"::
                - connected = False
                - disconnected = kwargs.get("disconnected", False)
                - online = False
                - nick = None

            .. Examples::
                self._set_connected(True)  # use when connecting
                self._set_connected(False)  # use when quitting
                self._set_connected(True, online=True)
                self._set_connected(False, disconnected=True)  # use when connecting
        """
        self._connected = connected
        self._disconnected = False if connected else kwargs.get("disconnected", False)
        self._online = False if not connected else kwargs.get("online", False)
        if not self._online:
            self._nick = None
        elif not self._nick:
            self._nick = self._pre_nick

    @property
    def authority(self) -> str:
        """ the authority to uniquely identify a server

            Use this as the authority when building a URI for the server, and also it can be used to
            uniquely identify a server since a server cannot have two clients with the same nick.

            Although, user@host:port is reserved by URLs, I just don't care.
            @see https://en.wikipedia.org/wiki/URL#Syntax
        """
        return f"{self.nick}@{self.host}:{self.port}"

    @authority.setter
    def authority(self, authority) -> None:
        """ set nick, host, port based on authority encoding

            These cannot be set if the server is connected.

            .. Example:
                `server.authority = 
        """
        if self._connected:
            self._warn("unable to change server settings while connected")
            return
        if "@" not in authority or ":" not in authority:
            self._warn("received invalid authority in setter")
            return
        self._nick, authority = authority.split("@", 1)
        self._host, self._port = authority.rsplit(":", 1)
        self._port = int(self._port)


    @property
    def nick(self) -> str:
        """ get nick

            use _nick if connected else _pre_nick
        """
        return self._nick if self._connected is None else self._pre_nick

    @nick.setter
    def nick(self, nick: str) -> None:
        """ set nick

            send NICK command if connected else set _pre_nick
        """
        if self._connected:
            self.send_nick(nick)
        else:
            self._pre_nick = nick

    @property
    def username(self) -> str:
        """ get username
        """
        return self._username

    @username.setter
    def username(self, username: str) -> None:
        """ set username

            This cannot be set if connected.
        """
        if self._connected:
            self._warn("unable to change username while connected")
            return
        self._username = username

    @property
    def realname(self):
        """ get realname
        """
        return self._realname

    @realname.setter
    def realname(self, realname: str) -> None:
        """ set realname

            This cannot be set if connected.
        """
        if self._connected:
            self._warn("unable to change realname while connected")
            return
        self._realname = realname

    @property
    def host(self) -> str:
        """ get host
        """
        return self._host

    @host.setter
    def host(self, host: str) -> None:
        """ set host

            This cannot be set if connected.
        """
        if self._connected:
            self._warn("unable to change host while connected")
            return
        self._host = host

    @property
    def port(self) -> int:
        """ get port
        """
        return self._port

    @port.setter
    def port(self, port: int) -> None:
        """ set port

            This cannot be set if connected.
        """
        if self._connected:
            self._warn("unable to change port while connected")
            return
        self._port = port

    @property
    def ssl(self) -> bool:
        """ get ssl
        """
        return self._ssl

    @ssl.setter
    def ssl(self, ssl: bool) -> None:
        """ set ssl

            This cannot be set if connected.
        """
        if self._connected:
            self._warn("unable to change ssl while connected")
            return
        self._ssl = ssl

    @property
    def autoconnect(self) -> bool:
        """ get autoconnect
        """
        return self._autoconnect

    @autoconnect.setter
    def autoconnect(self, autoconnect: bool) -> None:
        """ set autoconnect
        """
        self._autoconnect = autoconnect

    @property
    def connected(self) -> bool:
        """ get connected
        """
        return self._connected

    @connected.setter
    def connected(self, connected: bool) -> None:
        """ set connected
        """
        self._set_connected(connected)

    @property
    def online(self) -> bool:
        """ get online
        """
        return self._online

    @property
    def disconnected(self) -> bool:
        """ get disconnected
        """
        return self._disconnected

    @property
    def manager(self) -> "Optional[ServerManager]":
        """ get server manager for this server
        """
        return self._manager

    @manager.setter
    def manager(self, manager: "ServerManager") -> None:
        """ set server manager for this server
        """
        if self._manager:
            self._warn(f"already has manager")
        self._manager = manager

    @property
    def event_handler(self) -> Optional[EventHandler]:
        """ get event_handler for this server
        """
        return self._event_handler

    @event_handler.setter
    def event_handler(self, event_handler: EventHandler) -> None:
        """ set event handler for this server
        """
        if self._event_handler:
            self._warn(f"already has event handler")
        self._event_handler = event_handler

    @property
    def owner_name(self):
        return self._owner_name

    @owner_name.setter
    def owner_name(self, name: Optional[str]):
        self._owner_name = owner_name

    @property
    def owner_user(self):
        return self._owner_user

    @owner_user.setter
    def owner_user(self, user: Optional[str]):
        self._owner_user = owner_user

    @property
    def owner_host(self):
        return self._owner_host

    @owner_host.setter
    def owner_host(self, host: Optional[str]):
        self._owner_host = owner_host

    def send_raw(self, raw: str) -> None:
        """ send raw string to server
        """
        if self._connected and self._socket:
            self._debug(f"-> {raw}")
            rawbytes = raw.encode("utf-8") + b"\r\n"  # raw bytes
            # https://docs.python.org/3/howto/sockets.html#socket-howto
            totalsent = 0
            rawlen = len(rawbytes)
            while totalsent < rawlen:
                sent = self._socket.send(rawbytes[totalsent:])
                if sent == 0:
                    # socket broken
                    self._warn("connection closed")
                    self._set_connected(False, disconnected=True)
                    break
                totalsent += sent
        else:
            self._warn(f"[disconnected] -> {raw}")

    def send_msg(self, cmd: str, *params: Optional[str], prefix: Optional[str] = None) -> None:
        """ construct a message to send

            @see https://tools.ietf.org/html/rfc2812#section-2.3
        """
        msg = Message.build(cmd, *params)
        self.send_raw(msg.raw)

    def send_pass(self, pwd: str) -> None:
        """ PASS

            @see https://tools.ietf.org/html/rfc2812#section-3.1.1
        """
        self.send_msg("PASS", pwd)

    def send_nick(self, nick: str) -> None:
        """ NICK

            @see https://tools.ietf.org/html/rfc2812#section-3.1.1
        """
        self.send_msg("NICK", nick)

    def send_user(self, username: str, mode: Union[int,str], realname: str) -> None:
        """ USER

            @see https://tools.ietf.org/html/rfc2812#section-3.1.3
        """
        self.send_msg("USER", username, str(mode), "*", realname)

    def send_oper(self, name: str, pwd: str) -> None:
        """ OPER

            @see https://tools.ietf.org/html/rfc2812#section-3.1.4
        """
        self.send_msg("OPER", name, pwd)

    def send_mode(self, *params) -> None:
        """ MODE: either "UMODE" or "CMODE"
                - @see https://tools.ietf.org/html/rfc2812#section-3.1.5
                - @see https://tools.ietf.org/html/rfc2812#section-3.2.3
        """
        self.send_msg("MODE", *params)

    def send_quit(self, msg: Optional[str] = None) -> None:
        """ QUIT

            @see https://tools.ietf.org/html/rfc2812#section-3.1.7
        """
        self.send_msg("QUIT", msg)
        self._set_connected(False)

    def send_join(self, chans: str, keys: Optional[str] = None) -> None:
        """ JOIN

            @see https://tools.ietf.org/html/rfc2812#section-3.2.1
        """
        self.send_msg("JOIN", chans, keys)

    def send_part(self, chans: str, msg: Optional[str] = None) -> None:
        """ PART

            @see https://tools.ietf.org/html/rfc2812#section-3.2.2
        """
        self.send_msg("PART", chans, msg)

    def send_topic(self, chan: str, topic: Optional[str] = None) -> None:
        """ TOPIC

            @see https://tools.ietf.org/html/rfc2812#section-3.2.4
        """
        self.send_msg("TOPIC", chan, topic)

    def send_names(self, chans: Optional[str] = None, target: Optional[str] = None):
        """ NAMES

            @see https://tools.ietf.org/html/rfc2812#section-3.2.5
        """
        self.send_msg("NAMES", chans, target)

    def send_invite(self, nick, chan):
        """ INVITE

            @see https://tools.ietf.org/html/rfc2812#section-3.2.7
        """
        self.send_msg("INVITE", nick, chan)

    def send_kick(self, chans, users, comment: Optional[str] = None):
        """ KICK

            @see https://tools.ietf.org/html/rfc2812#section-3.2.8
        """
        self.send_msg("KICK", chans, users, comment)

    def send_privmsg(self, target: str, msg: str) -> None:
        """ PRIVMSG

            @see https://tools.ietf.org/html/rfc2812#section-3.3.1
        """
        self.send_msg("PRIVMSG", target, msg)

    def send_notice(self, target: str, msg: str) -> None:
        """ NOTICE

            @see https://tools.ietf.org/html/rfc2812#section-3.3.2
        """
        self.send_msg("NOTICE", target, msg)

    def send_motd(self, target: Optional[str] = None) -> None:
        """ MOTD

            @see https://tools.ietf.org/html/rfc2812#section-3.4.1
        """
        self.send_msg("MOTD", target)

    def send_lusers(self, mask: Optional[str] = None, target: Optional[str] = None):
        """ LUSERS

            @see https://tools.ietf.org/html/rfc2812#section-3.4.2
        """
        self.send_msg("LUSERS", mask, target)

    def send_version(self, target: Optional[str] = None):
        """ VERSION

            @see https://tools.ietf.org/html/rfc2812#section-3.4.3
        """
        self.send_msg("VERSION", target)

    def send_ping(self, target: str, target2: Optional[str] = None) -> None:
        """ PING

            @see https://tools.ietf.org/html/rfc2812#section-3.7.2
        """
        self.send_msg("PING", target, target2)

    def send_pong(self, target: Optional[str], target2: Optional[str] = None) -> None:
        """ PONG

            @see https://tools.ietf.org/html/rfc2812#section-3.7.3
        """
        self.send_msg("PONG", target, target2)

    def connect(self) -> None:
        """ connect to server

            @see https://tools.ietf.org/html/rfc2812#section-3.1
        """
        self._socket = socket.socket()
        try:
            self._socket.connect((self._host, self._port))
        except Exception as e:
            self._error(f"unable to connect to {self._host}:{self._port}")
            return
        self._set_connected(True)
        self._connected = True
        self._disconnected = False
        self._online = False
        self.send_nick(self._pre_nick)
        self.send_user(self._username, "*", self._realname)
        try:
            self._connect()
        except Exception as e:
            self._error(f"disconnected due to unhandled internal error: {e}")
            sys.stderr.write("-" * 80 + "\n")
            traceback.print_exc(file=sys.stderr)
            sys.stderr.write("-" * 80 + "\n")
            self._set_connected(False, disconnected=True)

    def _connect(self) -> None:
        """ try-wrapper for connect()

            try to stay connected, receive messages, process with event handler
        """
        buffer = b""
        while self._connected and self._socket:
            read = self._socket.recv(1024)
            if not read:
                # socket closed
                self._set_connected(False, disconnected=True)
                self._nick = None
                break
            buffer += read
            *blines, buffer = buffer.split(b"\r\n")
            for bline in blines:
                line = bline.decode("utf-8", "backslashreplace")
                msg = Message.from_raw(line)
                self._debug(f"<- {line}")
                if msg.command == "PING":
                    self.send_pong(msg.params[0])
                eol = buffer.find(b"\r\n")
                self._event_handler.process(self, msg)

    def disconnect(self):
        """ disconnect from server
        """
        # TODO: setup default QUIT message
        self.send_quit()

    def say(self, target: str, msg: str) -> None:
        """ same as `send_privmsg()` except also check if target not None
        """
        if target is not None:
            self.send_privmsg(target, msg)

    def me(self, target: str, msg: str) -> None:
        self.say(target, f"\x01ACTION {msg}\x01")

    def notice(self, target: str, msg: str) -> None:
        """ same as `send_notice()` except also check if target not None
        """
        if target is not None:
            self.send_notice(target, msg)


class ServerManager():
    """ Manages servers
    """

    def __init__(self, servers: List[Server] = (), plugin_dirs: List[str] = ()) -> None:
        self._servers = servers
        self._server_threads: List[threading.Thread] = []
        self._keep_alive = True
        self._plugin_dirs = [str(ROOT/"plugins")]
        self._plugin_dirs.extend(plugin_dirs)
        self._event_handler = EventHandler(self._plugin_dirs)

    def __enter__(self):
        """ context manager enter
        """
        self.start()
        return self

    def start(self):
        """
        """
        self._keep_alive = True
        self._server_threads = []
        for server in self._servers:
            server.manager = self
            server.event_handler = self._event_handler
            if server.autoconnect:
                thread = threading.Thread(target=server.connect)
                self._server_threads.append(thread)
                thread.start()

    def run(self):
        """ run all servers
        """
        server_ind = 0
        server_chans = [[] for server in self._servers]
        server_chan_inds = [-1 for server in self._servers]
        print(f"talking on server[{server_ind}]: {self._servers[server_ind].authority}")
        while self._keep_alive:
            inp = input(">>> ")
            cmd = inp.split(None, 1)
            if len(cmd) > 1:
                cmd, args = cmd[0], cmd[1]
            elif len(cmd) > 0:
                cmd, args = cmd[0], None
            else:
                continue
            cmd = cmd.lower()
            if cmd == "/exit":
                self._keep_alive = False
            elif cmd == "/select":
                num = args.split()
                if len(num) > 1 and num[1].isnumeric():
                    num = int(num[1])
                    if num < 0 or num >= len(self._servers):
                        server_ind = num
                        print(f"talking on server[{server_ind}]: {self._servers[server_ind].authority}")
                    else:
                        print(f"invalid index: {server_ind}")
            elif cmd == "/next":
                server_ind += 1
                if server_ind >= len(self._servers):
                    server_ind = 0
                print(f"talking on server[{server_ind}]: {self._servers[server_ind].authority}")
            elif cmd == "/join":
                if args:
                    chans = args.split()
                    if len(chans) == 1:
                        keys = None
                    else:
                        keys = chans[1]
                    chans = chans[0]
                    self._servers[server_ind].send_join(chans, keys)
                    chan = chans.split(",")[0]
                    if chan not in server_chans[server_ind]:
                        server_chans[server_ind].append(chan)
                        server_chan_inds[server_ind] = server_chans[server_ind].index(chan)
                        print(f"talking on channel {chan}")
            elif cmd == "/msg":
                if args:
                    msg = args.split(None, 1)
                    if len(msg) > 1:
                        self._servers[server_ind].privmsg(msg[0], msg[1])
            elif cmd == "/say":
                chanid = server_chan_inds[server_ind]
                if chanid >= 0:
                    chan = server_chans[server_ind][chanid]
                    self._servers[server_ind].send_privmsg(chan, args)
            elif cmd == "/part":
                chanid = server_chan_inds[server_ind]
                if chanid >= 0:
                    chan = server_chans[server_ind][chanid]
                    self._servers[server_ind].send_part(chan, args)
            elif cmd == "/setchan":
                if args:
                    chan = args.split()[0]
                    if chan not in server_chans[server_ind]:
                        server_chans[server_ind].append(chan)
                        server_chan_inds[server_ind] = server_chans[server_ind].index(chan)
                        print(f"talking on channel {chan}")
            else:
                self._servers[server_ind].send_raw(inp)

    def __exit__(self, typ, value, traceback):
        """ context manager exit
        """
        self.stop()

    def stop(self):
        """ close all processes

            disconnect from all connected servers; wait for all threads to finish
        """
        self._keep_alive = False
        for server in self._servers:
            if server.connected:
                server.disconnect()
        for thread in self._server_threads:
            thread.join()
        self._server_threads = []

    def get_servers(self, nick="*", user="*", port="*", matcher=None, **queries):
        """ Find servers based on glob patterns

            .. Examples::
                sm.get_server_with(online=True, host="chat.freenode.net")
        """
        for server in self._servers:
            if not fnmatch(server.authority, f"{nick}@{user}:{port}"):
                continue
            if not all(query_valid(server, query, queries[query]) for query in queries):
                continue
            if matcher and not matcher(server):
                continue
            yield server

# vim: foldmethod=marker foldmarker={{{,}}} foldlevel=0:
