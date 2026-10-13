"""Checks for what a patch gives back: the attribute as it was stored.

The whole hot reload rests on this. A hook that comes back as the wrong kind of
thing changes how the client calls it, which is a worse bug than the hook
itself failing.
"""

from checks.common import check


class _Base(object):
    def inherited(self):
        return 'base'


class _Holder(_Base):
    def plain(self):
        return 'plain'

    @classmethod
    def made(cls):
        return 'made'


ORIGINAL_PLAIN = _Holder.__dict__['plain']


def check_session_patches():
    from unicum.runtime.session import Session

    session = Session(0)

    def wrap(original):
        def replacement(*args, **kwargs):
            return 'wrapped ' + original(*args, **kwargs)
        return replacement

    session.patch(_Holder, 'plain', wrap)
    session.patch(_Holder, 'inherited', wrap)
    session.patch(_Holder, 'made', lambda original: classmethod(lambda cls: 'wrapped ' + original()))
    check('a patched method runs the patch', _Holder().plain() == 'wrapped plain')
    check('a patched inherited method too', _Holder().inherited() == 'wrapped base')
    check('a patched classmethod too', _Holder.made() == 'wrapped made')

    session.close()
    check('a plain method is restored to the original function', _Holder.__dict__['plain'] is ORIGINAL_PLAIN)
    check('an inherited method is left inherited, not shadowed', 'inherited' not in _Holder.__dict__)
    check('a classmethod is restored as a descriptor, not a bound method',
          isinstance(_Holder.__dict__['made'], classmethod))
    check('and it is still callable off the class', _Holder.made() == 'made')
