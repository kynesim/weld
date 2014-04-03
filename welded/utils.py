"""
Weld utilities
"""

class GiveUp(Exception):
    """
    Something has gone wrong - tell the user
    """
    # What to return to the user when something goes wrong.
    retval = 1

    def __init__(self, message = None, retval = 1):
        self.message = message
        self.retval = retval
    def __str__(self):
        if self.message is None:
            return ''
        else:
            return self.message

    def __repr__(self):
        parts = []
        if self.message is not None:
            parts.append(repr(self.message))
        if self.retcode != 1:
            parts.append('%d'%self.retcode)
        return 'GiveUp(%s)'%(', '.join(parts))


class Bug(GiveUp):
    """
    Use this to indicate that something has gone wrong with muddle itself.

    We thus expect that a traceback will be produced.
    """
    pass



# End file.

        
