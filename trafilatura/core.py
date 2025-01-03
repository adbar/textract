# pylint:disable-msg=E0611,I1101
"""
Extraction configuration and processing functions.
"""

import logging
import warnings

from copy import copy, deepcopy
from typing import Any, Dict, Optional, Set, Tuple, Union

from lxml.etree import _Element, Element, XPath, strip_tags
from lxml.html import HtmlElement

# own
from .baseline import baseline
from .deduplication import content_fingerprint, duplicate_test
from .external import compare_extraction
from .htmlprocessing import (
    build_html_output,
    convert_tags,
    prune_unwanted_nodes,
    tree_cleaning,
)
from .main_extractor import extract_comments, extract_content
from .metadata import Document, extract_metadata
from .settings import DEFAULT_CONFIG, Extractor, use_config
from .utils import (
    LANGID_FLAG,
    check_html_lang,
    language_filter,
    load_html,
    normalize_unicode,
)
from .xml import build_json_output, control_xml_output, xmltotxt, xmltocsv
from .xpaths import REMOVE_COMMENTS_XPATH


LOGGER = logging.getLogger(__name__)

TXT_FORMATS = {"markdown", "txt"}


def determine_returnstring(document: Document, options: Extractor) -> str:
    """Convert XML tree to chosen format, clean the result and output it as a string"""
    # XML (TEI) steps
    if "xml" in options.format:
        # last cleaning
        for element in document.body.iter("*"):
            if (
                element.tag != "graphic"
                and len(element) == 0
                and not element.text
                and not element.tail
            ):
                parent = element.getparent()
                # do not remove elements inside <code> to preserve formatting
                if parent is not None and parent.tag != "code":
                    parent.remove(element)
        # build output tree
        returnstring = control_xml_output(document, options)
    # CSV
    elif options.format == "csv":
        returnstring = xmltocsv(document, options.formatting)
    # JSON
    elif options.format == "json":
        returnstring = build_json_output(document, options.with_metadata)
    # HTML
    elif options.format == "html":
        returnstring = build_html_output(document, options.with_metadata)
    # Markdown and TXT
    else:
        if options.with_metadata:
            header = "---\n"
            for attr in (
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
            ):
                if getattr(document, attr):
                    header += f"{attr}: {str(getattr(document, attr))}\n"
            header += "---\n"
        else:
            header = ""
        returnstring = f"{header}{xmltotxt(document.body, options.formatting, options.preserve_space)}"
        if document.commentsbody is not None:
            returnstring = \
                f"{returnstring}\n{xmltotxt(document.commentsbody, options.formatting, options.preserve_space)}".strip()
    # normalize Unicode format (defaults to NFC)
    return normalize_unicode(returnstring)


def trafilatura_sequence(
    cleaned_tree: HtmlElement,
    cleaned_tree_backup: HtmlElement,
    tree_backup: HtmlElement,
    options: Extractor,
) -> Tuple[_Element, str, int]:
    "Execute the standard cascade of extractors used by Trafilatura."
    # Trafilatura's main extractor
    postbody, temp_text, len_text = extract_content(cleaned_tree, options)

    # comparison with external extractors
    if not options.fast:
        postbody, temp_text, len_text = compare_extraction(
            cleaned_tree_backup,
            deepcopy(tree_backup),
            postbody,
            temp_text,
            len_text,
            options,
        )

    # rescue: baseline extraction on original/dirty tree
    if len_text < options.min_extracted_size and not options.focus == "precision":  # type: ignore[attr-defined]
        postbody, temp_text, len_text = baseline(deepcopy(tree_backup))
        LOGGER.debug("non-clean extracted length: %s (extraction)", len_text)

    return postbody, temp_text, len_text


