def get_calmlib_root():
    from pathlib import Path
    # if this file is in calmlib: use that
    if 'calmlib' in __file__:
        # get the path up to the first calmlib
        return __file__.rsplit('calmlib', 1)[0]
    # else check ./calmlib_path.txt
    else:
        config_path = Path(__file__).parent / 'calmlib_root.txt'
        calmlib_path = config_path.read_text().strip()
        return calmlib_path


calmlib_root = str(get_calmlib_root())
import sys

if calmlib_root not in sys.path:
    sys.path.append(calmlib_root)

# todo 1: add LibDiscoverer
from calmlib.utils.lib_discoverer import LibDiscoverer

lib_discoverer = LibDiscoverer()

# todo 2: add all the libs
lib_discoverer.enable('code_keeper', depth=5)
# 2.1 code keeper, memory keeper
libs = [
    'calmlib',
    'gpt_kit',
    'bmmb'
]
lib_discoverer.enable_libs(libs)

# todo 3: import all the libs. initialize default variables
# --------------------------------
# 3.1 defaultenv
# --------------------------------
try:
    from pathlib import Path
    import sys

    p = Path('~/home/lib/defaultenv').expanduser()
    sys.path.append(str(p))
    from defaultenv import ENVCD as env
except:
    logger.warning('import defaultenv failed, traceback:', exc_info=True)

# --------------------------------
# 3.2 code keeper
from code_keeper import remind

print(remind())

if __name__ == '__main__':
    # todo: print info from memory keeper
    pass
