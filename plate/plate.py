#  MIT License
#
#  Copyright (c) 2020 Dan <https://github.com/delivrance>
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all
#  copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#  SOFTWARE.

import json
import logging
import re
from functools import partial
from pathlib import Path

from . import emojipedia, languages


class Plate:
    def __init__(self, root: str = "locales", locale: str = "en_US", fallback: str = None, separator: str = "|"):
        """Creates a new Plate instance.

        Parameters:
            root (str, optional):
                The folder root containing all locale sources.
                Defaults to "locales".

            locale (str, optional):
                The default locale.
                Defaults to "en_US"

            fallback (str, optional):
                The fallback locale used when the translated phrase keys have no value.
                Defaults to the value passed to the "locale" parameter, which is "en_US" by default.

            separator (str):
                The string used for delimiting pluralized phrases.
        """
        self.root = root
        self.locale = locale
        self.fallback = fallback or locale
        self.separator = separator

        self.locales = {
            locale: [getattr(languages, locale), None]
            for locale in filter(lambda x: not x.startswith("__"), vars(languages))
        }

        self._load()

    def set_locale(self, locale: str):
        """Sets a new default locale.

        Parameters:
            locale (str):
                The new default locale to set.
        """
        self._check_valid_locale(locale)
        self.locale = locale

    def get_translator(self, locale: str):
        """Retrieves a translator for a given locale.

        Parameters:
            locale (str):
                The locale to get the translator for.
        """
        self._check_valid_locale(locale)
        return partial(self, locale=locale)

    def __call__(self, key: str, locale: str = None, *, count: int = None, **kwargs) -> str:
        """Translate a phrase given a key and an optional locale.

        Parameters:
            key (str):
                Phrase key to translate.

            locale (str, optional):
                The destination locale code the phrase will be translated to.
                Defaults to the current default locale.

            count (int, optional):
                Special optional count argument used for pluralization.
                Only applicable in case phrases contain {count}.

            **kwargs:
                Extra optional keyword argument for string interpolations.
                Applicable to all phrases that contain placeholders.

        Returns:
            str: The translated phrase.
        """
        if locale is None:
            locale = self.locale
        else:
            self._check_valid_locale(locale)

        phrase = self.locales[locale][1].get(key)

        if not phrase:
            phrase = self.locales[self.fallback][1][key]

        try:
            if count is not None:
                phrase = self._format_plurals(phrase, locale, count)

            return phrase.format(**kwargs)
        except KeyError as e:
            raise KeyError('Missing interpolation value for key "{}"'.format(e.args[0])) from None

    def _check_valid_locale(self, locale: str):
        if locale not in self.locales:
            raise ValueError(
                'Invalid locale code "{}". Possible values are: {}'.format(
                    locale, ", ".join('"{}" ({})'.format(k, v[0]) for k, v in self.locales.items())
                )
            )

    def _load(self):
        for path in Path(self.root).iterdir():
            name = path.name

            if not name.endswith(".json"):
                logging.warning('Skipping unknown file "{}"'.format(name))
                continue

            locale = name.split(".")[0]

            self._check_valid_locale(locale)

            with open(str(path), encoding="utf-8") as f:
                try:
                    locale_data = json.load(f)
                except json.JSONDecodeError as e:
                    raise ValueError('Error in file "{}": {}'.format(name, e)) from None

            for k, v in locale_data.items():
                if isinstance(v, list):
                    locale_data[k] = "".join(v)

            for k, v in locale_data.items():
                with_emoji = v

                for text in re.findall(r":(\w+):", with_emoji):
                    if text.islower():
                        logging.warning(
                            'Emoji "{}" from "{}" in "{}" should be in upper case: "{}"'.format(
                                text, k, locale, text.upper()
                            )
                        )

                    emoji = getattr(emojipedia, text.upper(), None)

                    if emoji is None:
                        raise ValueError('"{}" in "{}" contains unknown emoji "{}"'.format(k, locale, text))

                    with_emoji = re.sub(":{}:".format(text), emoji, with_emoji)

                locale_data[k] = with_emoji

            self.locales[locale][1] = locale_data

        for locale in self.locales.copy():
            if self.locales[locale][1] is None:
                self.locales.pop(locale)

        fallback_keys = self.locales[self.fallback][1].keys()

        for locale, locale_data in self.locales.items():
            locale_data = locale_data[1]

            for key in fallback_keys:
                if key not in locale_data:
                    raise ValueError('Missing translation key "{}" from "{}"'.format(key, locale))

                if not locale_data[key]:
                    logging.warning('Empty translation phrase for key "{}" in "{}"'.format(key, locale))

            for key in locale_data:
                if key not in fallback_keys:
                    raise ValueError(
                        'The key "{}" from "{}" does not exist in fallback locale "{}"'.format(
                            key, locale, self.fallback
                        )
                    )

    def _format_plurals(self, phrase: str, locale: str, count: int) -> str:
        options = [option.strip() for option in phrase.split(self.separator)]

        # TODO: Add locales plural rules

        index = count if count < 3 else 2

        return options[index].format(count=count)