def bare_extraction(
    filecontent: Any,
    url: Optional[str] = None,
    fast: bool = False,
    no_fallback: bool = False,
    favor_precision: bool = False,
    favor_recall: bool = False,
    include_comments: bool = True,
    output_format: str = "python",
    target_language: Optional[str] = None,
    include_tables: bool = True,
    include_images: bool = False,
    include_formatting: bool = False,
    preserve_space: bool = False,
    include_links: bool = False,
    deduplicate: bool = False,
    date_extraction_params: Optional[Dict[str, Any]] = None,
    with_metadata: bool = False,
    only_with_metadata: bool = False,
    max_tree_size: Optional[int] = None,
    url_blacklist: Optional[Set[str]] = None,
    author_blacklist: Optional[Set[str]] = None,
    as_dict: bool = False,
    prune_xpath: Optional[Any] = None,
    config: Any = DEFAULT_CONFIG,
    options: Optional[Extractor] = None,
) -> Optional[Union[Document, Dict[str, Any]]]:
    """Internal function for text extraction returning bare Python variables.

    Args:
        filecontent: HTML code as string.
        url: URL of the webpage.
        fast: Use faster heuristics and skip backup extraction.
        no_fallback: Will be deprecated, use "fast" instead.
        favor_precision: prefer less text but correct extraction.
        favor_recall: prefer more text even when unsure.
        include_comments: Extract comments along with the main text.
        output_format: Define an output format, Python being the default
            and the interest of this internal function.
            Other values: "csv", "html", "json", "markdown", "txt", "xml", and "xmltei".
        target_language: Define a language to discard invalid documents (ISO 639-1 format).
        include_tables: Take into account information within the HTML <table> element.
        include_images: Take images into account (experimental).
        include_formatting: Keep structural elements related to formatting
            (present in XML format, converted to markdown otherwise).
        preserve_space: Preserve space when formatting text.
        include_links: Keep links along with their targets (experimental).
        deduplicate: Remove duplicate segments and documents.
        date_extraction_params: Provide extraction parameters to htmldate as dict().
        with_metadata: Extract metadata fields and add them to the output.
        only_with_metadata: Only keep documents featuring all essential metadata
            (date, title, url).
        url_blacklist: Provide a blacklist of URLs as set() to filter out documents.
        author_blacklist: Provide a blacklist of Author Names as set() to filter out authors.
        as_dict: Will be deprecated, use the .as_dict() method of the document class.
        prune_xpath: Provide an XPath expression to prune the tree before extraction.
            can be str or list of str.
        config: Directly provide a configparser configuration.
        options: Directly provide a whole extractor configuration.

    Returns:
        A Python dict() containing all the extracted information or None.

    Raises:
        ValueError: Extraction problem.
    """

    # deprecations
    _check_deprecation(no_fallback=no_fallback, as_dict=as_dict, max_tree_size=max_tree_size)

    # regroup extraction options
    if not options or not isinstance(options, Extractor):
        options = Extractor(
            config=config,
            output_format=output_format,
            fast=fast,
            precision=favor_precision,
            recall=favor_recall,
            comments=include_comments,
            formatting=include_formatting,
            preserve_space=preserve_space,
            links=include_links,
            images=include_images,
            tables=include_tables,
            dedup=deduplicate,
            lang=target_language,
            url=url,
            with_metadata=with_metadata,
            only_with_metadata=only_with_metadata,
            author_blacklist=author_blacklist,
            url_blacklist=url_blacklist,
            date_params=date_extraction_params,
        )

    try:
        # load the HTML tree
        tree = load_html(filecontent)
        if tree is None:
            LOGGER.error("empty HTML tree: %s", url)
            raise ValueError

        # quick and dirty HTML lang check
        if options.lang and (options.fast or not LANGID_FLAG):
            if check_html_lang(tree, options.lang) is False:
                LOGGER.error("wrong HTML meta language: %s", options.source)
                raise ValueError

        # extract metadata if necessary
        if options.with_metadata:

            document = extract_metadata(
                tree,
                options.url,
                options.date_params,
                options.fast,
                options.author_blacklist,
            )

            # cut short if extracted URL in blacklist
            if document.url in options.url_blacklist:
                LOGGER.warning("blacklisted URL: %s", document.url)
                raise ValueError

            # cut short if core elements are missing
            if options.only_with_metadata and not (
                document.date and document.title and document.url
            ):
                LOGGER.error("no metadata: %s", options.source)
                raise ValueError

        else:
            document = Document()

        # prune all xpath expressions that user specified
        # no backup as this is unetre full control of the user
        if prune_xpath is not None:
            if isinstance(prune_xpath, str):
                prune_xpath = [prune_xpath]
            tree = prune_unwanted_nodes(tree, [XPath(x) for x in prune_xpath])

        # clean and backup for further processing
        cleaned_tree = tree_cleaning(copy(tree), options)
        cleaned_tree_backup = copy(cleaned_tree)

        # convert tags, the rest does not work without conversion
        cleaned_tree = convert_tags(cleaned_tree, options, options.url or document.url)

        # comments first, then remove
        if options.comments:
            commentsbody, temp_comments, len_comments, cleaned_tree = extract_comments(
                cleaned_tree, options
            )
        else:
            commentsbody, temp_comments, len_comments = Element("body"), "", 0
        if options.focus == "precision":
            cleaned_tree = prune_unwanted_nodes(cleaned_tree, REMOVE_COMMENTS_XPATH)

        postbody, temp_text, len_text = trafilatura_sequence(
            cleaned_tree, cleaned_tree_backup, tree, options
        )

        # tree size sanity check
        if options.max_tree_size:
            # strip tags
            if len(postbody) > options.max_tree_size:
                LOGGER.debug("output tree too long: %s", len(postbody))
                strip_tags(postbody, "hi")
            # still too long, raise an error
            if len(postbody) > options.max_tree_size:
                LOGGER.debug(
                    "output tree too long: %s, discarding %s",
                    len(postbody),
                    options.source,
                )
                raise ValueError
        # size checks
        if options.comments and len_comments < options.min_extracted_comm_size:  # type: ignore[attr-defined]
            LOGGER.debug("not enough comments: %s", options.source)
        if (
            len_text < options.min_output_size  # type: ignore[attr-defined]
            and len_comments < options.min_output_comm_size  # type: ignore[attr-defined]
        ):
            LOGGER.debug(
                "text and comments not long enough: %s %s %s",
                len_text,
                len_comments,
                options.source,
            )
            raise ValueError

        # check duplicates at body level
        if options.dedup and duplicate_test(postbody, options) is True:
            LOGGER.debug("discarding duplicate document: %s", options.source)
            raise ValueError

        # sanity check on language
        if options.lang:
            is_not_target_lang, document = language_filter(
                temp_text, temp_comments, options.lang, document
            )
            if is_not_target_lang is True:
                LOGGER.debug("wrong language: %s", options.source)
                raise ValueError

    except (TypeError, ValueError):
        LOGGER.warning("discarding data: %s", options.source)
        return None

    # special case: python variables
    if options.format == "python":
        document.text = xmltotxt(postbody, options.formatting)
        if options.comments:
            document.comments = xmltotxt(commentsbody, options.formatting)
            document.commentsbody = commentsbody
        document.raw_text = document.text
    else:
        document.raw_text, document.commentsbody = temp_text, commentsbody
    document.body = postbody

    return document if not as_dict else document.as_dict()


