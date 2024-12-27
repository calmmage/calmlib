def load_global_env():
    from dotenv import load_dotenv
    from pathlib import Path

    p = Path("~/.env").expanduser()
    load_dotenv(p)
