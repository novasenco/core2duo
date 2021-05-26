# core2

## Description

core2 is a bot that adheres to the [IRC
protocol](https://en.wikipedia.org/wiki/Internet_Relay_Chat) and is capable of connecting to a any
IRC network, such as [freenode](https://freenode.net/) or [rizon](https://rizon.net/). core2 has
been developed from scratch using [RFC 2812](https://tools.ietf.org/html/rfc2812), [RFC
2813](https://tools.ietf.org/html/rfc2813), and [RFC 1359](https://tools.ietf.org/html/rfc1459).
There are high level libraries for connecting to tcp servers (most notably [twisted]()). However,
the [lower-level socket
library](https://docs.python.org/3/library/socket.html?highlight=socket%20socket#socket.socket) is
used instead. This is for learning purposes and to provide flexibility.

[video demo](https://www.youtube.com/watch?v=jVYm7TzNkcg)

## Usage

```sh
python3 -m venv env  # create virtual env (only once)
source env/bin/activate  # source venv (once PER shell) [1]
pip install .  # install project (only once) [2]
core2
```

- `[1]`: on Windows, use `call env\Scripts\activate.bat`
    - in fish or csh append `.fish` or `.csh` (resp.) to `env/bin/activate`
- `[2]` for development, use `pip install -e .` to make project *editable*

## Capabilities

### multi-server

- core2 can connect to multiple IRC servers at once
    - in order to achieve this,
      [threading](https://docs.python.org/3/library/threading.html#threading.Thread) is used
    - [asyncio](https://docs.python.org/3/library/asyncio.html) and
      [trio](https://trio.readthedocs.io/en/stable/tutorial.html) were both explored, but due to
      some limitations, threading is used instead

### pong

- automatically respond to a *ping* with a *pong* to stay connected

### logging

- log events and messages to log files
    - **server** logs to logs/server.log
    - other logs also

### event handling

- when a message is received, it calls an internal **event handler**
    - the event handler calls **hook**s if they match certain requirements
      designated by the hooks' attributes, themselves.

### freeze

- used metaprogramming to freeze objects (src code in *src/core2/meta.py*)
    - this is used in *messages.py*

### plugin ecosystem

A plugin consists of multipls hooks. Each hook is specified via a function with attributes.

Due to a lack of time, I cannot create documentation for this, so an example will suffice:

```python
from core2 import plugin_utils as utils

@utils.command(".hi")  # respond ".hi" command
def reload(server, msg, umsg, cmd, re_args):
    server.say(msg.channel, "hi")  # say "hi" in origin channel (on origin server)

@utils.regex("nick", ".*taco.*")  # respond to anyone with regex /.*taco.*/ in nick
@utils.privmsg  # respond only to privmsg commands (user messages)
def taco(server, msg, umsg, cmd, re_args):
    # say "Hi, [nick]! I love tacos!" back to origin channel/server
    server.say(msg.channel, f"Hi, {msg.prefix.name}! I love tacos!")
```

#### All Decorators

- `@equal("type", "arg")`: string equality match
- `@glob("type", "*arg*")`: glob match
- `@regex("type", ".*arg\s\w+$"`: regex match
- `@owner("host")`: sender must be owner (matched by owner's host)
- `@owner_host`: same as above
- `@command(".command")`: first word in message must be ".command"
- `@message("hello there")`: entire message should be "hello there"
- `@privmsg`: the message must be a private message sent by a user

#### All Types

`"type"` can be any of the following for `@equal`, `@glob`, `@regex`:

- `"raw"`: the entire raw message from the server
    - eg, `"nick!user@host PRIVMSG #channel :hello world"`
- `"command"`: the first word of the message from the server
    - eg, `"PRIVMSG"`
- `"symbolic"`: the symbolic representation of the command for the raw message
    - eg, `"PRIVMSG"`
- `"message_command"`: 
    - eg, `".myCommand"`
- `"message"`: 
    - eg, `".myCommand and the arguments"`
- `"prefix"`: 
    - eg, `"nick!user@host"`
- `"nick"`: 
    - eg, `"nick"`
- `"user"`: 
    - eg, `"host"`
- `"host"`: 
    - eg, `"host"`
- `"serverhost"`: 
    - eg, `"chat.freenode.net"`
- `"servername"`: 
    - eg, `"core2duo@chat.freenode.net:6667"`
- `"serveruri"`: 
    - eg, `"core2duo@chat.freenode.net:6667"`


## TODO

- ☐ **cli-args**: handle command-line arguments
- ☐ **config**: parse a configuration file
- ☐ **connection**: recognize when connected to server
- ☐ **ssl/sasl**: optionally use [SSL](https://tools.ietf.org/html/rfc6101) and
  [SASL](https://tools.ietf.org/html/rfc4422)
- ☐ **autojoin**: automatically join channels specified via cli args or config after successfully
  joining server
- ☐ **autoauth**: optionally automatically authenticate after joining a server (use SASL or message
  NickServ directly)
  parsing
  functions that can be loaded by specifying their location in config or cli args
- ☐ **nlp**: *Time permitting* use [spaCy](https://spacy.io/) for natural language processing (NLP)
  to allow for more functionality in *event-functions*
    - spaCy used over NLTK since it's faster and integrates with deep learning

The *event-functions* will probably be defined on the module level and have attached attributes that
describe when they should be called (for example, when certain commands or messages are issued) Use
regex, plain text matching, and maybe NLP to determine which functions are called. Functions should
be able to be loaded and reloaded using
[spec_file_from_location](https://docs.python.org/3/library/importlib.html#importlib.util.spec_from_file_location)
and
[module_from_spec](https://docs.python.org/3/library/importlib.html#importlib.util.module_from_spec);
this is done to prevent storing things in `sys.modules` so that reloading works properly.

The utility *event-functions* will include things like commands that can be used to send flags and
commands to ChanServ, which will make working with channels easier; detect spam and attempt to kick
users; authentication, which will allow trusted users to authenticate with the bot and use
privileged commands; other useful commands for privileged users. Users will be able to add their own
scripts as well, and will be able to configure the directories that contain loadable scripts. This
means that the bot API and plugin should be well-documented and structured nicely so that people can
easily customize and add their own scripts.
