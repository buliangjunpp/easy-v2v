

class _AlreadyHandled(object):
    def __iter__(self):
        return self

    def next(self):
        raise StopIteration

    __next__ = next


ALREADY_HANDLED = _AlreadyHandled()


from eventlet import wsgi
wsgi.ALREADY_HANDLED = ALREADY_HANDLED

bind = '0.0.0.0:6080'
worker_class = 'eventlet'
workers = 1
timeout = 400
daemon = False

loglevel = 'info'
errorlog = '/var/log/gunicorn/error.log'
accesslog = '/var/log/gunicorn/access.log'
access_log_format = '%(p)s %(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
