"""Tools for working with static resources and YUI3."""
import warnings
from pkg_resources import resource_listdir, resource_stream

_MODULE_CACHE = {}

def _extract_requires(line):
    # EVIL JS introspection
    # Will break if you sneeze hard
    l = line.split('requires: [', 1)
    if len(l) == 1:
        return None
    l = l[1]
    l, _ = l.split(']', 1)
    if len(l) == 1:
        return None
    return l.replace(' ', '').replace("'", '').replace('"', '').split(',')

def find_modules(resource, reload=False, fail_onerror=True):
    if not reload:
        cached = _MODULE_CACHE.get(resource, None)
        if cached is not None:
            return cached
    modules = {}
    pname, path = resource.split(':', 1)
    for filename in resource_listdir(pname, path):
        if filename.startswith('.') or not filename.endswith('.js'):
            continue
        module = filename[:-3]
        filepath = '/'.join([path, filename])
        file = resource_stream(pname, filepath)
        try:
            lines = file.read()
        finally:
            file.close()
        lines = lines.splitlines()
        lines.reverse()
        for l in lines:
            if not l.strip():
                continue
            requires = _extract_requires(l)
            if requires is None:
                msg = "could not find requires in %s:%s, last line was: %s" % (pname, filepath, l)
                if fail_onerror:
                    raise Exception(msg)
                else:
                    warnings.warn(msg)
            break
        modules[module] = dict(path=filename, requires=requires)
    _MODULE_CACHE[resource] = modules
    return find_modules(resource, reload=False)

def find_group(request, resource, fail_onerror=False):
    """Return a group for the YU3 loader configuration.

    This will look into the resource (which must be a directory) and extract
    any .js files. It will try to parse the file and figure the requirements.
    """
    modules = find_modules(resource, reload=request.registry.settings['reload_assets'], fail_onerror=fail_onerror)
    group = {'base': request.static_url(resource) + '/',
             'modules': modules}
    return group
