# ok, now that one lib works - let's make many of them work.
import sys
from pathlib import Path


# todo: add logging to all this
# todo: add metrics to all this.
# http://localhost:8888/notebooks/experiments/0_monitoring_mixin.ipynb


class LibDiscoverer:
    DEFAULT_ROOT_PATHS = ['~/home', '~/calmmage', '~']
    DEFAULT_LIBS = ['defaultenv', 'gpt_api', 'bmmb', 'calmlib', 'code_keeper']

    def __init__(self, root_paths=None):
        if not root_paths:
            root_paths = self.DEFAULT_ROOT_PATHS
        self.root_paths = self.format_paths(root_paths)

    @staticmethod
    def discover_lib_root(lib_name, root_path, depth=3):
        """
        find a path to add to sys.path so that import lib_name works
        start with root_path and go deeper up to depth layers
        if there's a lib_name/lib_name structure
        - add the path including first lib_name
        else - add the path up to the parent, excluding the last lib_name
        """
        root_path = Path(root_path)

        for i in range(depth):
            res = list(root_path.glob('*/' * i + lib_name))
            if res:
                lib_path = res[0]
                break
        else:
            raise ValueError(f'lib {lib_name} not found in {root_path}')

        if (lib_path / lib_name).exists():
            return lib_path
        else:
            return lib_path.parent

    @staticmethod
    def format_paths(paths):
        return [Path(p).expanduser() for p in paths]

    def register_lib(self, lib_name, root_path=None, force=False, depth=3):
        """make it so import lib_name works
        lib_path is the path where approximately lib should be
        """
        # step 0: check if the lib actually already imports
        try:
            __import__(lib_name)
        except ImportError:
            pass
        else:
            if not force:
                return

        # step 1: discover lib path
        root_paths = self.root_paths
        if root_path is not None:
            root_paths = [Path(root_path).expanduser()] + root_paths

        for root_path in root_paths:
            try:
                lib_root = self.discover_lib_root(lib_name, root_path,
                                                  depth=depth)
            except ValueError:
                continue
            else:
                break
        else:
            raise ValueError(f'lib {lib_name} not found in {root_paths}')

        # add discovered lib path to self._lib_roots - at the start.
        if lib_root.name == lib_name:
            new_root_path = lib_root.parent
            if new_root_path not in self.root_paths:
                self.root_paths.insert(0, new_root_path)

        # step 2: add lib path to sys.path
        self.register_path(lib_root)

    enable = enable_lib = register_lib

    @staticmethod
    def register_path(p):
        p = str(p)
        if p not in sys.path:
            sys.path.append(str(p))

    def discover_and_register_libs(self, libs=None, depth=3):
        """make it so import lib_name works for each lib in libs"""
        if libs is None:
            libs = self.DEFAULT_LIBS
        elif isinstance(libs, str):
            libs = [libs]

        for lib in libs:
            self.register_lib(lib, depth=depth)

    enable_libs = discover_and_register_libs

    def status(self):
        status = {}
        # todo: track connected libraries
        # track available libraries

        # show lib roots (added)
        return status

    def print_status(self):
        for k, v in self.status().items():
            print(f'{k}: {v}')


if __name__ == '__main__':
    ld = LibDiscoverer()
    ld.print_status()

    ld.enable('code_keeper', depth=5)
