import os
import sys
import hashlib
import subprocess
import threading
import time
import contextlib
import traceback
import errno
import functools
import logging
import pickle
import six
import socket

from flask import request
from eventlet.green import subprocess
from oslo_log import log as logging

from collections import namedtuple, deque, OrderedDict
from contextlib import contextmanager


from v2v.common import time as v2v_time
from v2v.common.proc import pidstat
from v2v.common import excutils

LOG = logging.getLogger(__name__)


class UnlimitedSemaphore(object):
    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @property
    def balance(self):
        return 0


def get_request_info(add_log=True):
    args_data = dict(request.args)
    try:
        json_data = dict(request.json or {})
    except Exception:
        json_data = {}
    form_data = dict(request.form)
    file_data = dict(request.files)
    data = {'args_data': args_data,
            'json_data': json_data, 'form_data': form_data, 'file_data': file_data}

    if add_log:
        LOG.debug('request wiht url [%s] data [%s]' % (request.url, data))

    return data


@contextlib.contextmanager
def save_and_reraise_exception():
    """Save current exception, run some code and then re-raise."""
    type_, value, tb = sys.exc_info()
    try:
        yield
    except Exception:
        logging.error('Original exception being dropped: %s' %
                      (traceback.format_exception(type_, value, tb)))
        raise


def resp_message(data=None, success=True, code=200, message='', exception=None) -> dict:
    """
    返回值包装器

    :param exception:
    :param message:
    :param code:
    :param success: 默认True
    :param data:
    :return:
    """
    resp = {"success": success,
            "code": code,
            "message": message,
            "data": data
            }
    if exception:
        resp.update({
            'success': False,
            'code': exception.code,
            'message': exception.message
        })
    return resp


def storage_unit_switch(size: int or float, org_unit: str = ("B", "KB", "MB", "GB", "TB", "PB"),
                        target_unit: str = ("B", "KB", "MB", "GB", "TB", "PB")):
    """
    存储单位转换

    :param size: 值
    :param org_unit: 原单位
    :param target_unit: 目标单位
    :return: 精确到小数点后两位
    """
    unit = ("B", "KB", "MB", "GB")
    if org_unit not in unit or target_unit not in unit:
        raise TypeError
    else:
        org_index = unit.index(org_unit)
        target_index = unit.index(target_unit)
        result = size * (1024 ** (org_index - target_index))
        return round(result, 2)


def exec_command(cmd, timeout=60, check=False):
    """
    本地执行命令

    :param cmd:
    :param timeout: 单位s 如果指定,超时后raise TimeoutExpired
    :param check: 如果为True,当以非零状态码结束，raise CalledProcessError, 里边有错误的内容
    :return:
    """
    result = subprocess.run(cmd, shell=True, timeout=timeout, check=check, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, universal_newlines=True)
    return result.returncode, result.stdout, result.stderr


def check_cmd_output(cmd):
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        return None


def get_host_uuid():
    cmd = ['dmidecode', '-s', 'system-serial-number']
    uuid = check_cmd_output(cmd)
    if uuid is not None:
        uuid = uuid.decode().strip()
    return uuid


