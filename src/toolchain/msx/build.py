"""Validate fresh local build destinations."""

def destination(root, path, *, sessions=False):
    path = path.absolute()
    if '..' in path.parts or any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError('Output cannot traverse parents or symlinks')
    scope = root.resolve()/('references/sessions' if sessions else 'references/build')
    if not path.is_relative_to(scope):
        raise ValueError('Output must be below references/build')
    if path.exists():
        raise ValueError('Output exists; select a fresh output directory')
    return path