def extract(
    filecontent: Any,
    url: Optional[str] = None,
    record_id: Optional[str] = None,
    fast: bool = False,
    no_fallback: bool = False,
    favor_precision: bool = False,
    favor_recall: bool = False,
    include_comments: bool = True,
    output_format: str = "txt",
    tei_validation: bool = False,
    target_language: Optional[str] = None,
    include_tables: bool = True,
    include_images: bool = False,
    include_formatting: bool = False,
    preserve_space: bool = False,
    include_links: bool = False,
    deduplicate: bool = False,
    date_extraction_params: Optional[Dict[str, Any]] = None,
    with_metadata: bool = False,
    only_with_metadata: bool = False,
    max_tree_size: Optional[int] = None,
    url_blacklist: Optional[Set[str]] = None,
    author_blacklist: Optional[Set[str]] = None,
    settingsfile: Optional[str] = None,
    prune_xpath: Optional[Any] = None,
    config: Any = DEFAULT_CONFIG,
    options: Optional[Extractor] = None,
) -> Optional[str]:
    """Main function exposed by the package:
       Wrapper for text extraction and conversion to chosen output format.

    Args:
        filecontent: HTML code as string.
        url: URL of the webpage.
        record_id: Add an ID to the metadata.
        fast: Use faster heuristics and skip backup extraction.
        no_fallback: Will be deprecated, use "fast" instead.
        favor_precision: prefer less text but correct extraction.
        favor_recall: when unsure, prefer more text.
        include_comments: Extract comments along with the main text.
        output_format: Define an output format:
            "csv", "html", "json", "markdown", "txt", "xml", and "xmltei".
        tei_validation: Validate the XML-TEI output with respect to the TEI standard.
        target_language: Define a language to discard invalid documents (ISO 639-1 format).
        include_tables: Take into account information within the HTML <table> element.
        include_images: Take images into account (experimental).
        include_formatting: Keep structural elements related to formatting
            (only valuable if output_format is set to XML).
        preserve_space: Preserve space when formatting text.
        include_links: Keep links along with their targets (experimental).
        deduplicate: Remove duplicate segments and documents.
        date_extraction_params: Provide extraction parameters to htmldate as dict().
        with_metadata: Extract metadata fields and add them to the output.
        only_with_metadata: Only keep documents featuring all essential metadata
            (date, title, url).
        url_blacklist: Provide a blacklist of URLs as set() to filter out documents.
        author_blacklist: Provide a blacklist of Author Names as set() to filter out authors.
        settingsfile: Use a configuration file to override the standard settings.
        prune_xpath: Provide an XPath expression to prune the tree before extraction.
            can be str or list of str.
        config: Directly provide a configparser configuration.
        options: Directly provide a whole extractor configuration.

    Returns:
        A string in the desired format or None.

    """
    document = _internal_extraction(
        filecontent=filecontent,
        url=url,
        record_id=record_id,
        fast=fast,
        no_fallback=no_fallback,
        favor_precision=favor_precision,
        favor_recall=favor_recall,
        include_comments=include_comments,
        output_format=output_format,
        tei_validation=tei_validation,
        target_language=target_language,
        include_tables=include_tables,
        include_images=include_images,
        include_formatting=include_formatting,
        preserve_space=preserve_space,
        include_links=include_links,
        deduplicate=deduplicate,
        date_extraction_params=date_extraction_params,
        with_metadata=with_metadata,
        only_with_metadata=only_with_metadata,
        max_tree_size=max_tree_size,
        url_blacklist=url_blacklist,
        author_blacklist=author_blacklist,
        settingsfile=settingsfile,
        prune_xpath=prune_xpath,
        config=config,
        options=options)
    return document.text if document is not None else None


