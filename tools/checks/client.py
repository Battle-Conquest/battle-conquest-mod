"""Registers the fake client modules the mod imports."""

import sys
import types

from checks.engine import FakeEvent
from checks.fakes import FakeBattleResultsService


def _package(name):
    module = types.ModuleType(name)
    module.__path__ = []
    sys.modules[name] = module
    return module


def _attach(parent, name, module):
    sys.modules[name] = module
    setattr(sys.modules[parent], name.rsplit('.', 1)[1], module)


def install_fake_client(bigworld):
    """Register the client modules the mod imports, and return the results service.

    Only the surface the mod actually touches, and each stand-in keeps the
    real signature: a fake that accepts anything would hide exactly the kind
    of mismatch this test exists to catch.
    """
    sys.modules['BigWorld'] = bigworld

    for name in ('gui', 'helpers', 'skeletons', 'skeletons.gui', 'messenger', 'messenger.proto'):
        _package(name)

    # Every server message reaches this event, and results_request subscribes
    # to it to hear that a battle finished. Stubbed here rather than only in
    # its own checks so that starting the mod for real goes down that path:
    # a subscription that only ever happens under a fake service channel is a
    # subscription nothing proves the mod makes.
    messenger_events = types.ModuleType('messenger.proto.events')
    messenger_events.g_messengerEvents = type('MessengerEvents', (object,), {})()
    messenger_events.g_messengerEvents.serviceChannel = type('ServiceChannel', (object,), {})()
    messenger_events.g_messengerEvents.serviceChannel.onChatMessageReceived = FakeEvent()
    _attach('messenger.proto', 'messenger.proto.events', messenger_events)

    # The client's player-state events: the sender drains when the account
    # becomes the player.
    player_events = types.ModuleType('PlayerEvents')
    player_events.g_playerEvents = type('PlayerEvents', (object,), {})()
    for name in ('onAccountShowGUI', 'onAccountBecomePlayer', 'onAvatarBecomePlayer',
                 'onAvatarBecomeNonPlayer', 'onArenaCreated'):
        setattr(player_events.g_playerEvents, name, FakeEvent())
    sys.modules['PlayerEvents'] = player_events

    results = types.ModuleType('skeletons.gui.battle_results')
    results.IBattleResultsService = type('IBattleResultsService', (object,), {})
    _attach('skeletons.gui', 'skeletons.gui.battle_results', results)

    # Keyed by interface, because handing every caller the same object hides
    # a whole class of mistake: asking for the wrong service still "works".
    services = {results.IBattleResultsService: FakeBattleResultsService()}
    dependency = types.ModuleType('helpers.dependency')
    dependency.instance = lambda interface: services[interface]
    _attach('helpers', 'helpers.dependency', dependency)

    return services[results.IBattleResultsService]
