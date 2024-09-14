# 1) run external binary - basically any bash command
import threading
from subprocess import Popen, PIPE


def run_cmd(cmd, stdin=''):
    """
    Execute any bash command. Return its output.
    :param cmd:
    :param stdin:
    :return:
    """

    p = Popen(cmd.split(), stdin=PIPE, stdout=PIPE, stderr=PIPE)
    output, err = p.communicate(stdin.encode())
    rc = p.returncode
    if rc:
        raise Exception(err)
    return output.decode()


# 2) run python code - eval
# 3) run python function in backgroud - threading, subprocess etc.

def run_bg(func, *args, **kwargs):
    """
    Execute any callable in a background thread
    :param func: target func for thread
    :param args: args for func
    :param kwargs: kwargs for func
    :return: threading.Thread object
    """
    t = threading.Thread(target=func, args=args, kwargs=kwargs)
    t.start()
    return t
