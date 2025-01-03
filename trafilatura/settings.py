# pylint:disable-msg=E0611
"""
Listing a series of settings that are applied module-wide.
"""

from configparser import ConfigParser
from datetime import datetime
from html import unescape
from typing import Any, Dict, List, Optional, Set

try:
    from os import sched_getaffinity
    CPU_COUNT = len(sched_getaffinity(0))
except ImportError:
    from os import cpu_count
    CPU_COUNT = cpu_count() or 1

from pathlib import Path

from lxml.etree import _Element, Element, XPath

from .utils import line_processing


SUPPORTED_FMT_CLI = ["csv", "json", "html", "markdown", "txt", "xml", "xmltei"]
SUPPORTED_FORMATS = set(SUPPORTED_FMT_CLI) | {"python"}  # for bare_extraction() only


def use_config(
    filename: Optional[str] = None, config: Optional[ConfigParser] = None
) -> ConfigParser:
    """
    Use configuration object or read and parse a settings file.
    """
    if config is not None:
        return config

    if filename is None:
        filename = str(Path(__file__).parent / "settings.cfg")
    elif not Path(filename).is_file():
        raise FileNotFoundError("The given config file does not exist")

    config = ConfigParser()
    config.read(filename)
    return config


DEFAULT_CONFIG = use_config()

CONFIG_MAPPING = {
    "min_extracted_size": "MIN_EXTRACTED_SIZE",
    "min_output_size": "MIN_OUTPUT_SIZE",
    "min_output_comm_size": "MIN_OUTPUT_COMM_SIZE",
    "min_extracted_comm_size": "MIN_EXTRACTED_COMM_SIZE",
    "min_duplcheck_size": "MIN_DUPLCHECK_SIZE",
    "max_repetitions": "MAX_REPETITIONS",
    "max_file_size": "MAX_FILE_SIZE",
    "min_file_size": "MIN_FILE_SIZE",
}


# todo Python >= 3.10: use dataclass with slots=True
class Extractor:
    "Defines a class to store all extraction options."
    __slots__ = [
        "config",
        # general
        "format",
        "fast",
        "focus",
        "comments",
        "formatting",
        "preserve_space",
        "links",
        "images",
        "tables",
        "dedup",
        "lang",
        # extraction size
        "min_extracted_size",
        "min_output_size",
        "min_output_comm_size",
        "min_extracted_comm_size",
        # deduplication
        "min_duplcheck_size",
        "max_repetitions",
        # rest
        "max_file_size",
        "min_file_size",
        "max_tree_size",
        # meta
        "source",
        "url",
        "with_metadata",
        "only_with_metadata",
        "tei_validation",
        "date_params",
        "author_blacklist",
        "url_blacklist",
    ]

    def __init__(
        self,
        *,
        config: ConfigParser = DEFAULT_CONFIG,
        output_format: str = "txt",
        fast: bool = False,
        precision: bool = False,
        recall: bool = False,
        comments: bool = True,
        formatting: bool = False,
        preserve_space: bool = False,
        links: bool = False,
        images: bool = False,
        tables: bool = True,
        dedup: bool = False,
        lang: Optional[str] = None,
        url: Optional[str] = None,
        source: Optional[str] = None,
        with_metadata: bool = False,
        only_with_metadata: bool = False,
        tei_validation: bool = False,
        author_blacklist: Optional[Set[str]] = None,
        url_blacklist: Optional[Set[str]] = None,
        date_params: Optional[Dict[str, str]] = None,
    ):
        self._set_source(url, source)
        self._set_format(output_format)
        self._add_config(config)
        self.fast: bool = fast
        self.focus: str = (
            "recall" if recall else "precision" if precision else "balanced"
        )
        self.comments: bool = comments
        self.formatting: bool = formatting or self.format == "markdown"
        self.preserve_space: bool = preserve_space
        self.links: bool = links
        self.images: bool = images
        self.tables: bool = tables
        self.dedup: bool = dedup
        self.lang: Optional[str] = lang
        self.url: Optional[str] = url
        self.only_with_metadata: bool = only_with_metadata
        self.tei_validation: bool = tei_validation
        self.author_blacklist: Set[str] = author_blacklist or set()
        self.url_blacklist: Set[str] = url_blacklist or set()
        self.with_metadata: bool = (
            with_metadata
            or only_with_metadata
            or bool(url_blacklist)
            or output_format == "xmltei"
        )
        self.date_params: Dict[str, Any] = date_params or set_date_params(
            self.config.getboolean("DEFAULT", "EXTENSIVE_DATE_SEARCH")
        )
        self.max_tree_size = None

    def _set_source(self, url: Optional[str], source: Optional[str]) -> None:
        "Set the source attribute in a robust way."
        source = url or source
        self.source = source and source.encode("utf-8", "replace").decode("utf-8")

    def _set_format(self, chosen_format: str) -> None:
        "Store the format if supported and raise an error otherwise."
        if chosen_format not in SUPPORTED_FORMATS:
            raise AttributeError(
                f"Cannot set format, must be one of: {', '.join(sorted(SUPPORTED_FORMATS))}"
            )
        self.format = chosen_format

    def _add_config(self, config: ConfigParser) -> None:
        "Store options loaded from config file."
        for key, value in CONFIG_MAPPING.items():
            setattr(self, key, config.getint("DEFAULT", value))
        self.config = config


