# pylint:disable-msg=E0611,I1101
"""
All functions related to XML generation, processing and validation.
"""

import csv
import logging

from html import unescape
from importlib.metadata import version
from io import StringIO
from json import dumps as json_dumps
from pathlib import Path
from typing import List, Optional

from lxml.etree import (_Element, Element, SubElement, XMLParser,
                        fromstring, tostring, DTD)

from .settings import Document, Extractor
from .utils import is_in_table_cell, sanitize, sanitize_tree, text_chars_test


LOGGER = logging.getLogger(__name__)
PKG_VERSION = version("trafilatura")

# validation
TEI_SCHEMA = str(Path(__file__).parent / "data" / "tei_corpus.dtd")
TEI_VALID_TAGS = {'ab', 'body', 'cell', 'code', 'del', 'div', 'graphic', 'head', 'hi', \
                  'item', 'lb', 'list', 'p', 'quote', 'ref', 'row', 'table'}
TEI_VALID_ATTRS = {'rend', 'rendition', 'role', 'target', 'type'}
TEI_DTD = None  # to be downloaded later if necessary
TEI_REMOVE_TAIL = {"ab", "p"}
TEI_DIV_SIBLINGS = {"p", "list", "table", "quote", "ab"}

CONTROL_PARSER = XMLParser(remove_blank_text=True)

NEWLINE_ELEMS = {'graphic', 'head', 'lb', 'list', 'p', 'quote', 'row', 'table'}
SPECIAL_FORMATTING = {'code', 'del', 'head', 'hi', 'ref'}
WITH_ATTRIBUTES = {'cell', 'row', 'del', 'graphic', 'head', 'hi', 'item', 'list', 'ref'}
NESTING_WHITELIST = {"cell", "figure", "item", "note", "quote"}

META_ATTRIBUTES = [
    'sitename', 'title', 'author', 'date', 'url', 'hostname',
    'description', 'categories', 'tags', 'license', 'id',
    'fingerprint', 'language'
]

HI_FORMATTING = {'#b': '**', '#i': '*', '#u': '__', '#t': '`'}

MAX_TABLE_WIDTH = 1000


# https://github.com/lxml/lxml/blob/master/src/lxml/html/__init__.py
def delete_element(element: _Element, keep_tail: bool = True) -> None:
    """
    Removes this element from the tree, including its children and
    text. The tail text is joined to the previous element or parent.
    """
    parent = element.getparent()
    if parent is None:
        return

    if keep_tail and element.tail:
        previous = element.getprevious()
        if previous is None:
            parent.text = (parent.text or "") + element.tail
        else:
            previous.tail = (previous.tail or "") + element.tail

    parent.remove(element)


def merge_with_parent(element: _Element, include_formatting: bool = False) -> None:
    '''Merge element with its parent and convert formatting to markdown.'''
    parent = element.getparent()
    if parent is None:
        return

    full_text = replace_element_text(element, include_formatting)
    if element.tail is not None:
        full_text += element.tail

    previous = element.getprevious()
    if previous is not None:
        # There is a previous node, append text to its tail
        previous.tail = f'{previous.tail} {full_text}' if previous.tail else full_text
    elif parent.text is not None:
        parent.text = f'{parent.text} {full_text}'
    else:
        parent.text = full_text
    parent.remove(element)


def remove_empty_elements(tree: _Element) -> _Element:
    '''Remove text elements without text.'''
    for element in tree.iter('*'):  # 'head', 'hi', 'item', 'p'
        if len(element) == 0 and text_chars_test(element.text) is False and text_chars_test(element.tail) is False:
            parent = element.getparent()
            # not root element or element which is naturally empty
            # do not remove elements inside <code> to preserve formatting
            if parent is not None and element.tag != "graphic" and parent.tag != 'code':
                parent.remove(element)
    return tree


