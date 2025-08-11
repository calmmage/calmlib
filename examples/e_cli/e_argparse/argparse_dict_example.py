import argparse


def main(test):
    print(test)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", default="Test")
    args = parser.parse_args()
    main(**args.__dict__)
