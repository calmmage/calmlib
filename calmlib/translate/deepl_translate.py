import os


def discover_deepl_auth_key():
    # env
    key = os.getenv("DEEPL_AUTH_KEY")
    if key:
        return key
    # file on disk
    path_candidates = [
        os.path.join(os.path.expanduser("~"), ".deepl_auth_key"),
        ".deepl_auth_key",
    ]
    for path in path_candidates:
        if os.path.exists(path):
            with open(path) as f:
                auth_key = f.read().strip()
            if auth_key:
                return auth_key
    # user input
    auth_key = input("Please enter your DeepL auth key: ")
    # save to disk
    path = os.path.join(os.path.expanduser("~"), ".deepl_auth_key")
    with open(path, "w") as f:
        f.write(auth_key)
    return auth_key


registry = {}


def init_deepl(auth_key=None):
    import deepl

    if auth_key is None:
        auth_key = discover_deepl_auth_key()

    translator = deepl.Translator(auth_key)
    return translator


def get_deepl_translator():
    if "translator" not in registry:
        registry["translator"] = init_deepl()
    return registry["translator"]


# todo: add supported languages as a const list
def translate_text(text, target_lang="EN-US"):
    lang = parse_lang(target_lang)
    translator = get_deepl_translator()
    result = translator.translate_text(text, target_lang=lang)
    return result.text


import re

ru_pattern = re.compile("[а-яА-Я]")
en_pattern = re.compile("[a-zA-Z]")

lang_dict = {
    "russian": "RU",
    "english": "EN-US",
    "ru": "RU",
    "en": "EN-US",
    "ru-ru": "RU",
    "en-uk": "EN-GB",
    "en-gb": "EN-GB",
    "en-us": "EN-US",
}


def parse_lang(lang):
    return lang_dict[lang.lower()]


def requires_translation(
    text: str, target_lang: str, rel_tolerance=0.5, abs_tolerance=200
):
    lang = parse_lang(target_lang)

    if lang == "RU":
        count_wrong = len(en_pattern.findall(text))
    elif lang in ["EN-US", "EN-GB"]:
        count_wrong = len(ru_pattern.findall(text))
    else:
        raise ValueError("Invalid target language")

    rel = count_wrong / len(text)
    if rel > rel_tolerance or count_wrong > abs_tolerance:
        return True
    else:
        return False