def args_to_extractor(args: Any, url: Optional[str] = None) -> Extractor:
    "Derive extractor configuration from CLI args."
    options = Extractor(
        config=use_config(filename=args.config_file),
        output_format=args.output_format,
        formatting=args.formatting,
        precision=args.precision,
        recall=args.recall,
        comments=args.no_comments,
        tables=args.no_tables,
        dedup=args.deduplicate,
        lang=args.target_language,
        url=url,
        with_metadata=args.with_metadata,
        only_with_metadata=args.only_with_metadata,
        tei_validation=args.validate_tei,
    )
    for attr in ("fast", "images", "links"):
        setattr(options, attr, getattr(args, attr))
    return options


def set_date_params(extensive: bool = True) -> Dict[str, Any]:
    "Provide default parameters for date extraction."
    return {
        "original_date": True,
        "extensive_search": extensive,
        "max_date": datetime.now().strftime("%Y-%m-%d"),
    }


# todo Python >= 3.10: use dataclass with slots=True
class Document:
    "Defines a class to store all necessary data and metadata fields for extracted information."
    __slots__ = [
        "title",
        "author",
        "url",
        "hostname",
        "description",
        "sitename",
        "date",
        "categories",
        "tags",
        "fingerprint",
        "id",
        "license",
        "body",
        "comments",
        "commentsbody",
        "raw_text",
        "text",
        "language",
        "image",
        "pagetype",
        "filedate",
        # 'locale'?
    ]

    def __init__(
        self,
        *,
        title: Optional[str] = None,
        author: Optional[str] = None,
        url: Optional[str] = None,
        hostname: Optional[str] = None,
        description: Optional[str] = None,
        sitename: Optional[str] = None,
        date: Optional[str] = None,
        categories: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        fingerprint: Optional[str] = None,
        idval: Optional[str] = None,
        license_val: Optional[str] = None,
        body: _Element = Element("body"),
        comments: Optional[str] = None,
        commentsbody: _Element = Element("body"),
        raw_text: Optional[str] = None,
        text: Optional[str] = None,
        language: Optional[str] = None,
        image: Optional[str] = None,
        pagetype: Optional[str] = None,
        filedate: Optional[str] = None,
    ):
        self.title: Optional[str] = title
        self.author: Optional[str] = author
        self.url: Optional[str] = url
        self.hostname: Optional[str] = hostname
        self.description: Optional[str] = description
        self.sitename: Optional[str] = sitename
        self.date: Optional[str] = date
        self.categories: Optional[List[str]] = categories
        self.tags: Optional[List[str]] = tags
        self.fingerprint: Optional[str] = fingerprint
        self.id: Optional[str] = idval
        self.license: Optional[str] = license_val
        self.body: _Element = body
        self.comments: Optional[str] = comments
        self.commentsbody: _Element = commentsbody
        self.raw_text: Optional[str] = raw_text
        self.text: Optional[str] = text
        self.language: Optional[str] = language
        self.image: Optional[str] = image
        self.pagetype: Optional[str] = pagetype
        self.filedate: Optional[str] = filedate

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Document':
        "Set a series of attributes using a dictionary."
        doc = cls()
        for key, value in data.items():
            setattr(doc, key, value)
        return doc

    def clean_and_trim(self) -> None:
        "Limit text length and trim the attributes."
        for slot in self.__slots__:
            value = getattr(self, slot)
            if isinstance(value, str):
                # length
                if len(value) > 10000:
                    value = value[:9999] + "…"
                # HTML entities, remove spaces and control characters
                value = line_processing(unescape(value))
                setattr(self, slot, value)

    def as_dict(self) -> Dict[str, Optional[str]]:
        "Convert the document to a dictionary."
        return {attr: getattr(self, attr, None) for attr in self.__slots__}


