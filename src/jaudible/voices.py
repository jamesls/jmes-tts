LANGUAGES = {
    'english': {
        'voice': 'Matthew',
        'engine': 'generative',
        'language_code': 'en-US',
    },
    'french': {
        'engine': 'generative',
        'voice': 'Lea',
        'language_code': 'fr-FR',
    },
    'spanish': {
        'engine': 'generative',
        'voice': 'Mia',
        'language_code': 'es-MX',
    },
    'cantonese': {
        'engine': 'neural',
        'voice': 'Hiujin',
        'language_code': 'yue-CN',
    },
    'mandarin': {
        'engine': 'neural',
        'voice': 'Zhiyu',
        'language_code': 'cmn-CN',
    },
}


def normalize_language(language: str) -> str:
    return language.strip().lower()
