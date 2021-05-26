
from core2.message import Message, Prefix, Command

def test_rfc_commands():
    """ test all commands from https://tools.ietf.org/html/rfc2812#section-3.2
    """
    m1 = Message.from_raw("JOIN #foobar")
    m2 = Message.build("JOIN", "#foobar")
    assert m1 == m2
    assert m1.prefix == Prefix()
    assert not bool(m1.prefix)
    assert m1.prefix == None
    assert m1.command == "JOIN"
    assert m1.params == ("#foobar",)
    assert m1.raw == m1.orig
    assert m2.raw == m2.orig

    m1 = Message.from_raw(":somenick!~someuser@some.host.com JOIN ##core2")
    m2 = Message.build("JOIN", "##core2", prefix=Prefix("somenick", "~someuser", "some.host.com"))
    assert m1 == m2
    assert m1.orig == m1.raw
    assert m1.command == "JOIN"
    assert m1.params == ("##core2",)
    assert m1.prefix == "somenick!~someuser@some.host.com"

    m1 = Message.from_raw(":WiZ!jto@tolsun.oulu.fi JOIN #Twilight_zone")
    assert m1.raw == m1.orig
    assert m1.command == "JOIN"
    assert m1.params == ("#Twilight_zone",)
    assert m1.prefix == "WiZ!jto@tolsun.oulu.fi"

    m1 = Message.from_raw("PART #twilight_zone")
    m2 = Message.build("PART", "#twilight_zone")
    assert m1 == m2
    assert m1.orig == m1.raw
    assert m1.command == "PART"
    assert m1.params == ("#twilight_zone",)
    assert m1.prefix == None
