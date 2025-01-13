# pylint:disable-msg=C0301,E0611,I1101
"""
Functions to process nodes in HTML code.
"""

import logging

from copy import deepcopy
from typing import List, Optional, Tuple

from courlan.urlutils import fix_relative_urls, get_base_url
from lxml.etree import _Element, Element, SubElement, XPath, strip_tags, tostring
from lxml.html import HtmlElement

from .deduplication import duplicate_test
from .settings import (
    Document,
    Extractor,
    CUT_EMPTY_ELEMS,
    MANUALLY_CLEANED,
    MANUALLY_STRIPPED,
)
from .utils import textfilter, trim, is_image_element
from .xml import META_ATTRIBUTES, delete_element


LOGGER = logging.getLogger(__name__)

REND_TAG_MAPPING = {
    "em": "#i",
    "i": "#i",
    "b": "#b",
    "strong": "#b",
    "u": "#u",
    "kbd": "#t",
    "samp": "#t",
    "tt": "#t",
    "var": "#t",
    "sub": "#sub",
    "sup": "#sup",
}

HTML_TAG_MAPPING = {v: k for k, v in REND_TAG_MAPPING.items()}

PRESERVE_IMG_CLEANING = {"figure", "picture", "source"}

CODE_INDICATORS = ["{", "(\"", "('", "\n    "]


def tree_cleaning(tree: HtmlElement, options: Extractor) -> HtmlElement:
    "Prune the tree by discarding unwanted elements."
    # determine cleaning strategy, use lists to keep it deterministic
    cleaning_list, stripping_list = MANUALLY_CLEANED.copy(), MANUALLY_STRIPPED.copy()
    if not options.tables:
        cleaning_list.extend(["table", "td", "th", "tr"])
    else:
        # prevent this issue: https://github.com/adbar/trafilatura/issues/301
        for elem in tree.xpath(".//figure[descendant::table]"):
            elem.tag = "div"
    if options.images:
        # Many websites have <img> inside <figure> or <picture> or <source> tag
        cleaning_list = [e for e in cleaning_list if e not in PRESERVE_IMG_CLEANING]
        stripping_list.remove("img")

    # strip targeted elements
    strip_tags(tree, stripping_list)

    # prevent removal of paragraphs
    if options.focus == "recall" and tree.find(".//p") is not None:
        tcopy = deepcopy(tree)
        for expression in cleaning_list:
            for element in tree.iter(expression):
                delete_element(element)
        if tree.find(".//p") is None:
            tree = tcopy
    # delete targeted elements
    else:
        for expression in cleaning_list:
            for element in tree.iter(expression):
                delete_element(element)

    return prune_html(tree, options.focus)


def prune_html(tree: HtmlElement, focus: str = "balanced") -> HtmlElement:
    "Delete selected empty elements to save space and processing time."
    tails = focus != "precision"
    # .//comment() needed for date extraction
    for element in tree.xpath(".//processing-instruction()|.//*[not(node())]"):
        if element.tag in CUT_EMPTY_ELEMS:
            delete_element(element, keep_tail=tails)
    return tree


def prune_unwanted_nodes(
    tree: HtmlElement, nodelist: List[XPath], with_backup: bool = False
) -> HtmlElement:
    "Prune the HTML tree by removing unwanted sections."
    if with_backup:
        old_len = len(tree.text_content())  # ' '.join(tree.itertext())
        backup = deepcopy(tree)

    for expression in nodelist:
        for subtree in expression(tree):
            # preserve tail text from deletion
            if subtree.tail is not None:
                prev = subtree.getprevious()
                if prev is None:
                    prev = subtree.getparent()
                if prev is not None:
                    # There is a previous node, append text to its tail
                    prev.tail = (prev.tail or "") + " " + subtree.tail
            # remove the node
            delete_element(subtree)

    if with_backup:
        new_len = len(tree.text_content())
        # todo: adjust for recall and precision settings
        return tree if new_len > old_len / 7 else backup
    return tree


def collect_link_info(
    links_xpath: List[HtmlElement],
) -> Tuple[int, int, int, List[str]]:
    "Collect heuristics on link text"
    mylist = [e for e in (trim(elem.text_content()) for elem in links_xpath) if e]
    lengths = list(map(len, mylist))
    # longer strings impact recall in favor of precision
    shortelems = sum(1 for l in lengths if l < 10)
    return sum(lengths), len(mylist), shortelems, mylist