def strip_double_tags(tree: _Element) -> _Element:
    "Prevent nested tags among a fixed list of tags."
    for elem in reversed(tree.xpath(".//head | .//code | .//p")):
        for subelem in elem.iterdescendants("code", "head", "p"):
            if subelem.tag == elem.tag and subelem.getparent().tag not in NESTING_WHITELIST:
                merge_with_parent(subelem)
    return tree


def build_json_output(docmeta: Document, with_metadata: bool = True) -> str:
    '''Build JSON output based on extracted information'''
    if with_metadata:
        outputdict = {slot: getattr(docmeta, slot, None) for slot in docmeta.__slots__}
        outputdict.update({
            'source': outputdict.pop('url'),
            'source-hostname': outputdict.pop('sitename'),
            'excerpt': outputdict.pop('description'),
            'categories': ';'.join(outputdict.pop('categories') or []),
            'tags': ';'.join(outputdict.pop('tags') or []),
            'text': xmltotxt(outputdict.pop('body'), include_formatting=False),
        })
        commentsbody = outputdict.pop('commentsbody')
    else:
        outputdict = {'text': xmltotxt(docmeta.body, include_formatting=False)}
        commentsbody = docmeta.commentsbody

    outputdict['comments'] = xmltotxt(commentsbody, include_formatting=False)

    return json_dumps(outputdict, ensure_ascii=False)


def clean_attributes(tree: _Element) -> _Element:
    '''Remove unnecessary attributes.'''
    for elem in tree.iter('*'):
        if elem.tag not in WITH_ATTRIBUTES:
            elem.attrib.clear()
    return tree


def build_xml_output(docmeta: Document) -> _Element:
    '''Build XML output tree based on extracted information'''
    output = Element('doc')
    add_xml_meta(output, docmeta)
    docmeta.body.tag = 'main'

    # clean XML tree
    output.append(clean_attributes(docmeta.body))
    docmeta.commentsbody.tag = 'comments'
    output.append(clean_attributes(docmeta.commentsbody))

    return output


def control_xml_output(document: Document, options: Extractor) -> str:
    '''Make sure the XML output is conform and valid if required'''
    strip_double_tags(document.body)
    remove_empty_elements(document.body)

    func = build_xml_output if options.format == "xml" else build_tei_output
    output_tree = func(document)

    output_tree = sanitize_tree(output_tree)
    # necessary for cleaning
    output_tree = fromstring(tostring(output_tree, encoding='unicode'), CONTROL_PARSER)

    # validate
    if options.format == 'xmltei' and options.tei_validation:
        LOGGER.debug('TEI validation result: %s %s', validate_tei(output_tree), options.source)

    return tostring(output_tree, pretty_print=True, encoding='unicode').strip()


def add_xml_meta(output: _Element, docmeta: Document) -> None:
    '''Add extracted metadata to the XML output tree'''
    for attribute in META_ATTRIBUTES:
        value = getattr(docmeta, attribute, None)
        if value:
            output.set(attribute, value if isinstance(value, str) else ';'.join(value))


def build_tei_output(docmeta: Document) -> _Element:
    '''Build TEI-XML output tree based on extracted information'''
    # build TEI tree
    output = write_teitree(docmeta)
    # filter output (strip unwanted elements), just in case
    # check and repair
    output = check_tei(output, docmeta.url)
    return output


