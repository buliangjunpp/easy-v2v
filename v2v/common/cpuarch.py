import os
import platform


X86_64 = 'x86_64'
PPC64 = 'ppc64'
PPC64LE = 'ppc64le'
AARCH64 = 'aarch64'
S390X = 's390x'

SUPPORTED_ARCHITECTURES = (X86_64, PPC64, PPC64LE, AARCH64, S390X)

PAGE_SIZE_BYTES = os.sysconf('SC_PAGESIZE')


class UnsupportedArchitecture(Exception):
    def __init__(self, target_arch):
        self._target_arch = target_arch

    def __str__(self):
        return '{} is not supported architecture.'.format(self._target_arch)


def real():
    '''
    Get the system (host) CPU architecture.

    Returns:

    One of the Architecture attributes indicating the architecture that the
    system is using
    or
    raises UnsupportedArchitecture exception.

    Examples:

    current() ~> X86_64
    '''
    return _supported(platform.machine())


def is_ppc(arch):
    return arch == PPC64 or arch == PPC64LE


def is_x86(arch):
    return arch == X86_64


def is_arm(arch):
    return arch == AARCH64


def is_s390(arch):
    return arch == S390X


def _supported(target_arch):
    if target_arch not in SUPPORTED_ARCHITECTURES:
        raise UnsupportedArchitecture(target_arch)

    return target_arch
