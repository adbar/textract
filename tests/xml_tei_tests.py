"""
Test for transformation to TEI.
"""
from copy import copy

from lxml.etree import Element, SubElement, XMLParser, fromstring, tostring

from trafilatura.metadata import Document
from trafilatura.xml import (check_tei, replace_element_text, write_fullheader,
                             _handle_unwanted_tails, _move_element_one_level_up,
                             _wrap_unwanted_siblings_of_div)


def test_sanity():
    element = Element("p")
    element.text = "test"
    backup = copy(element)
    _handle_unwanted_tails(element)
    assert element.text == backup.text
    element.tail = "tail"
    backup = copy(element)
    _handle_unwanted_tails(element)
    assert element.text == "test tail"
    div_elem = Element("div")
    div_elem.append(backup)
    _handle_unwanted_tails(backup)
    assert tostring(div_elem) == b"<div><p>test tail</p></div>"

    new_elem = Element("div")
    _wrap_unwanted_siblings_of_div(new_elem)
    assert new_elem is not None

    p_elem = SubElement(new_elem, "p")
    _move_element_one_level_up(p_elem)
    assert tostring(new_elem) == b"<div><p/></div>"

    head = Element("head")
    result = check_tei(head, "")
    assert result == head


def test_publisher_added_before_availability_in_publicationStmt():
    # add publisher string
    teidoc = Element("TEI", xmlns="http://www.tei-c.org/ns/1.0")
    metadata = Document()
    metadata.sitename = "The Publisher"
    metadata.license = "CC BY-SA 4.0"
    metadata.categories = metadata.tags = ["cat"]
    header = write_fullheader(teidoc, metadata)
    publicationstmt = header.find(".//{*}fileDesc/{*}publicationStmt")
    assert [child.tag for child in publicationstmt.getchildren()] == [
        "publisher",
        "availability",
    ]
    assert publicationstmt[0].text == "The Publisher"

    teidoc = Element("TEI", xmlns="http://www.tei-c.org/ns/1.0")
    metadata = Document()
    metadata.hostname = "example.org"
    metadata.license = "CC BY-SA 4.0"
    metadata.categories = metadata.tags = ["cat"]
    header = write_fullheader(teidoc, metadata)
    publicationstmt = header.find(".//{*}fileDesc/{*}publicationStmt")
    assert [child.tag for child in publicationstmt.getchildren()] == [
        "publisher",
        "availability",
    ]
    assert publicationstmt[0].text == "example.org"

    teidoc = Element("TEI", xmlns="http://www.tei-c.org/ns/1.0")
    metadata = Document()
    metadata.hostname = "example.org"
    metadata.sitename = "Example"
    metadata.license = "CC BY-SA 4.0"
    metadata.categories = metadata.tags = ["cat"]
    header = write_fullheader(teidoc, metadata)
    publicationstmt = header.find(".//{*}fileDesc/{*}publicationStmt")
    assert [child.tag for child in publicationstmt.getchildren()] == [
        "publisher",
        "availability",
    ]
    assert publicationstmt[0].text == "Example (example.org)"
    # no publisher, add "N/A"
    teidoc = Element("TEI", xmlns="http://www.tei-c.org/ns/1.0")
    metadata = Document()
    metadata.categories = metadata.tags = ["cat"]
    metadata.license = "CC BY-SA 4.0"
    header = write_fullheader(teidoc, metadata)
    publicationstmt = header.find(".//{*}fileDesc/{*}publicationStmt")
    assert [child.tag for child in publicationstmt.getchildren()] == [
        "publisher",
        "availability",
    ]
    assert publicationstmt[0].text == "N/A"
    # no license, add nothing
    teidoc = Element("TEI", xmlns="http://www.tei-c.org/ns/1.0")
    metadata = Document()
    metadata.categories = metadata.tags = ["cat"]
    header = write_fullheader(teidoc, metadata)
    publicationstmt = header.find(".//{*}fileDesc/{*}publicationStmt")
    assert [child.tag for child in publicationstmt.getchildren()] == ["p"]


