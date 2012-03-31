def load_tests(loader, tests, ignore):
    import os
    import pkg_resources
    # only run under python2.7+ but we are just testing the documentation
    root = pkg_resources.get_distribution('van.static').location
    readme = os.path.join(root, 'README.rst')
    if os.path.exists(readme):
        import doctest
        tests.addTests(doctest.DocFileSuite(readme, module_relative=False))
    return tests