def check_tei(xmldoc: _Element, url: Optional[str]) -> _Element:
    '''Check if the resulting XML file is conform and scrub remaining tags'''
    # convert head tags
    for elem in xmldoc.iter('head'):
        elem.tag = 'ab'
        elem.set('type', 'header')
        parent = elem.getparent()
        if parent is None:
            continue
        if len(elem) > 0:
            new_elem = _tei_handle_complex_head(elem)
            parent.replace(elem, new_elem)
            elem = new_elem
        if parent.tag == "p":
            _move_element_one_level_up(elem)
    # convert <lb/> when child of <div> to <p>
    for elem in xmldoc.findall(".//text/body//div/lb"):
        if elem.tail and elem.tail.strip():
            elem.tag, elem.text, elem.tail = 'p', elem.tail, None
    # look for elements that are not valid
    for elem in xmldoc.findall('.//text/body//*'):
        # check elements
        if elem.tag not in TEI_VALID_TAGS:
            # disable warnings for chosen categories
            # if element.tag not in ('div', 'span'):
            LOGGER.warning('not a TEI element, removing: %s %s', elem.tag, url)
            merge_with_parent(elem)
            continue
        if elem.tag in TEI_REMOVE_TAIL:
            _handle_unwanted_tails(elem)
        elif elem.tag == "div":
            _handle_text_content_of_div_nodes(elem)
            _wrap_unwanted_siblings_of_div(elem)
            #if len(elem) == 0:
            #    elem.getparent().remove(elem)
        # check attributes
        for attribute in [a for a in elem.attrib if a not in TEI_VALID_ATTRS]:
            LOGGER.warning('not a valid TEI attribute, removing: %s in %s %s', attribute, elem.tag, url)
            elem.attrib.pop(attribute)
    return xmldoc


def validate_tei(xmldoc: _Element) -> bool:
    '''Check if an XML document is conform to the guidelines of the Text Encoding Initiative'''
    global TEI_DTD

    if TEI_DTD is None:
        # https://tei-c.org/release/xml/tei/custom/schema/dtd/tei_corpus.dtd
        TEI_DTD = DTD(TEI_SCHEMA)

    result = TEI_DTD.validate(xmldoc)
    if result is False:
        LOGGER.warning('not a valid TEI document: %s', TEI_DTD.error_log.last_error)

    return result


def replace_element_text(element: _Element, include_formatting: bool) -> str:
    elem_text = element.text or ""
    "Determine element text based on just the text of the element. One must deal with the tail separately."
    # handle formatting: convert to markdown
    if include_formatting and element.text:
        if element.tag == "head":
            try:
                number = int(element.get("rend")[1])  # type: ignore[index]
            except (TypeError, ValueError):
                number = 2
            elem_text = f'{"#" * number} {elem_text}'
        elif element.tag == "del":
            elem_text = f"~~{elem_text}~~"
        elif element.tag == "hi":
            rend = element.get("rend")
            if rend in HI_FORMATTING:
                elem_text = f"{HI_FORMATTING[rend]}{elem_text}{HI_FORMATTING[rend]}"
        elif element.tag == "code":
            if "\n" in elem_text or element.xpath(".//lb"):  # Handle <br> inside <code>
                # Convert <br> to \n within code blocks
                for lb in element.xpath(".//lb"):
                    elem_text = f"{elem_text}\n{lb.tail}"
                    lb.getparent().remove(lb)
                elem_text = f"```\n{elem_text}\n```\n"
            else:
                elem_text = f"`{elem_text}`"
    # handle links
    if element.tag == "ref":
        if elem_text:
            link_text = f"[{elem_text}]"
            target = element.get("target")
            if target:
                elem_text = f"{link_text}({target})"
            else:
                LOGGER.warning("missing link attribute: %s %s'", elem_text, element.attrib)
                elem_text = link_text
        else:
            LOGGER.warning("empty link: %s %s", elem_text, element.attrib)
    # cells
    if element.tag == "cell":
        elem_text = elem_text.strip()

        if elem_text:
            elem_text = f"{elem_text} "
    # lists
    elif element.tag == "item" and elem_text:
        elem_text = f"- {elem_text}\n"
    return elem_text