def extract_with_metadata(
    filecontent: Any,
    url: Optional[str] = None,
    record_id: Optional[str] = None,
    fast: bool = False,
    favor_precision: bool = False,
    favor_recall: bool = False,
    include_comments: bool = True,
    output_format: str = "txt",
    tei_validation: bool = False,
    target_language: Optional[str] = None,
    include_tables: bool = True,
    include_images: bool = False,
    include_formatting: bool = False,
    preserve_space: bool = False,
    include_links: bool = False,
    deduplicate: bool = False,
    date_extraction_params: Optional[Dict[str, Any]] = None,
    url_blacklist: Optional[Set[str]] = None,
    author_blacklist: Optional[Set[str]] = None,
    settingsfile: Optional[str] = None,
    prune_xpath: Optional[Any] = None,
    config: Any = DEFAULT_CONFIG,
    options: Optional[Extractor] = None,
) -> Optional[Document]:
    """Main function exposed by the package:
       Wrapper for text extraction and conversion to chosen output format.
       This method also returns document metadata.

    Args:
        filecontent: HTML code as string.
        url: URL of the webpage.
        record_id: Add an ID to the metadata.
        fast: Use faster heuristics and skip backup extraction.
        no_fallback: Will be deprecated, use "fast" instead.
        favor_precision: prefer less text but correct extraction.
        favor_recall: when unsure, prefer more text.
        include_comments: Extract comments along with the main text.
        output_format: Define an output format:
            "csv", "html", "json", "markdown", "txt", "xml", and "xmltei".
        tei_validation: Validate the XML-TEI output with respect to the TEI standard.
        target_language: Define a language to discard invalid documents (ISO 639-1 format).
        include_tables: Take into account information within the HTML <table> element.
        include_images: Take images into account (experimental).
        include_formatting: Keep structural elements related to formatting
            (only valuable if output_format is set to XML).
        preserve_space: Preserve space when formatting text.
        include_links: Keep links along with their targets (experimental).
        deduplicate: Remove duplicate segments and documents.
        date_extraction_params: Provide extraction parameters to htmldate as dict().
        url_blacklist: Provide a blacklist of URLs as set() to filter out documents.
        author_blacklist: Provide a blacklist of Author Names as set() to filter out authors.
        settingsfile: Use a configuration file to override the standard settings.
        prune_xpath: Provide an XPath expression to prune the tree before extraction.
            can be str or list of str.
        config: Directly provide a configparser configuration.
        options: Directly provide a whole extractor configuration.

    Returns:
        Document metadata with content string in the desired format or None.
    """
    return _internal_extraction(
        filecontent=filecontent,
        url=url,
        record_id=record_id,
        fast=fast,
        favor_precision=favor_precision,
        favor_recall=favor_recall,
        include_comments=include_comments,
        output_format=output_format,
        tei_validation=tei_validation,
        target_language=target_language,
        include_tables=include_tables,
        include_images=include_images,
        include_formatting=include_formatting,
        preserve_space=preserve_space,
        include_links=include_links,
        deduplicate=deduplicate,
        date_extraction_params=date_extraction_params,
        with_metadata=True,
        only_with_metadata=False,
        url_blacklist=url_blacklist,
        author_blacklist=author_blacklist,
        settingsfile=settingsfile,
        prune_xpath=prune_xpath,
        config=config,
        options=options)