# Safety checks
PARALLEL_CORES = min(CPU_COUNT, 16)  # 16 processes at most
LRU_SIZE = 4096

# Files
MAX_FILES_PER_DIRECTORY = 1000
FILENAME_LEN = 8

# Network
MAX_LINKS = 10**6
MAX_SITEMAPS_SEEN = 10**4


# filters
CUT_EMPTY_ELEMS = {
    "article",
    "b",
    "blockquote",
    "dd",
    "div",
    "dt",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "i",
    "li",
    "main",
    "p",
    "pre",
    "q",
    "section",
    "span",
    "strong",
}
# 'meta', 'td', 'a', 'caption', 'dl', 'header',
# 'colgroup', 'col',
# CUT_EMPTY_ELEMS = {'div', 'span'}

# order could matter, using lists to keep extraction deterministic
MANUALLY_CLEANED = [
    # important
    "aside",
    "embed",
    "footer",
    "form",
    "head",
    "iframe",
    "menu",
    "object",
    "script",
    # other content
    "applet",
    "audio",
    "canvas",
    "figure",
    "map",
    "picture",
    "svg",
    "video",
    # secondary
    "area",
    "blink",
    "button",
    "datalist",
    "dialog",
    "frame",
    "frameset",
    "fieldset",
    "link",
    "input",
    "ins",
    "label",
    "legend",
    "marquee",
    "math",
    "menuitem",
    "nav",
    "noindex",
    "noscript",
    "optgroup",
    "option",
    "output",
    "param",
    "progress",
    "rp",
    "rt",
    "rtc",
    "select",
    "source",
    "style",
    "track",
    "textarea",
    "time",
    "use",
]
# 'meta', 'hr', 'img', 'data', 'details', 'summary'

MANUALLY_STRIPPED = [
    "abbr",
    "acronym",
    "address",
    "bdi",
    "bdo",
    "big",
    "cite",
    "data",
    "dfn",
    "font",
    "hgroup",
    "img",
    "ins",
    "mark",
    "meta",
    "ruby",
    "small",
    "tbody",
    "template",
    "tfoot",
    "thead",
]
# 'center', 'rb', 'wbr'

BASIC_CLEAN_XPATH = XPath(
    ".//aside|.//div[contains(@class|@id, 'footer')]|.//footer|.//script|.//style"
)

TAG_CATALOG = frozenset(
    ["blockquote", "code", "del", "head", "hi", "lb", "list", "p", "pre", "quote"]
)
# + list(CUT_EMPTY_ELEMS)


JUSTEXT_LANGUAGES = {
    "ar": "Arabic",
    "bg": "Bulgarian",
    "cz": "Czech",
    "da": "Danish",
    "de": "German",
    "en": "English",
    "el": "Greek",
    "es": "Spanish",
    "fa": "Persian",
    "fi": "Finnish",
    "fr": "French",
    "hr": "Croatian",
    "hu": "Hungarian",
    # 'ja': '',
    "ko": "Korean",
    "id": "Indonesian",
    "it": "Italian",
    "no": "Norwegian_Nynorsk",
    "nl": "Dutch",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "sr": "Serbian",
    "sv": "Swedish",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "ur": "Urdu",
    "vi": "Vietnamese",
    # 'zh': '',
}