def process_element(element: _Element, returnlist: List[str], include_formatting: bool) -> None:
    "Recursively convert a LXML element and its children to a flattened string representation."
    if element.tag == 'cell' and element.getprevious() is None:
        returnlist.append('| ')

    if element.text:
        # this is the text that comes before the first child
        returnlist.append(replace_element_text(element, include_formatting))

    if element.tail and element.tag != 'graphic' and is_in_table_cell(element):
        # if element is in table cell, append tail after element text when element is not graphic since we deal with
        # graphic tail alone, textless elements like lb should be processed here too, otherwise process tail at the end
        returnlist.append(element.tail.strip())

    for child in element:
        process_element(child, returnlist, include_formatting)

    if not element.text:
        if element.tag == "graphic":
            # add source, default to ''
            text = f'{element.get("title", "")} {element.get("alt", "")}'
            returnlist.append(f'![{text.strip()}]({element.get("src", "")})')

            if element.tail:
                returnlist.append(f' {element.tail.strip()}')
        # newlines for textless elements
        elif element.tag in NEWLINE_ELEMS:
            # add line after table head
            if element.tag == "row":
                cell_count = len(element.xpath(".//cell"))
                # restrict columns to a maximum of 1000
                span_info = element.get("colspan") or element.get("span")
                if not span_info or not span_info.isdigit():
                    max_span = 1
                else:
                    max_span = min(int(span_info), MAX_TABLE_WIDTH)
                # row ended so draw extra empty cells to match max_span
                if cell_count < max_span:
                    returnlist.append(f'{"|" * (max_span - cell_count)}\n')
                # if this is a head row, draw the separator below
                if element.xpath("./cell[@role='head']"):
                    returnlist.append(f'\n|{"---|" * max_span}\n')
            else:
                returnlist.append("\n")
        elif element.tag != "cell":
            # cells still need to append vertical bars
            # but nothing more to do with other textless elements
            return

    # Process text

    # Common elements (Now processes end-tag logic correctly)
    if element.tag in NEWLINE_ELEMS and not element.xpath("ancestor::cell"):
        # spacing hack
        returnlist.append("\n\u2424\n" if include_formatting and element.tag != 'row' else "\n")
    elif element.tag == "cell":
        returnlist.append(" | ")
    elif element.tag not in SPECIAL_FORMATTING:
        returnlist.append(" ")

    # this is text that comes after the closing tag, so it should be after any NEWLINE_ELEMS
    if element.tail and not is_in_table_cell(element):
        returnlist.append(element.tail)


def xmltotxt(xmloutput: Optional[_Element], include_formatting: bool) -> str:
    "Convert to plain text format and optionally preserve formatting as markdown."
    if xmloutput is None:
        return ""

    returnlist: List[str] = []

    process_element(xmloutput, returnlist, include_formatting)

    return unescape(sanitize("".join(returnlist)) or "")


def xmltocsv(document: Document, include_formatting: bool, *, delim: str = "\t", null: str = "null") -> str:
    "Convert the internal XML document representation to a CSV string."
    # preprocessing
    posttext = xmltotxt(document.body, include_formatting) or null
    commentstext = xmltotxt(document.commentsbody, include_formatting) or null

    # output config
    output = StringIO()
    outputwriter = csv.writer(output, delimiter=delim, quoting=csv.QUOTE_MINIMAL)

    # organize fields
    outputwriter.writerow([d if d else null for d in (
        document.url,
        document.id,
        document.fingerprint,
        document.hostname,
        document.title,
        document.image,
        document.date,
        posttext,
        commentstext,
        document.license,
        document.pagetype
    )])
    return output.getvalue()


def write_teitree(docmeta: Document) -> _Element:
    '''Bundle the extracted post and comments into a TEI tree'''
    teidoc = Element('TEI', xmlns='http://www.tei-c.org/ns/1.0')
    write_fullheader(teidoc, docmeta)
    textelem = SubElement(teidoc, 'text')
    textbody = SubElement(textelem, 'body')
    # post
    postbody = clean_attributes(docmeta.body)
    postbody.tag = 'div'
    postbody.set('type', 'entry')
    textbody.append(postbody)
    # comments
    commentsbody = clean_attributes(docmeta.commentsbody)
    commentsbody.tag = 'div'
    commentsbody.set('type', 'comments')
    textbody.append(commentsbody)
    return teidoc


