"""Static resources testing support."""
import os
import subprocess
import tempfile

MAX_PROCS = 4
try:
    import multiprocessing
    MAX_PROCS = multiprocessing.cpu_count() * 2
except ImportError:
    pass
except NotImplementedError:
    pass

def assert_jslint_dir(path, failfast=False):
    """Run jslint on all .js files under path.

    return True or raises an AssertionError if any file fails.

    This function will attempt to start the 2*number of CPU's to speed up
    checking.
    """
    messages, files = jslint_dir(path, failfast)
    if not files:
        raise AssertionError("Did not find any .js files to check in %s" % path)
    if not messages:
        return True
    messages = sorted([(m['file'], m) for m in messages])
    lines = ["JSLint failed on %s files out of %s checked" % (len(messages), len(files))]
    for file, m in messages:
        lines.append('')
        lines.append("JSLint failed: %s" % file)
        lines.append(m['stdout'])
    raise AssertionError('\n'.join(lines))

def jslint_dir(path, failfast):
    queue = []
    messages = []
    files_checked = []
    for root, dirs, files in os.walk(path):
        for name in files:
            if name.startswith('.') or not name.endswith('.js'):
                continue
            f = os.path.join(root, name)
            queue.append(f)
            files_checked.append(f)
    running = {}
    while queue:
        next = queue.pop(0)
        p, output = _start_jslint(next)
        running[next] = p, output
        if len(running) == MAX_PROCS:
            # just wait till one of the processes is finished
            running.values()[0][0].wait()
        messages.extend(_check_running(running))
        assert len(running) <= MAX_PROCS
    for p, _ in running.values():
        p.wait()
        messages.extend(_check_running(running))
    return messages, files_checked

def _start_jslint(path):
    output = tempfile.TemporaryFile()
    p = subprocess.Popen(['jslint', path],
            stdout=output,
            stderr=subprocess.STDOUT)
    return p, output

def _check_running(running):
    messages = []
    for file, p in running.items():
        p, output = p
        ret = p.poll()
        if ret is not None:
            del running[file]
            output.seek(0)
            result = output.read()
            if result.strip() != 'No error found': # cant trust the returncode :(
                messages.append(dict(file=file, stdout=result))
            output.close()
    return messages