def _check_deprecation(
        no_fallback: bool = False,
        as_dict: bool = False,
        max_tree_size: Optional[int] = None,
)-> None:
    '''Check deprecated or to-be-deprecated params'''
    if no_fallback:
        fast = no_fallback
        warnings.warn(
            '"no_fallback" will be deprecated in a future version, use "fast" instead',
            PendingDeprecationWarning
        )
    if as_dict:
        warnings.warn(
            '"as_dict" will be deprecated, use the .as_dict() method on bare_extraction results',
            PendingDeprecationWarning
        )
    if max_tree_size:
        raise ValueError("max_tree_size is deprecated, use settings.cfg file instead")


def _internal_extraction(
        filecontent: Any,
        url: Optional[str] = None,
        record_id: Optional[str] = None,
        fast: bool = False,
        no_fallback: bool = False,
        favor_precision: bool = False,
        favor_recall: bool = False,
        include_comments: bool = True,
        output_format: str = "txt",
        tei_validation: bool = False,
        target_language: Optional[str] = None,
        include_tables: bool = True,
        include_images: bool = False,
        include_formatting: bool = False,
        preserve_space: bool = False,
        include_links: bool = False,
        deduplicate: bool = False,
        date_extraction_params: Optional[Dict[str, Any]] = None,
        with_metadata: bool = False,
        only_with_metadata: bool = False,
        max_tree_size: Optional[int] = None,
        url_blacklist: Optional[Set[str]] = None,
        author_blacklist: Optional[Set[str]] = None,
        settingsfile: Optional[str] = None,
        prune_xpath: Optional[Any] = None,
        config: Any = DEFAULT_CONFIG,
        options: Optional[Extractor] = None,
) -> Optional[Document]:
    '''Internal method to do the extraction'''
    _check_deprecation(no_fallback=no_fallback, as_dict=False, max_tree_size=max_tree_size)

    # regroup extraction options
    if not options or not isinstance(options, Extractor):
        options = Extractor(
            config=use_config(settingsfile, config),
            output_format=output_format,
            fast=fast,
            precision=favor_precision,
            recall=favor_recall,
            comments=include_comments,
            formatting=include_formatting,
            preserve_space=preserve_space,
            links=include_links,
            images=include_images,
            tables=include_tables,
            dedup=deduplicate,
            lang=target_language,
            url=url,
            with_metadata=with_metadata,
            only_with_metadata=only_with_metadata,
            tei_validation=tei_validation,
            author_blacklist=author_blacklist,
            url_blacklist=url_blacklist,
            date_params=date_extraction_params,
        )

    # extraction
    document = bare_extraction(
        filecontent,
        options=options,
        as_dict=False,
        prune_xpath=prune_xpath,
    )

    # post-processing
    if not document or not isinstance(document, Document):
        return None

    if options.format not in TXT_FORMATS:
        # control output
        if options.format == "python":
            raise ValueError(
                "'python' format only usable in bare_extraction() function"
            )
        # add record ID to metadata
        document.id = record_id
        # calculate fingerprint
        if document.raw_text is not None:
            document.fingerprint = content_fingerprint(
                str(document.title) + " " + str(document.raw_text)
            )

    # return
    document.text = determine_returnstring(document, options)
    return document