def _define_publisher_string(docmeta: Document) -> str:
    '''Construct a publisher string to include in TEI header'''
    if docmeta.hostname and docmeta.sitename:
        publisher = f'{docmeta.sitename.strip()} ({docmeta.hostname})'
    else:
        publisher = docmeta.hostname or docmeta.sitename or 'N/A'
        if LOGGER.isEnabledFor(logging.WARNING) and publisher == 'N/A':
            LOGGER.warning('no publisher for URL %s', docmeta.url)
    return publisher


def write_fullheader(teidoc: _Element, docmeta: Document) -> _Element:
    '''Write TEI header based on gathered metadata'''
    # todo: add language info
    header = SubElement(teidoc, 'teiHeader')
    filedesc = SubElement(header, 'fileDesc')
    bib_titlestmt = SubElement(filedesc, 'titleStmt')
    SubElement(bib_titlestmt, 'title', type='main').text = docmeta.title
    if docmeta.author:
        SubElement(bib_titlestmt, 'author').text = docmeta.author

    publicationstmt_a = SubElement(filedesc, 'publicationStmt')
    publisher_string = _define_publisher_string(docmeta)
    # license, if applicable
    if docmeta.license:
        SubElement(publicationstmt_a, 'publisher').text = publisher_string
        availability = SubElement(publicationstmt_a, 'availability')
        SubElement(availability, 'p').text = docmeta.license
    # insert an empty paragraph for conformity
    else:
        SubElement(publicationstmt_a, 'p')

    notesstmt = SubElement(filedesc, 'notesStmt')
    if docmeta.id:
        SubElement(notesstmt, 'note', type='id').text = docmeta.id
    SubElement(notesstmt, 'note', type='fingerprint').text = docmeta.fingerprint

    sourcedesc = SubElement(filedesc, 'sourceDesc')
    source_bibl = SubElement(sourcedesc, 'bibl')

    sigle = ', '.join(filter(None, [docmeta.sitename, docmeta.date]))
    if not sigle:
        LOGGER.warning('no sigle for URL %s', docmeta.url)
    source_bibl.text = ', '.join(filter(None, [docmeta.title, sigle]))
    SubElement(sourcedesc, 'bibl', type='sigle').text = sigle

    biblfull = SubElement(sourcedesc, 'biblFull')
    bib_titlestmt = SubElement(biblfull, 'titleStmt')
    SubElement(bib_titlestmt, 'title', type='main').text = docmeta.title
    if docmeta.author:
        SubElement(bib_titlestmt, 'author').text = docmeta.author

    publicationstmt = SubElement(biblfull, 'publicationStmt')
    SubElement(publicationstmt, 'publisher').text = publisher_string
    if docmeta.url:
        SubElement(publicationstmt, 'ptr', type='URL', target=docmeta.url)
    SubElement(publicationstmt, 'date').text = docmeta.date

    profiledesc = SubElement(header, 'profileDesc')
    abstract = SubElement(profiledesc, 'abstract')
    SubElement(abstract, 'p').text = docmeta.description

    if docmeta.categories or docmeta.tags:
        textclass = SubElement(profiledesc, 'textClass')
        keywords = SubElement(textclass, 'keywords')
        if docmeta.categories:
            SubElement(keywords, 'term', type='categories').text = ','.join(docmeta.categories)
        if docmeta.tags:
            SubElement(keywords, 'term', type='tags').text = ','.join(docmeta.tags)

    creation = SubElement(profiledesc, 'creation')
    SubElement(creation, 'date', type="download").text = docmeta.filedate

    encodingdesc = SubElement(header, 'encodingDesc')
    appinfo = SubElement(encodingdesc, 'appInfo')
    application = SubElement(appinfo, 'application', version=PKG_VERSION, ident='Trafilatura')
    SubElement(application, 'label').text = 'Trafilatura'
    SubElement(application, 'ptr', target='https://github.com/adbar/trafilatura')

    return header


