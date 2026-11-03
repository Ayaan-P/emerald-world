"""Private sandbox entrypoint. Importing this module has no side effects."""
import json
import resource


def _restrict_syscalls():
    """Fail closed unless the kernel enforces this read-only x86-64 policy.

    Python imports still work, but process/thread creation, execution, sockets,
    filesystem mutation and namespace changes are unavailable. RLIMIT_NPROC
    alone is not a fork-bomb defense for privileged namespace users.
    """
    import ctypes
    import errno
    import platform
    if platform.machine() != 'x86_64':
        raise RuntimeError('mechanic seccomp policy requires x86_64')

    class Filter(ctypes.Structure):
        _fields_ = [('code', ctypes.c_ushort), ('jt', ctypes.c_ubyte),
                    ('jf', ctypes.c_ubyte), ('k', ctypes.c_uint)]

    class Program(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ushort), ('filters', ctypes.POINTER(Filter))]

    allow = 0x7fff0000
    denied = 0x00050000 | errno.EPERM
    rules = [(0x20, 0, 0, 4), (0x15, 1, 0, 0xc000003e),
             (0x06, 0, 0, 0x80000000), (0x20, 0, 0, 0)]
    # seccomp_data.args starts at byte 16. open flags are arg1, openat arg2.
    for syscall, flags_offset in ((2, 24), (257, 32)):
        rules.extend([(0x15, 0, 4, syscall), (0x20, 0, 0, flags_offset),
                      (0x45, 0, 1, 3 | 64 | 128 | 512 | 1024 | 0x400000),
                      (0x06, 0, 0, denied), (0x06, 0, 0, allow)])
    allowed = (0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
               16, 17, 19, 20, 21, 23, 24, 25, 28, 32, 33, 35, 39, 60,
               63, 72, 73, 79, 89, 96, 97, 98, 99, 102, 104, 107, 108,
               110, 131, 186, 202, 204, 217, 228, 230, 231, 262, 267,
               269, 270, 271, 302, 318, 332)
    for syscall in allowed:
        rules.extend([(0x15, 0, 1, syscall), (0x06, 0, 0, allow)])
    rules.append((0x06, 0, 0, denied))
    filters = (Filter * len(rules))(*(Filter(*rule) for rule in rules))
    program = Program(len(rules), filters)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) or libc.prctl(22, 2, ctypes.byref(program), 0, 0):
        raise OSError(ctypes.get_errno(), 'cannot enable mechanic seccomp policy')


def _check_json(value, depth=0):
    if depth > 64:
        raise ValueError('JSON nesting exceeds 64 levels')
    kind = type(value)
    if value is None or kind in (str, int, float, bool):
        return
    if kind is list:
        for child in value:
            _check_json(child, depth + 1)
    elif kind is dict and all(type(key) is str for key in value):
        for child in value.values():
            _check_json(child, depth + 1)
    else:
        raise ValueError('result must have strict JSON types')


def main():
    import os
    os.closerange(3, 1048576)
    os.environ.pop('PWD', None)
    resource.setrlimit(resource.RLIMIT_CPU, (1, 1))
    resource.setrlimit(resource.RLIMIT_AS, (134217728, 134217728))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1048576, 1048576))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    with open('/app/request.json') as stream:
        request = json.load(stream)
    with open('/app/candidate.py') as stream:
        source = stream.read()
    _restrict_syscalls()
    scope = {'__name__': 'mechanic', '__file__': '/app/candidate.py'}
    exec(compile(source, '/app/candidate.py', 'exec'), scope)
    result = scope['update'](request['context'], request['state'])
    _check_json(result)
    serialized = json.dumps(result, allow_nan=False, separators=(',', ':'))
    if 'tests' in request:
        import unittest
        import sys
        # Serialize immediately so tests cannot erase invalid output by mutating
        # a returned object. Host-side validation uses the runtime's own schema.
        results = []
        size = len(json.dumps({'baseline': serialized, 'test_results': []},
                              separators=(',', ':')).encode('utf-8'))
        recording_failed = False
        update = scope['update']

        def tested_update(*args, **kwargs):
            nonlocal size, recording_failed
            value = update(*args, **kwargs)
            try:
                _check_json(value)
                snapshot = json.dumps(value, allow_nan=False, separators=(',', ':'))
                size += len(json.dumps(snapshot).encode('utf-8')) + bool(results)
                if recording_failed or size > 196608:
                    raise ValueError('mechanic test output exceeds limit')
                results.append(snapshot)
            except (ValueError, TypeError, RecursionError, UnicodeError):
                # A test catching the serialization error must not permit staging.
                recording_failed = True
                raise
            return value

        tests = {'__name__': 'mechanic_tests', 'update': tested_update}
        exec(compile(request['tests'], '/app/tests.py', 'exec'), tests)
        count = 0
        suite = unittest.TestSuite()
        for name, value in sorted(tests.items()):
            if name.startswith('test_') and callable(value):
                value()
                count += 1
            elif isinstance(value, type) and issubclass(value, unittest.TestCase):
                suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(value))
        count += suite.countTestCases()
        if not count:
            raise ValueError('supplied test file contains no tests')
        if not unittest.TextTestRunner(stream=sys.stderr).run(suite).wasSuccessful():
            raise ValueError('candidate tests failed')
        if recording_failed:
            raise ValueError('invalid mechanic test output')
        serialized = json.dumps({'baseline': serialized, 'test_results': results},
                                allow_nan=False, separators=(',', ':'))
    print(serialized)


if __name__ == '__main__':
    main()
