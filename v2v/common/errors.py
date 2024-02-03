class Base(Exception):
    msg = "Base class for v2v errors"

    def __str__(self):
        return self.msg.format(self=self)