def link_density_test(
    element: HtmlElement, text: str, favor_precision: bool = False
) -> Tuple[bool, List[str]]:
    "Remove sections which are rich in links (probably boilerplate)"
    links_xpath = element.findall(".//ref")
    if not links_xpath:
        return False, []
    mylist: List[str] = []
    # shortcut
    if len(links_xpath) == 1:
        len_threshold = 10 if favor_precision else 100
        link_text = trim(links_xpath[0].text_content())
        if len(link_text) > len_threshold and len(link_text) > len(text) * 0.9:
            return True, []
    if element.tag == "p":
        limitlen = 60 if element.getnext() is None else 30
    else:
        if element.getnext() is None:
            limitlen = 300
        # elif re.search(r'[.?!:]', element.text_content()):
        #    limitlen, threshold = 150, 0.66
        else:
            limitlen = 100
    elemlen = len(text)
    if elemlen < limitlen:
        linklen, elemnum, shortelems, mylist = collect_link_info(links_xpath)
        if elemnum == 0:
            return True, mylist
        LOGGER.debug(
            "list link text/total: %s/%s – short elems/total: %s/%s",
            linklen,
            elemlen,
            shortelems,
            elemnum,
        )
        if linklen > elemlen * 0.8 or (elemnum > 1 and shortelems / elemnum > 0.8):
            return True, mylist
    return False, mylist


def link_density_test_tables(element: HtmlElement) -> bool:
    "Remove tables which are rich in links (probably boilerplate)."
    links_xpath = element.findall(".//ref")

    if not links_xpath:
        return False

    elemlen = len(trim(element.text_content()))
    if elemlen < 200:
        return False

    linklen, elemnum, _, _ = collect_link_info(links_xpath)
    if elemnum == 0:
        return True

    LOGGER.debug("table link text: %s / total: %s", linklen, elemlen)
    return linklen > 0.8 * elemlen if elemlen < 1000 else linklen > 0.5 * elemlen


def delete_by_link_density(
    subtree: HtmlElement,
    tagname: str,
    backtracking: bool = False,
    favor_precision: bool = False,
) -> HtmlElement:
    """Determine the link density of elements with respect to their length,
    and remove the elements identified as boilerplate."""
    deletions = []
    len_threshold = 200 if favor_precision else 100
    depth_threshold = 1 if favor_precision else 3

    for elem in subtree.iter(tagname):
        elemtext = trim(elem.text_content())
        result, templist = link_density_test(elem, elemtext, favor_precision)
        if result or (
            backtracking
            and templist
            and 0 < len(elemtext) < len_threshold
            and len(elem) >= depth_threshold
        ):
            deletions.append(elem)
            # else: # and not re.search(r'[?!.]', text):
            # print(elem.tag, templist)

    for elem in dict.fromkeys(deletions):
        delete_element(elem)

    return subtree


def handle_textnode(
    elem: _Element,
    options: Extractor,
    comments_fix: bool = True,
    preserve_spaces: bool = False,
) -> Optional[_Element]:
    "Convert, format, and probe potential text elements."
    if elem.tag == "graphic" and is_image_element(elem):
        return elem
    if elem.tag == "done" or (len(elem) == 0 and not elem.text and not elem.tail):
        return None

    # lb bypass
    if not comments_fix and elem.tag == "lb":
        if not preserve_spaces:
            elem.tail = trim(elem.tail) or None
        # if textfilter(elem) is True:
        #     return None
        # duplicate_test(subelement)?
        return elem

    if not elem.text and len(elem) == 0:
        # try the tail
        # LOGGER.debug('using tail for element %s', elem.tag)
        elem.text, elem.tail = elem.tail, ""
        # handle differently for br/lb
        if comments_fix and elem.tag == "lb":
            elem.tag = "p"

    # trim
    if not preserve_spaces:
        elem.text = trim(elem.text) or None
        if elem.tail:
            elem.tail = trim(elem.tail) or None

    # filter content
    # or not re.search(r'\w', element.text):  # text_content()?
    if (
        not elem.text
        and textfilter(elem)
        or (options.dedup and duplicate_test(elem, options))
    ):
        return None
    return elem


def process_node(elem: _Element, options: Extractor) -> Optional[_Element]:
    "Convert, format, and probe potential text elements (light format)."
    if elem.tag == "done" or (len(elem) == 0 and not elem.text and not elem.tail):
        return None

    # trim
    elem.text, elem.tail = trim(elem.text) or None, trim(elem.tail) or None

    # adapt content string
    if elem.tag != "lb" and not elem.text and elem.tail:
        elem.text, elem.tail = elem.tail, None

    # content checks
    if elem.text or elem.tail:
        if textfilter(elem) or (options.dedup and duplicate_test(elem, options)):
            return None

    return elem


def convert_lists(elem: _Element) -> None:
    "Convert <ul> and <ol> to <list> and underlying <li> elements to <item>."
    elem.set("rend", elem.tag)
    elem.tag = "list"
    i = 1
    for subelem in elem.iter("dd", "dt", "li"):
        # keep track of dd/dt items
        if subelem.tag in ("dd", "dt"):
            subelem.set("rend", f"{str(subelem.tag)}-{i}")
            # increment counter after <dd> in description list
            if subelem.tag == "dd":
                i += 1
        # convert elem tag (needs to happen after the rest)
        subelem.tag = "item"


