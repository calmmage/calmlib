from calmlib.tools.dev_env_setup.dev_env import (
    CalmmageDevEnv,
    DEFAULT_ROOT_DIR,
    DEFAULT_APP_DATA_DIR,
)

if __name__ == "__main__":
    import argparse

    # Create a parser object
    parser = argparse.ArgumentParser(description="Accepts root dir and app data dir")

    # Add arguments to the parser
    parser.add_argument(
        "--root-dir", "-r", default=DEFAULT_ROOT_DIR, help="The root directory"
    )
    parser.add_argument(
        "--app-data-dir",
        "-a",
        default=DEFAULT_APP_DATA_DIR,
        help="The app data directory",
    )

    # Parse the arguments
    args = parser.parse_args()

    # Create the CalmmageDevEnv object and run the monthly_job method
    dev_env = CalmmageDevEnv(args.root_dir, args.app_data_dir)
    dev_env.monthly_job()
