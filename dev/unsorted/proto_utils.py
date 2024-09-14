from pathlib import Path


def compile_proto(path, output_path=None, package_path=None):
    """
    compile a proto file located at :path:
    """
    from calmlib import run_cmd
    # protoc -I=proto/ --python_out=proto/ proto/test.proto
    path = Path(path)
    if output_path is None:
        output_path = path.parent
    if package_path is None:
        package_path = path.parent
    cmd = f"protoc -I={package_path} --python_out={output_path} {path}"
    return run_cmd(cmd)