def time_func(func):
    def inner(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time() - start
        LOG.debug(f'函数{func.__name__}共计用时{end}s')
        return result

    return inner


def chunk_read(filepath, size=10 * 1024 * 1024):
    """
    分块读取，返回生成器

    :param filepath: 文件的绝对路径
    :param size: 每次读取文件的大小
    :return: generator
    """
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(size)
            if not chunk:
                break
            yield chunk


def hash_file(filepath, size=10 * 1024 * 1024):
    """
    计算文件MD5值

    :param filepath: 文件的绝对路径
    :param size: 每次读取文件的大小
    :returns: str 文件的MD5值
    """
    md5 = hashlib.md5()
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(size)
            if not chunk:
                break
            md5.update(chunk)

    return md5.hexdigest()


def execute(cmd, check_exit_code=True, return_stderr=False):
    LOG.debug("Running command: %s" % cmd)
    obj = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    _stdout, _stderr = (obj.communicate())
    obj.stdin.close()
    msg = "cmd stdout:%s, cmd stderr:%s" % (_stdout, _stderr)
    LOG.debug(msg)
    if obj.returncode and check_exit_code:
        raise RuntimeError(msg)

    return return_stderr and (_stdout, _stderr) or _stdout


@contextlib.contextmanager
def remove_path_on_error(path):
    """Protect code that wants to operate on PATH atomically.
    Any exception will cause PATH to be removed.
    """
    try:
        yield
    except Exception as e:
        LOG.error(f"error {str(e)}")
        with excutils.save_and_reraise_exception():
            try:
                os.unlink(path)
            except OSError as e:
                raise Exception(e)
        raise Exception(f"error {str(e)}")


def send_file(src, dst, hostname):
    """
    向从节点发送文件

    :param src: 源路径
    :param dst:
    :param hostname:
    :return:
    """
    cmd = f"scp {src} root@{hostname}:{dst}"
    exec_command(cmd, check=True)


def get_file(src, dst, hostname):
    """
    向从节点发送文件

    :param src: 下载到本地的位置
    :param dst: 目标服务器的路径
    :param hostname: 服务器的主机名
    :return:
    """
    pass


def get_file_size(path):
    """
    获取绝对路径下某文件大小， 以合适单位显式
    :param path: 必须是存在的路径
    :return: str

    """
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    index = 0
    size = os.path.getsize(path)
    while size > 1024:
        size = size / 1024
        index += 1

    return str(int(size)) + units[index]


def spawn_thread(target, *args, **kwargs):
    t = threading.Thread(target=target, args=args, kwargs=kwargs)
    if kwargs.get('_set_daemon', False):
        t.daemon = True
    t.start()
    if kwargs.get('_set_join', False):
        t.join()
    return t


_THP_STATE_PATH = '/sys/kernel/mm/transparent_hugepage/enabled'
if not os.path.exists(_THP_STATE_PATH):
    _THP_STATE_PATH = '/sys/kernel/mm/redhat_transparent_hugepage/enabled'


class IOCLASS:
    REALTIME = 1
    BEST_EFFORT = 2
    IDLE = 3


class NICENESS:
    NORMAL = 0
    HIGH = 19


def _parseMemInfo(lines):
    """
    Parse the content of ``/proc/meminfo`` as list of strings
    and return its content as a dictionary.
    """
    meminfo = {}
    for line in lines:
        var, val = line.split()[0:2]
        meminfo[var[:-1]] = int(val)
    return meminfo


def readMemInfo():
    """
    Parse ``/proc/meminfo`` and return its content as a dictionary.

    For a reason unknown to me, ``/proc/meminfo`` is sometimes
    empty when opened. If that happens, the function retries to open it
    3 times.

    :returns: a dictionary representation of ``/proc/meminfo``
    """
    # FIXME the root cause for these retries should be found and fixed
    tries = 3
    while True:
        tries -= 1
        try:
            with open('/proc/meminfo') as f:
                lines = f.readlines()
                return _parseMemInfo(lines)
        except:
            logging.warning(lines, exc_info=True)
            if tries <= 0:
                raise
            time.sleep(0.1)


def _parseCmdLine(pid):
    with open("/proc/%d/cmdline" % pid, "rb") as f:
        return tuple(f.read().split(b"\0")[:-1])


def getCmdArgs(pid):
    res = tuple()
    # Sometimes cmdline is empty even though the process is not a zombie.
    # Retrying seems to solve it.
    while len(res) == 0:
        # cmdline is empty for zombie processes
        if pidstat(pid).state in ("Z", "z"):
            return tuple()

        res = _parseCmdLine(pid)

    return res


def convertToStr(val):
    varType = type(val)
    if varType is float:
        return '%.2f' % (val)
    elif varType is int:
        return '%d' % (val)
    else:
        return val


class Canceled(BaseException):
    """
    Raised by methods decorated with @cancelpoint.

    Objects using cancellation points may like to handle this exception for
    cleaning up after cancellation.

    Inherits from BaseException so it can propagate through normal Exception
    handlers.
    """


def cancelpoint(meth):
    """
    Decorate a method so it raises Canceled exception if the methods is invoked
    after the object was canceled.

    Decorated object must implement __canceled__ method, returning truthy value
    if the object is canceled.
    """
    @functools.wraps(meth)
    def wrapper(self, *a, **kw):
        if self.__canceled__():
            raise Canceled()
        value = meth(self, *a, **kw)
        if self.__canceled__():
            raise Canceled()
        return value
    return wrapper


symbolerror = {}
for code, symbol in six.iteritems(errno.errorcode):
    symbolerror[os.strerror(code)] = symbol


class closing(object):
    """
    Context Manager that is responsible for closing the object it gets upon
    completion of the with statement.
    __exit__ will be called in the end of the with statement and in case of
    exception during the object lifetime.

    Adaptation from https://docs.python.org/2.7/library/contextlib.html
    """
    def __init__(self, obj, log="utils.closing"):
        self.obj = obj
        self.log = log

    def __enter__(self):
        return self.obj

    def __exit__(self, t, v, tb):
        try:
            self.obj.close()
        except Exception:
            if t is None:
                raise
            log = logging.getLogger(self.log)
            log.exception("Error closing %s", self.obj)


class Callback(namedtuple('Callback_', ('func', 'args', 'kwargs'))):
    log = logging.getLogger("utils.Callback")

    def __call__(self):
        result = None
        try:
            self.log.debug('Calling %s with args=%s and kwargs=%s',
                           self.func.__name__, self.args, self.kwargs)
            result = self.func(*self.args, **self.kwargs)
        except Exception:
            self.log.error("%s failed", self.func.__name__, exc_info=True)
        return result


class CallbackChain(threading.Thread):
    """
    Encapsulates the pattern of calling multiple alternative functions
    to achieve some action.

    The chain ends when the action succeeds (indicated by a callback
    returning True) or when it runs out of alternatives.
    """
    log = logging.getLogger("utils.CallbackChain")

    def __init__(self, callbacks=()):
        """
        :param callbacks:
            iterable of callback objects. Individual callback should be
            callable and when invoked should return True/False based on whether
            it was successful in accomplishing the chain's action.
        """
        super(CallbackChain, self).__init__()
        self.daemon = True
        self.callbacks = deque(callbacks)

    def run(self):
        """Invokes serially the callback objects until any reports success."""
        try:
            self.log.debug("Starting callback chain.")
            while self.callbacks:
                callback = self.callbacks.popleft()
                if callback():
                    self.log.debug("Succeeded after invoking " +
                                   callback.func.__name__)
                    return
            self.log.debug("Ran out of callbacks")
        except Exception:
            self.log.error("Unexpected CallbackChain error", exc_info=True)

    def addCallback(self, func, *args, **kwargs):
        """
        :param func:
            the callback function
        :param args:
            args of the callback
        :param kwargs:
            kwargs of the callback
        :return:
        """
        self.callbacks.append(Callback(func, args, kwargs))


class RollbackContext(object):
    '''
    A context manager for recording and playing rollback.
    The first exception will be remembered and re-raised after rollback

    Sample usage:
    with RollbackContext() as rollback:
        step1()
        rollback.prependDefer(lambda: undo step1)
        def undoStep2(arg): pass
        step2()
        rollback.prependDefer(undoStep2, arg)

    More examples see tests/utilsTests.py
    '''
    def __init__(self, on_exception_only=False):
        self._finally = []
        self._on_exception_only = on_exception_only

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        If this function doesn't return True (or raises a different
        exception), python re-raises the original exception once this
        function is finished.
        """
        if self._on_exception_only and exc_type is None and exc_value is None:
            return

        undoExcInfo = None
        for undo, args, kwargs in self._finally:
            try:
                undo(*args, **kwargs)
            except Exception:
                # keep the earliest exception info
                if undoExcInfo is None:
                    undoExcInfo = sys.exc_info()

        if exc_type is None and undoExcInfo is not None:
            six.reraise(undoExcInfo[0], undoExcInfo[1], undoExcInfo[2])

    def defer(self, func, *args, **kwargs):
        self._finally.append((func, args, kwargs))

    def prependDefer(self, func, *args, **kwargs):
        self._finally.insert(0, (func, args, kwargs))


@contextmanager
def running(runnable):
    runnable.start()
    try:
        yield runnable
    finally:
        runnable.stop()


def get_selinux_enforce_mode():
    """
    Returns the SELinux mode as reported by kernel.

    1 = enforcing - SELinux security policy is enforced.
    0 = permissive - SELinux prints warnings instead of enforcing.
    -1 = disabled - No SELinux policy is loaded.
    """
    selinux_mnts = ['/sys/fs/selinux', '/selinux']
    for mnt in selinux_mnts:
        enforce_path = os.path.join(mnt, 'enforce')
        if not os.path.exists(enforce_path):
            continue

        with open(enforce_path) as fileStream:
            return int(fileStream.read().strip())

    # Assume disabled if cannot find
    return -1


def picklecopy(obj):
    """
    Returns a deep copy of argument,
    like copy.deepcopy() does, but faster.

    To be faster, this function leverages the pickle
    module. The following types are safely handled:

    * None, True, and False
    * integers, long integers, floating point numbers,
      complex numbers
    * normal and Unicode strings
    * tuples, lists, sets, and dictionaries containing
      only picklable objects
    * functions defined at the top level of a module
    * built-in functions defined at the top level of a module
    * classes that are defined at the top level of a module
    * instances of such classes whose __dict__ or the
      result of calling __getstate__() is picklable.

    Attempts to pickle unpicklable objects will raise the
    PicklingError exception;
    For full documentation, see:
    https://docs.python.org/2/library/pickle.html
    """
    return pickle.loads(pickle.dumps(obj, pickle.HIGHEST_PROTOCOL))


def round(n, size):
    """
    Round number n to the next multiple of size
    """
    count = int(n + size - 1) // size
    return count * size


def create_connected_socket(host, port, sslctx=None, timeout=None):
    addrinfo = socket.getaddrinfo(host, port,
                                  socket.AF_UNSPEC, socket.SOCK_STREAM)
    family, socktype, proto, _, _ = addrinfo[0]
    sock = socket.socket(family, socktype, proto)

    if sslctx:
        sock = sslctx.wrapSocket(sock)

    sock.settimeout(timeout)
    sock.connect((host, port))
    return sock


@contextmanager
def stopwatch(message, level=logging.DEBUG,
              log=logging.getLogger('vds.stopwatch')):
    if log.isEnabledFor(level):
        start = v2v_time.monotonic_time()
        yield
        elapsed = v2v_time.monotonic_time() - start
        log.log(level, "%s: %.2f seconds", message, elapsed)
    else:
        yield


def unique(iterable):
    """
    Return unique items from iterable of hashable objects, keeping the
    original order.
    """
    return list(OrderedDict.fromkeys(iterable).keys())


def log_success(success, log, msg_ok, msg_fail):
    if success:
        log.info(msg_ok)
    else:
        log.warn(msg_fail)
    return success
