"""Display readiness, separate from the account gate used for report transport."""
import logging

from battle_conquest.report_sender import at_garage

_logger = logging.getLogger('battle_conquest.quest_garage')
_said_unavailable = False


def garage_ready():
    if not at_garage():
        return False
    try:
        from helpers import dependency
        from skeletons.gui.shared.utils import IHangarSpace
        from gui.Scaleform.Waiting import Waiting
        space = dependency.instance(IHangarSpace)
        return bool(space is not None and space.spaceInited and not Waiting.isVisible())
    except Exception:
        global _said_unavailable
        if not _said_unavailable:
            _said_unavailable = True
            _logger.warning('garage readiness unavailable; panel waits for the loaded hangar')
        return False
