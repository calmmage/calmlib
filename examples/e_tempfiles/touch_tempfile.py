from tempfile import TemporaryFile

if __name__ == "__main__":
    with TemporaryFile("r+") as f:
        f.write("test")
        f.seek(0)
        print(f.read())