def test_unwanted_siblings_of_div_removed():
    xml_doc = fromstring("<TEI><text><body><div><div><p>text1</p></div><p>text2</p></div></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    result =  [elem.tag for elem in cleaned.find(".//div").iter()]
    expected = ["div", "div", "p", "div", "p"]
    assert result == expected
    result_str = tostring(cleaned.find(".//body"), encoding="unicode")
    expected_str = "<body><div><div><p>text1</p></div><div><p>text2</p></div></div></body>"
    assert result_str == expected_str
    xml_doc = fromstring("<TEI><text><body><div><div/><list><item>text</item></list></div></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [elem.tag for elem in cleaned.find(".//div").iter()]
    expected = ["div", "div", "div", "list", "item"]
    assert result == expected
    xml_doc = fromstring("<TEI><text><body><div><div/><table><row><cell>text</cell></row></table></div></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [elem.tag for elem in cleaned.find(".//div").iter()]
    expected = ["div", "div", "div", "table", "row", "cell"]
    assert result == expected
    xml_doc = fromstring("<TEI><text><body><div><p>text1</p><div/><div/><p>text2</p></div></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = tostring(cleaned.find(".//body"), encoding="unicode")
    expected = "<body><div><p>text1</p><div/><div/><div><p>text2</p></div></div></body>"
    assert result == expected
    xml_doc = fromstring("<TEI><text><body><div><div><p>text1</p></div><p>text2</p><p>text3</p></div></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [elem.tag for elem in cleaned.find(".//div").iter()]
    expected = ["div", "div", "p", "div", "p", "p"]
    assert result == expected
    xml_doc = fromstring("<TEI><text><body><div><p>text1</p><div/><p>text2</p><div/><p>text3</p></div></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [elem.tag for elem in cleaned.find(".//div").iter()]
    expected = ["div", "p", "div", "div", "p", "div", "div", "p"]
    assert result == expected
    xml_doc = fromstring("<TEI><text><body><div><p>text1</p><div/><p>text2</p><div/><list/></div></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [elem.tag for elem in cleaned.find(".//div").iter()]
    expected = ["div", "p", "div", "div", "p", "div", "div", "list"]
    assert result == expected
    xml_doc = fromstring("<TEI><text><body><div><p/><div/><p>text1</p><ab/><p>text2</p></div></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    result_str = tostring(cleaned.find(".//body"), encoding="unicode")
    expected_str = "<body><div><p/><div/><div><p>text1</p><ab/><p>text2</p></div></div></body>"
    assert result_str == expected_str
    xml_doc = fromstring("<TEI><text><body><div><div/><ab/></div></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    result_str = tostring(cleaned.find(".//body"), encoding="unicode")
    expected_str = "<body><div><div/><div><ab/></div></div></body>"
    assert result_str == expected_str
    xml_doc = fromstring("<TEI><text><body><div><div/><quote>text</quote></div></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [elem.tag for elem in cleaned.find(".//div").iter()]
    expected = ["div", "div", "div", "quote"]
    assert result == expected
    xml_doc = fromstring("<TEI><text><body><div><div/><lb/></div></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [elem.tag for elem in cleaned.find(".//div").iter()]
    assert result == ["div", "div", "lb"]
    xml_doc = fromstring("<TEI><text><body><div><div/><ab/></div></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [elem.tag for elem in cleaned.find(".//div").iter()]
    assert result == ["div", "div", "div", "ab"]
    xml_doc = fromstring("<TEI><text><body><div><div><p>text1</p></div><list/><ul><li>text2</li></ul></div></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    result_str = tostring(cleaned.find(".//body"), encoding="unicode")
    expected_str = "<body><div><div><p>text1</p></div><div><list/></div></div></body>"
    assert result_str == expected_str
    xml_doc = fromstring("<TEI><text><body><div><div><p>text1</p></div><ul><li>text2</li></ul><list/></div></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    result_str = tostring(cleaned.find(".//body"), encoding="unicode")
    expected_str = "<body><div><div><p>text1</p></div><div><list/></div></div></body>"
    assert result_str == expected_str
    xml_str = "<TEI><text><body><div><p/><div/></div></body></text></TEI>"
    result = tostring(check_tei(fromstring(xml_str), "fake_url"), encoding="unicode")
    assert result == xml_str
    xml_doc = fromstring("<TEI><text><body><div><div/><lb/>tail</div></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [elem.tag for elem in cleaned.find(".//div").iter()]
    assert result == ["div", "div", "div", "p"]


def test_tail_on_p_like_elements_removed():
    xml_doc = fromstring(
        """
    <TEI><text><body>
      <div>
        <p>text</p>former link
        <p>more text</p>former span
        <p>even more text</p>another span
      </div>
    </body></text></TEI>""")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [(el.text, el.tail) for el in cleaned.iter('p')]
    assert result == [("text former link", None), ("more text former span", None), ("even more text another span", None)]
    xml_doc = fromstring("<TEI><text><body><div><head>title</head>some text<p>article</p></div></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [(elem.tag, elem.text, elem.tail) for elem in cleaned.find(".//div").iterdescendants()]
    assert result == [("ab", "title", None), ("p", "some text", None), ("p", "article", None)]
    xml_doc = fromstring("<TEI><text><body><div><ab>title</ab>tail<p>more text</p></div></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [(elem.tag, elem.text, elem.tail) for elem in cleaned.find(".//div").iterdescendants()]
    assert result == [("ab", "title", None), ("p", "tail", None), ("p", "more text", None)]
    xml_doc = fromstring("<TEI><text><body><div><p>text</p><lb/>tail</div></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [(elem.tag, elem.text, elem.tail) for elem in cleaned.find(".//div").iterdescendants()]
    assert result == [("p", "text", None), ("p", "tail", None)]
    xml_doc = fromstring("<TEI><text><body><div><p/>tail</div></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [(elem.tag, elem.text, elem.tail) for elem in cleaned.find(".//p").iter()]
    assert result == [("p", "tail", None)]
    xml_doc = fromstring("<TEI><text><body><div><p/>tail1<ab/>tail2<ab/>tail3</div></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [elem.text for elem in cleaned.iter() if elem.text]
    assert result == ["tail1", "tail2", "tail3"]


def test_head_with_children_converted_to_ab():
    xml_doc = fromstring("<text><head>heading</head><p>some text</p></text>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [
        (child.tag, child.text) if child.text is not None else child.tag
        for child in cleaned.iter()
    ]
    assert result == ["text", ("ab", "heading"), ("p", "some text")]
    xml_doc = fromstring("<text><head><p>text</p></head></text>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [(child.tag, child.text, child.tail) for child in cleaned.iter()]
    assert result == [("text", None, None), ("ab", "text", None)]
    head_with_mulitple_p = fromstring(
        "<text><head><p>first</p><p>second</p><p>third</p></head></text>"
    )
    cleaned = check_tei(head_with_mulitple_p, "fake_url")
    result = [(child.tag, child.text, child.tail) for child in cleaned.iter()]
    assert result == [
        ("text", None, None),
        ("ab", "first", None),
        ("lb", None, "second"),
        ("lb", None, "third"),
    ]
    xml_with_complex_head = fromstring(
        "<text><head><p>first</p><list><item>text</item></list><p>second</p><p>third</p></head></text>"
    )
    cleaned = check_tei(xml_with_complex_head, "fake_url")
    result = [(child.tag, child.text, child.tail) for child in cleaned.iter()]
    assert result == [
        ("text", None, None),
        ("ab", "first", None),
        ("list", None, "second"),
        ("item", "text", None),
        ("lb", None, "third"),
    ]
    xml_doc = fromstring("<text><head><list><item>text1</item></list><p>text2</p></head></text>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [(child.tag, child.text, child.tail) for child in cleaned.iter()]
    assert result == [
        ("text", None, None),
        ("ab", None, None),
        ("list", None, "text2"),
        ("item", "text1", None)
    ]
    xml_doc = fromstring("<text><head>heading</head><p>some text</p></text>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = cleaned[0].attrib
    assert result == {"type":"header"}
    xml_doc = fromstring("<text><head rend='h3'>heading</head><p>some text</p></text>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = cleaned[0].attrib
    assert result == {"type":"header", "rend":"h3"}
    tei_doc = fromstring("<TEI><teiheader/><text><body><head><p>text</p></head></body></text></TEI>")
    cleaned = check_tei(tei_doc, "fake_url")
    result = cleaned.find(".//ab")
    assert result.text == 'text'
    assert result.attrib == {"type":"header"}
    xml_doc = fromstring("<text><body><head>text1<p>text2</p></head></body></text>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [(child.tag, child.text, child.tail) for child in cleaned.find(".//ab").iter()]
    assert result == [("ab", "text1", None), ("lb", None, "text2")]
    xml_doc = fromstring(
    """<text>
            <body>
                <head>text1
                    <p>text2</p>
                </head>
            </body>
        </text>
    """
    )
    cleaned = check_tei(xml_doc, "fake_url")
    result = [(child.tag, child.text, child.tail) for child in cleaned.find(".//ab").iter()]
    assert result == [("ab", "text1", None), ("lb", None, "text2")]
    xml_doc = fromstring("<TEI><text><body><head><list><item>text1</item></list><p>text2</p></head>tail</body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [(child.tag, child.text, child.tail) for child in cleaned.find(".//body").iter()]
    assert result == [
        ("body", None, None),
        ("ab", None, None),
        ("list", None, "text2"),
        ("item", "text1", None),
        ("p", "tail", None)
    ]


def test_ab_with_p_parent_resolved():
    parser = XMLParser(remove_blank_text=True)
    xml_doc = fromstring("<text><p><head>text1</head></p></text>")
    cleaned = check_tei(xml_doc, "fake_url")
    assert cleaned.find(".//ab") is not None and cleaned.find(".//p") is None
    xml_doc = fromstring("<body><p>text1<head>text2</head></p></body>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = cleaned.find(".//ab")
    assert result.getparent().tag == "body" and result.text == "text2"
    xml_doc = fromstring("<TEI><text><body><p><head>text1</head></p>text2</body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    assert cleaned.find(".//ab").text == "text1" and cleaned.find(".//p").text == "text2"
    xml_doc = fromstring("<text><p><head rend='h3'>text</head></p></text>")
    cleaned = check_tei(xml_doc, "fake_url")
    assert cleaned.find("ab").attrib == {"type":"header", "rend":"h3"}
    xml_doc = fromstring("<text><p><head>text1</head><list/><head>text2</head></p></text>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [(elem.tag, elem.text, elem.tail) for elem in cleaned.iter()]
    assert result == [
        ("text", None, None),
        ("ab", "text1", None),
        ("p", None, None),
        ("list", None, None),
        ("ab", "text2", None),

    ]
    xml_doc = fromstring("<TEI><text><body><p><head>text1</head>text2</p></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    assert cleaned.find(".//p").text == "text2"
    xml_doc = fromstring("<TEI><text><body><p>text0<head>text1</head>text2</p></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    assert cleaned.find(".//ab").getnext().text == "text2"
    xml_doc = fromstring("<TEI><text><body><p>text0<list/><head>text1</head>text2</p>text3</body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    assert "text2" in tostring(cleaned, encoding="unicode") and cleaned.find(".//p/list") is not None
    xml_doc = fromstring("""
    <TEI>
      <text><body>
        <p>text1<head>text2</head>text3
          <head>text4</head>text5
        </p>
      </body></text>
    </TEI>"""
    )
    cleaned = check_tei(xml_doc, "fake_url")
    result = [(elem.tag, elem.text, elem.tail if elem.tail is None else elem.tail.strip()) for elem in xml_doc.iter(["p", "ab"])]
    assert result == [
        ("p", "text1", ""),
        ("ab", "text2", None),
        ("p", "text3", None),
        ("ab", "text4", None),
        ("p", "text5", None),
    ]
    xml_doc = fromstring("""
    <TEI>
      <text>
        <body>
          <p>text0<head>text1</head>
            <list>
              <item>text2</item>
            </list>
            <head>text3</head>text4
          </p>
        </body>
      </text>
    </TEI>"""
    )
    cleaned = check_tei(xml_doc, "fake_url")
    result = [(elem.tag, elem.text, elem.tail if elem.tail is None else elem.tail.strip()) for elem in xml_doc.iter(["p", "ab"])]
    assert result == [
        ("p", "text0", ""),
        ("ab", "text1", ""),
        ("p", None, None),
        ("ab", "text3", None),
        ("p", "text4", None),
    ]
    xml_doc = fromstring("<TEI><text><body><p>text0<head>text1</head></p>text2</body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [(elem.tag, elem.text, elem.tail) for elem in xml_doc.iter(["p", "ab"])]
    assert result == [
        ("p", "text0", None),
        ("ab", "text1", None),
        ("p", "text2", None),
    ]
    xml_doc = fromstring("<TEI><text><body><p>text1<head>text2</head>text3<head>text4</head></p></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [(elem.tag, elem.text, elem.tail) for elem in cleaned.iter(["p", "ab"])]
    assert result == [
        ("p", "text1", None),
        ("ab", "text2", None),
        ("p", "text3", None),
        ("ab", "text4", None),
    ]
    xml_doc = fromstring("<text><head>text1</head><p>text2<head>text3</head></p></text>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [(elem.tag, elem.text, elem.tail) for elem in cleaned]
    assert result == [
        ("ab", "text1", None),
        ("p", "text2", None),
        ("ab", "text3", None),
    ]
    xml_doc = fromstring("<text><p>text1<head>text2</head></p><head>text3</head></text>")
    cleaned = check_tei(xml_doc, "fake_url")
    result = [(elem.tag, elem.text, elem.tail) for elem in cleaned]
    assert result == [
        ("p", "text1", None),
        ("ab", "text2", None),
        ("ab", "text3", None),
    ]
    xml_doc = fromstring(
        """
        <text>
            <head>text1<p>text2</p></head>
            <p>text3<head>text4</head></p>
        </text>""",
        parser=parser
    )
    cleaned = check_tei(xml_doc, "fake_url")
    result = [(elem.tag, elem.text, elem.tail) for elem in cleaned.iter()]
    assert result == [
        ("text", None, None),
        ("ab", "text1", None),
        ("lb", None, "text2"),
        ("p", "text3", None),
        ("ab", "text4", None),
    ]
    xml_doc = fromstring(
        """
        <TEI>
        <text>
          <body>
            <p>text1<head>
                    <list>
                        <item>text2</item>
                    </list>
                </head>
            text3
            </p>
          </body>
        </text>
        </TEI>
        """,
        parser=parser
    )
    cleaned = check_tei(xml_doc, "fake_url")
    result = [(elem.tag, elem.text, elem.tail) for elem in cleaned.iter(["p", "ab", "item"])]
    assert result ==  [
        ("p", "text1", None),
        ("ab", None, None),
        ("item", "text2", None),
        ("p", "text3", None),
    ]


def test_handling_of_text_content_in_div():
    xml_doc = fromstring("<TEI><text><body><div>text<head/></div></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    assert cleaned.find(".//p").text == "text"
    xml_doc = fromstring("<TEI><text><body><div>text1<p>text2</p></div></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    assert cleaned.find(".//p").text == "text1 text2"
    xml_doc = fromstring("<TEI><text><body><div>text<p/></div></body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    assert cleaned.find(".//p").text == "text"
    xml_doc = fromstring("<TEI><text><body><div><p/></div>tail</body></text></TEI>")
    cleaned = check_tei(xml_doc, "fake_url")
    assert cleaned.find(".//p").text == "tail"


def test_replace_element_text():
    elem = Element("head")
    elem.text = "Title"
    elem.set("rend", "h1")
    assert replace_element_text(elem, True) == "# Title"

    elem = Element("hi")
    elem.text = "Text"
    elem.set("rend", "#b")
    assert replace_element_text(elem, True) == "**Text**"

    elem = Element("item")
    elem.text = "Test text"
    elem.tag = "item"
    assert replace_element_text(elem, True) == "- Test text "

    elem = Element("ref")
    elem.text = "Link"
    elem.set("target", "https://example.com")
    assert replace_element_text(elem, True) == "[Link](https://example.com)"

    elem = Element("ref")
    elem.text = "Link"
    assert replace_element_text(elem, True) == "[Link]"


if __name__ == "__main__":
    test_publisher_added_before_availability_in_publicationStmt()
    test_unwanted_siblings_of_div_removed()
    test_tail_on_p_like_elements_removed()
    test_head_with_children_converted_to_ab()
    test_ab_with_p_parent_resolved()
    test_replace_element_text()
