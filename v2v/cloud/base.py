import six
from abc import ABCMeta
from abc import abstractmethod


@six.add_metaclass(ABCMeta)
class BaseDriver(object):
    """Abstract class for driver

    All driver should be provided connect and disconnect method.
    """
    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def disconnect(self):
        pass