def _handle_text_content_of_div_nodes(element: _Element) -> None:
    "Wrap loose text in <div> within <p> elements for TEI conformity."
    if element.text and element.text.strip():
        if len(element) > 0 and element[0].tag == "p":
            element[0].text = f'{element.text} {element[0].text or ""}'.strip()
        else:
            new_child = Element("p")
            new_child.text = element.text
            element.insert(0, new_child)
        element.text = None

    if element.tail and element.tail.strip():
        if len(element) > 0 and element[-1].tag == "p":
            element[-1].text = f'{element[-1].text or ""} {element.tail}'.strip()
        else:
            new_child = Element("p")
            new_child.text = element.tail
            element.append(new_child)
        element.tail = None


def _handle_unwanted_tails(element: _Element) -> None:
    "Handle tail on p and ab elements"
    element.tail = element.tail.strip() if element.tail else None
    if not element.tail:
        return

    if element.tag == "p":
        element.text = " ".join(filter(None, [element.text, element.tail]))
    else:
        new_sibling = Element('p')
        new_sibling.text = element.tail
        parent = element.getparent()
        if parent is not None:
            parent.insert(parent.index(element) + 1 , new_sibling)
    element.tail = None


def _tei_handle_complex_head(element: _Element) -> _Element:
    "Convert certain child elements to <ab> and <lb>."
    new_element = Element('ab', attrib=element.attrib)
    new_element.text = element.text.strip() if element.text else None
    for child in element.iterchildren():
        if child.tag == 'p':
            if len(new_element) > 0 or new_element.text:
                # add <lb> if <ab> has no children or last tail contains text
                if len(new_element) == 0 or new_element[-1].tail:
                    SubElement(new_element, 'lb')
                new_element[-1].tail = child.text
            else:
                new_element.text = child.text
        else:
            new_element.append(child)
    tail = element.tail.strip() if element.tail else None
    if tail:
        new_element.tail = tail
    return new_element


def _wrap_unwanted_siblings_of_div(div_element: _Element) -> None:
    "Wrap unwanted siblings of a div element in a new div element."
    new_sibling = Element("div")
    new_sibling_index = None
    parent = div_element.getparent()
    if parent is None:
        return
    # check siblings after target element
    for sibling in div_element.itersiblings():
        if sibling.tag == "div":
            break
        if sibling.tag in TEI_DIV_SIBLINGS:
            new_sibling_index = new_sibling_index or parent.index(sibling)
            new_sibling.append(sibling)
        # some elements (e.g. <lb/>) can appear next to div, but
        # order of elements should be kept, thus add and reset new_sibling
        else:
            if new_sibling_index and len(new_sibling) > 0:
                parent.insert(new_sibling_index, new_sibling)
                new_sibling = Element("div")
                new_sibling_index = None
    if new_sibling_index and len(new_sibling) != 0:
        parent.insert(new_sibling_index, new_sibling)


def _move_element_one_level_up(element: _Element) -> None:
    """
    Fix TEI compatibility issues by moving certain p-elems up in the XML tree.
    There is always a n+2 nesting for p-elements with the minimal structure ./TEI/text/body/p
    """
    parent = element.getparent()
    grand_parent = parent.getparent() if parent is not None else None
    if parent is None or grand_parent is None:
        return

    new_elem = Element("p")
    new_elem.extend(list(element.itersiblings()))

    grand_parent.insert(grand_parent.index(parent) + 1, element)

    tail = element.tail.strip() if element.tail else None
    if tail:
        new_elem.text = tail
        element.tail = None

    tail = parent.tail.strip() if parent.tail else None
    if tail:
        new_elem.tail = tail
        parent.tail = None

    if len(new_elem) > 0 or new_elem.text or new_elem.tail:
        grand_parent.insert(grand_parent.index(element) + 1, new_elem)

    if len(parent) == 0 and not parent.text:
        grand_parent.remove(parent)
