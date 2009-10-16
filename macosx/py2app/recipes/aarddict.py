def check(cmd, mf):
    m = mf.findNode('aarddict')
    if m is None or m.filename is None:
        return None
    return dict(
        packages = ['aarddict']
    )