def convert_quotes(elem: _Element) -> None:
    "Convert quoted elements while accounting for nested structures."
    code_flag = False
    if elem.tag == "pre":
        # detect if there could be code inside
        # pre with a single span is more likely to be code
        if len(elem) == 1 and elem[0].tag == "span":
            code_flag = True
        # find hljs elements to detect if it's code
        code_elems = elem.xpath(".//span[starts-with(@class,'hljs')]")
        if code_elems:
            code_flag = True
            for subelem in code_elems:
                subelem.attrib.clear()
        if elem.text and any([code_indicator in elem.text for code_indicator in CODE_INDICATORS]):
            code_flag = True
    elem.tag = "code" if code_flag else "quote"


def convert_headings(elem: _Element) -> None:
    "Add head tags and delete attributes."
    elem.attrib.clear()
    elem.set("rend", elem.tag)
    elem.tag = "head"


def convert_line_breaks(elem: _Element) -> None:
    "Convert <br> and <hr> to <lb>"
    elem.tag = "lb"


def convert_deletions(elem: _Element) -> None:
    'Convert <del>, <s>, <strike> to <del rend="overstrike">'
    elem.tag = "del"
    elem.set("rend", "overstrike")


def convert_details(elem: _Element) -> None:
    "Handle details and summary."
    elem.tag = "div"
    for subelem in elem.iter("summary"):
        subelem.tag = "head"


CONVERSIONS = {
    "dl": convert_lists,
    "ol": convert_lists,
    "ul": convert_lists,
    "h1": convert_headings,
    "h2": convert_headings,
    "h3": convert_headings,
    "h4": convert_headings,
    "h5": convert_headings,
    "h6": convert_headings,
    "br": convert_line_breaks,
    "hr": convert_line_breaks,
    "blockquote": convert_quotes,
    "pre": convert_quotes,
    "q": convert_quotes,
    "del": convert_deletions,
    "s": convert_deletions,
    "strike": convert_deletions,
    "details": convert_details,
    # wbr
}


def convert_link(elem: HtmlElement, base_url: Optional[str]) -> None:
    "Replace link tags and href attributes, delete the rest."
    elem.tag = "ref"
    target = elem.get("href")  # defaults to None
    elem.attrib.clear()
    if target:
        # convert relative URLs
        if base_url:
            target = fix_relative_urls(base_url, target)
        elem.set("target", target)


def convert_tags(
    tree: HtmlElement, options: Extractor, url: Optional[str] = None
) -> HtmlElement:
    "Simplify markup and convert relevant HTML tags to an XML standard."
    # delete links for faster processing
    if not options.links:
        xpath_expr = ".//*[self::div or self::li or self::p]//a"
        if options.tables:
            xpath_expr += "|.//table//a"
        # necessary for further detection
        for elem in tree.xpath(xpath_expr):
            elem.tag = "ref"
        # strip the rest
        strip_tags(tree, "a")
    else:
        # get base URL for converting relative URLs
        base_url = url and get_base_url(url)
        for elem in tree.iter("a", "ref"):
            convert_link(elem, base_url)

    if options.formatting:
        for elem in tree.iter(REND_TAG_MAPPING.keys()):
            elem.attrib.clear()
            elem.set("rend", REND_TAG_MAPPING[elem.tag])
            elem.tag = "hi"
    else:
        strip_tags(tree, *REND_TAG_MAPPING.keys())

    # iterate over all concerned elements
    for elem in tree.iter(CONVERSIONS.keys()):
        CONVERSIONS[elem.tag](elem)
    # images
    if options.images:
        for elem in tree.iter("img"):
            elem.tag = "graphic"

    return tree


HTML_CONVERSIONS = {
    "list": "ul",
    "item": "li",
    "code": "pre",
    "quote": "blockquote",
    "head": lambda elem: f"h{int(elem.get('rend', 'h3')[1:])}",
    "lb": "br",
    "img": "graphic",
    "ref": "a",
    "hi": lambda elem: HTML_TAG_MAPPING[elem.get("rend", "#i")],
}


def convert_to_html(tree: _Element) -> _Element:
    "Convert XML to simplified HTML."
    for elem in tree.iter(HTML_CONVERSIONS.keys()):
        conversion = HTML_CONVERSIONS[str(elem.tag)]
        # apply function or straight conversion
        if callable(conversion):
            elem.tag = conversion(elem)
        else:
            elem.tag = conversion  # type: ignore[assignment]
        # handle attributes
        if elem.tag == "a":
            elem.set("href", elem.attrib.pop("target", ""))
        else:
            elem.attrib.clear()
    tree.tag = "body"
    root = Element("html")
    root.append(tree)
    return root


def build_html_output(document: Document, with_metadata: bool = False) -> str:
    "Convert the document to HTML and return a string."
    html_tree = convert_to_html(document.body)

    if with_metadata:
        head = Element("head")
        for item in META_ATTRIBUTES:
            if value := getattr(document, item):
                SubElement(head, "meta", name=item, content=value)
        html_tree.insert(0, head)

    return tostring(html_tree, pretty_print=True, encoding="unicode").strip()
