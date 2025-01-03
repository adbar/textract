# pylint:disable-msg=I1101,W1401
"""
Unit tests for the trafilatura library.
"""

import logging
import sys
import time

from copy import copy
from os import path

import pytest

from lxml import etree, html


try:
    from cchardet import detect
except ImportError:
    from charset_normalizer import detect

import trafilatura.htmlprocessing
from trafilatura import bare_extraction, extract, extract_with_metadata, xml
from trafilatura.core import Extractor
from trafilatura.external import sanitize_tree, try_justext, try_readability
from trafilatura.main_extractor import (handle_formatting, handle_image,
                                        handle_lists, handle_paragraphs, handle_quotes,
                                        handle_table, handle_textelem)
from trafilatura.meta import reset_caches
from trafilatura.metadata import Document
from trafilatura.readability_lxml import is_probably_readerable
from trafilatura.settings import DEFAULT_CONFIG, TAG_CATALOG, use_config
from trafilatura.utils import (LANGID_FLAG, detect_encoding, is_dubious_html, is_image_file,
                               language_classifier, load_html, normalize_unicode,
                               repair_faulty_html, sanitize, textfilter, trim)

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


TEST_DIR = path.abspath(path.dirname(__file__))
RESOURCES_DIR = path.join(TEST_DIR, 'resources')
SAMPLE_META = Document()

ZERO_CONFIG = DEFAULT_CONFIG
ZERO_CONFIG['DEFAULT']['MIN_OUTPUT_SIZE'] = '0'
ZERO_CONFIG['DEFAULT']['MIN_EXTRACTED_SIZE'] = '0'

NEW_CONFIG = use_config(filename=path.join(RESOURCES_DIR, 'newsettings.cfg'))

MOCK_PAGES = {
'http://exotic_tags': 'exotic_tags.html',
}

DEFAULT_OPTIONS = Extractor()


def load_mock_page(url, xml_flag=False, langcheck=None, tei_output=False):
    '''load mock page from samples'''
    try:
        with open(path.join(TEST_DIR, "resources", MOCK_PAGES[url]), "r", encoding="utf-8") as inputf:
            htmlstring = inputf.read()
    # encoding/windows fix for the tests
    except UnicodeDecodeError:
        # read as binary
        with open(path.join(TEST_DIR, "resources", MOCK_PAGES[url]), "rb") as inputf:
            htmlbinary = inputf.read()
        guessed_encoding = detect(htmlbinary)['encoding']
        if guessed_encoding is not None:
            try:
                htmlstring = htmlbinary.decode(guessed_encoding)
            except UnicodeDecodeError:
                htmlstring = htmlbinary
        else:
            print('Encoding error')
    if xml_flag:
        output_format = 'xml'
    elif tei_output:
        output_format = 'xmltei'
    else:
        output_format = 'txt'
    return extract(
               htmlstring, url,
               record_id='0000',
               output_format=output_format,
               target_language=langcheck
           )


def test_trim():
    '''test string trimming'''
    assert trim('	Test  ') == 'Test'
    assert trim('\t\tTest  Test\r\n') == 'Test Test'
    my_elem = etree.Element('body')
    my_elem.text = 'Test Text'
    assert textfilter(my_elem) is False
    # my_elem.text = 'Tags: Arbeit, Urlaub'
    my_elem.text = 'Instagram'
    assert textfilter(my_elem) is True
    my_elem.text = '\t\t'
    assert textfilter(my_elem) is True
    # sanitize logic
    assert sanitize(None) is None
    # non-breaking spaces
    print(sanitize('Test&nbsp;Text'))
    assert sanitize('Test&nbsp;Text') == 'Test Text'
    # clear cache
    # reset caches: examine_date_elements used above
    old_values = trim.cache_info()
    reset_caches()
    assert trim.cache_info() != old_values


def test_input():
    '''test if loaded strings/trees are handled properly'''
    teststring = "高山云雾出好茶".encode("utf-8")
    assert detect_encoding(teststring) == ["utf-8"]
    teststring = "高山云雾出好茶".encode("gb18030")
    assert "gb18030" in detect_encoding(teststring)
    assert "gb18030" in detect_encoding(teststring*1000)

    assert is_dubious_html("This is a string.") is True

    htmlstring = "<!DOCTYPE html PUBLIC />\n<html></html>"
    beginning = htmlstring[:50].lower()
    assert repair_faulty_html(htmlstring, beginning) == "\n<html></html>"

    htmlstring = "<html>\n</html>"
    beginning = htmlstring[:50].lower()
    assert repair_faulty_html(htmlstring, beginning) == htmlstring

    htmlstring = "<html/>\n</html>"
    beginning = htmlstring[:50].lower()
    assert repair_faulty_html(htmlstring, beginning) == "<html>\n</html>"

    htmlstring = '<!DOCTYPE html>\n<html lang="en-US"/>\n<head/>\n<body/>\n</html>'
    beginning = htmlstring[:50].lower()
    assert (
        repair_faulty_html(htmlstring, beginning)
        == '<!DOCTYPE html>\n<html lang="en-US">\n<head/>\n<body/>\n</html>'
    )

    htmlstring = '<!DOCTYPE html><html><head></head><body>Foo <br/> Bar</body></html>'
    beginning = htmlstring[:50].lower()
    assert (
        repair_faulty_html(htmlstring, beginning)
        == '<!DOCTYPE html><html><head></head><body>Foo <br/> Bar</body></html>\n'
    )

    with pytest.raises(TypeError) as err:
        assert load_html(123) is None
    assert 'incompatible' in str(err.value)

    assert load_html('<html><body>ÄÖÜ</body></html>') is not None
    assert load_html(b'<html><body>\x2f\x2e\x9f</body></html>') is not None
    assert load_html('<html><body>\x2f\x2e\x9f</body></html>'.encode('latin-1')) is not None
    #assert load_html(b'0'*int(10e3)) is None
    # old: with pytest.raises(TypeError) as err:
    assert extract(None, 'url', '0000', target_language=None) is None
    # GZip
    with open(path.join(RESOURCES_DIR, 'webpage.html.gz'), 'rb') as gzfile:
        myinput = gzfile.read()
    assert 'Long story short,' in extract(myinput)

    # unicode normalization
    assert normalize_unicode('A\u0308ffin') != 'A\u0308ffin'
    testresult = extract('<html><body><p>A\u0308ffin</p></body></html>', config=ZERO_CONFIG)
    assert testresult != 'A\u0308ffin' and testresult == 'Äffin'
    options = Extractor(source="test\udcc3this")
    assert options.source == "test?this"

    # output format
    assert extract('<html><body><p>ABC</p></body></html>', output_format="xml") is not None
    with pytest.raises(AttributeError):
        assert extract('<html><body><p>ABC</p></body></html>', output_format="xyz") is not None
    assert bare_extraction('<html><body><p>ABC</p></body></html>', output_format="python") is not None
    with pytest.raises(AttributeError):
        assert bare_extraction('<html><body><p>ABC</p></body></html>', output_format="xyz") is not None

    # text elements
    elem = etree.Element("p")
    elem.text = "text"
    assert handle_textelem(elem, [], DEFAULT_OPTIONS) is not None
    elem = etree.Element("unexpected")
    elem.text = "text"
    assert handle_textelem(elem, [], DEFAULT_OPTIONS) is None


def test_xmltocsv():
    doc = Document()
    doc.body = etree.fromstring('<xml/>')
    doc.commentsbody = etree.fromstring('<xml/>')
    assert xml.xmltocsv(doc, False) == 'null\tnull\tnull\tnull\tnull\tnull\tnull\tnull\tnull\tnull\tnull\r\n'

    doc.title = 'Test title'
    doc.url = 'https://example.org'
    doc.hostname = 'example.org'
    doc.id = '1'
    doc.license = 'CC BY-SA'
    doc.image = 'https://example.org/image.jpg'
    doc.pagetype = 'article'
    text = 'Test text'
    comments = 'Test comment'
    doc.body = etree.fromstring(f'<p>{text}</p>')
    doc.commentsbody = etree.fromstring(f'<p>{comments}</p>')

    target = 'https://example.org\t1\tnull\texample.org\tTest title\thttps://example.org/image.jpg\tnull\tTest text\tTest comment\tCC BY-SA\tarticle\r\n'

    assert xml.xmltocsv(doc, False) == target

    mystring = '<html><body><p>ÄÄÄÄÄÄÄÄÄÄÄÄÄÄ</p></body></html>'
    assert extract(mystring, output_format='csv', config=ZERO_CONFIG) is not None
    assert extract(mystring, output_format='csv', include_comments=False, config=ZERO_CONFIG).endswith('\tnull\r\n')


def test_tojson():
    # test json
    mystring = '<html><body><p>ÄÄÄÄÄÄÄÄÄÄÄÄÄÄ</p></body></html>'
    result = extract(mystring, output_format='json', config=ZERO_CONFIG)
    assert "Ä" in result and result.endswith('}')
    result = extract(mystring, output_format='json', config=ZERO_CONFIG, with_metadata=True)
    assert result.endswith('}') and '"fingerprint":' in result and '"language":' in result
    assert extract(mystring, output_format='json', include_comments=False, config=ZERO_CONFIG).endswith('}')


def test_python_output():
    # bare extraction for python
    mystring = '<html><body><p>ÄÄÄÄÄÄÄÄÄÄÄÄÄÄ</p></body></html>'
    result = bare_extraction(mystring, config=ZERO_CONFIG)
    dict_result = result.as_dict()
    assert isinstance(dict_result, dict) and len(dict_result) == 21


def test_exotic_tags(xmloutput=False):
    options = DEFAULT_OPTIONS
    options._add_config(ZERO_CONFIG)
    # cover some edge cases with a specially crafted file
    result = load_mock_page('http://exotic_tags', xml_flag=xmloutput, tei_output=True)
    assert 'Teletype text' in result and 'My new car is silver.' in result
    filepath = path.join(TEST_DIR, 'resources', 'exotic_tags_tei.html')
    with open(filepath, "r", encoding="utf-8") as f:
        content = etree.fromstring(f.read())
    res = xml.check_tei(content, 'http://dummy')
    assert etree.tostring(res).startswith(b'<html>\n<text>\n<body>\n<div>\n\n<hi rend="uppercase">Hello</hi>\n<p>Teletype text</p>')
    # misformed HTML declaration
    htmlstring = '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" 2012"http://www.w3.org/TR/html4/loose.dtd"><html><head></head><body><p>ABC</p></body></html>'
    # outputs '012"http://www.w3.org/TR/html4/loose.dtd">\nABC'
    assert 'ABC' in extract(htmlstring, config=ZERO_CONFIG)
    # quotes
    assert handle_quotes(etree.Element('quote'), options) is None
    assert handle_table(etree.Element('table'), TAG_CATALOG, options) is None
    # p within p
    element, second = etree.Element('p'), etree.Element('p')
    element.text, second.text = '1st part.', '2nd part.'
    element.append(second)
    # delete last <lb>
    element.append(etree.Element('lb'))
    converted = handle_paragraphs(element, ['p'], options)
    assert etree.tostring(converted) == b'<p>1st part. 2nd part.</p>'
    # naked div with <lb>
    assert '1.\n2.\n3.' in extract('<html><body><main><div>1.<br/>2.<br/>3.<br/></div></main></body></html>', fast=True, config=ZERO_CONFIG)
    # HTML5: <details>
    htmlstring = '<html><body><article><details><summary>Epcot Center</summary><p>Epcot is a theme park at Walt Disney World Resort featuring exciting attractions, international pavilions, award-winning fireworks and seasonal special events.</p></details></article></body></html>'
    my_result = extract(htmlstring, fast=True, config=ZERO_CONFIG)
    assert 'Epcot Center' in my_result and 'award-winning fireworks' in my_result
    my_result = extract(htmlstring, fast=False, config=ZERO_CONFIG)
    assert 'Epcot Center' in my_result and 'award-winning fireworks' in my_result

    # edge cases
    htmlstring = '''<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8">
    <title>A weird bug</title>
  </head>
  <body>
      <div>
        <h1>Lorem ipsum dolor sit amet, consectetur adipiscing elit.</h1>
        <h2>Sed et interdum lectus.</h2>
        <p>Quisque molestie nunc eu arcu condimentum fringilla.</p>
        <!-- strong can be changed to b, em, i, u, or kbd -->
        <strong><a></a></strong>
        <h2>Aliquam eget interdum elit, id posuere ipsum.</h2>
        <p>Phasellus lectus erat, hendrerit sed tortor ac, dignissim vehicula metus.<br/></p>
      </div>
  </body>
</html>'''
    assert extract(htmlstring, include_formatting=True, include_links=True, include_images=True) is not None

    htmlstring = '''<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8">
    <title>A weird bug</title>
  </head>
  <body>
    <div id="content">
      <h1>A header</h1>
      <h2>Very specific bug so odd</h2>
      <h3>Nested header</h3>
      <p>Some "hyphenated-word quote" followed by a bit more text line.</p>
      <em><p>em improperly wrapping p here</p></em>
      <p>Text here<br/></p>
      <h3>More articles</h3>
    </div>
  </body>
</html>'''
    common = {"include_formatting": True, "include_links": True, "include_images": True}
    params = [
        common, {**common, "favor_precision": True}, {**common, "favor_recall": True}
    ]
    for p in params:
        result = extract(htmlstring, **p)
        assert "em improperly wrapping p here" in result and result.endswith("Text here")

    # comments
    assert extract('<html><body><article><p>text</p><div class="comments"><p>comment</p></div></article></body></html>', include_comments=True, fast=True, config=ZERO_CONFIG).endswith("\ncomment")


def test_formatting():
    '''Test HTML formatting conversion and extraction'''
    options = DEFAULT_OPTIONS

    # trailing <lb>
    my_document = html.fromstring('<html><body><p>This here is the text.<br/></p></body></html>')
    my_result = extract(my_document, output_format='xml', config=ZERO_CONFIG)
    assert 'lb' not in my_result
    # simple formatting
    my_document = html.fromstring('<html><body><p><b>This here is in bold font.</b></p></body></html>')
    my_result = extract(my_document, output_format='xml', include_formatting=True, config=ZERO_CONFIG)
    assert '<hi rend="#b">This here is in bold font.</hi>' in my_result
    # titles as markdown
    my_string = '<html><body><article><h3>Title</h3><p><b>This here is in bold font.</b></p></article></body></html>'
    my_document = html.fromstring(my_string)
    my_result = extract(my_document, output_format='txt', include_formatting=True, config=ZERO_CONFIG)
    assert my_result == '### Title\n\n**This here is in bold font.**'
    assert extract(my_string, output_format='markdown', config=ZERO_CONFIG) == my_result
    assert '<hi rend="#b">' in etree.tostring(bare_extraction(my_string, output_format='markdown', config=ZERO_CONFIG).body, encoding="unicode")

    meta_string = '<html><head><title>Test</title></head><body><p>ABC.</p></body></html>'
    meta_result = extract(meta_string, output_format='markdown', config=ZERO_CONFIG, with_metadata=True)
    assert " ".join(meta_result.split()) == "--- title: Test --- ABC."

    # space between paragraphs
    my_document = html.fromstring('<html><body><article><h3>Title</h3><p>Paragraph 1</p><p>Paragraph 2</p></article></body></html>')
    my_result = extract(my_document, output_format='txt', include_formatting=True, config=ZERO_CONFIG)
    assert my_result.endswith('Paragraph 1\n\nParagraph 2')

    # code sections
    my_document = html.fromstring('<html><body><article><h3>Title</h3><p>Here is a code sample:</p><code>import trafilatura</code></p></article></body></html>')
    my_result = extract(my_document, output_format='txt', include_formatting=True, config=ZERO_CONFIG)
    assert my_result == """### Title

Here is a code sample:

`import trafilatura`"""
    my_document = html.fromstring('<html><body><article><h3>Title</h3><p>Here is a code sample:</p><code>import trafilatura\ntrafilatura.extract("")</code></p></article></body></html>')
    my_result = extract(my_document, output_format='txt', include_formatting=True, config=ZERO_CONFIG)
    assert my_result == """### Title

Here is a code sample:

```
import trafilatura
trafilatura.extract("")
```"""

    # nested
    my_document = html.fromstring('<html><body><p><b>This here is in bold and <i>italic</i> font.</b></p></body></html>')
    my_result = extract(my_document, output_format='xml', include_formatting=True, config=ZERO_CONFIG)
    assert '<hi rend="#b">This here is in bold and italic font.</hi>' in my_result
    # empty
    my_document = html.fromstring('<html><body><p><b><i></i></b></p></body></html>')
    my_result = extract(my_document, output_format='xml', include_formatting=True, config=ZERO_CONFIG)
    assert '<main/>' in my_result
    # wild div
    my_document = html.fromstring('<html><body><article><div><strong>Wild text</strong></div></article></body></html>')
    my_result = extract(my_document, output_format='xml', include_formatting=True, config=ZERO_CONFIG)
    assert '<p>' in my_result and '<hi rend="#b">Wild text</hi>' in my_result  # no rend so far
    my_document = html.fromstring('<html><body><article><div><strong>Wild text</strong></div></article></body></html>')
    my_result = extract(my_document, config=ZERO_CONFIG)
    assert my_result == 'Wild text'
    # links
    doc = html.fromstring('<html><body><p><a href="">Link text</a></p></body></html>')
    my_result = extract(doc, config=ZERO_CONFIG)
    assert my_result == 'Link text'
    # line-breaks
    doc = html.fromstring('<html><body><p><br/></p></body></html>')
    my_result = extract(doc, config=ZERO_CONFIG)
    assert my_result == ''
    doc = html.fromstring('<html><body><p><br/>Here is the text.</p></body></html>')
    my_result = extract(doc, config=ZERO_CONFIG)
    assert my_result == 'Here is the text.'
    # handle formatting tails
    element = etree.Element("hi")
    element.text = 'Here is the text.'
    element.tail = 'And a tail.'
    options._add_config(ZERO_CONFIG)
    converted = handle_formatting(element, options)
    assert etree.tostring(converted) == b'<p><hi>Here is the text.</hi>And a tail.</p>'
    # empty elements
    my_document = html.fromstring('<html><body><div>\t\n</div><div>There is text here.</div></body></html>')
    my_result = extract(my_document, output_format='xml', config=ZERO_CONFIG)
    assert '<main>\n    <p>There is text here.</p>\n  </main>' in my_result
    # lists with links
    my_document = html.fromstring('<html><body><article><ul><li>Number 1</li><li>Number <a href="test.html">2</a></li><li>Number 3</li><p>Test</p></article></body></html>')
    my_result = extract(my_document, output_format='xml', include_links=True, config=ZERO_CONFIG)
    assert '<item>Number <ref target="test.html">2</ref></item>' in my_result

    my_document = html.fromstring("""<html><body><article>
        <ul>
            <li>Number 0</li>
            <li>Number <a href="test.html">1</a></li>
            <li><a href="test.html">Number 2</a> n2</li>
            <li>Number 3</li>
            <li><p>Number 4</p> n4</li>
        </ul>
        <p>Test</p></article></body></html>
    """)
    my_result = extract(my_document, output_format='markdown', include_links=True, config=ZERO_CONFIG)
    assert my_result == '- Number 0\n- Number [1](test.html)\n- [Number 2](test.html) n2\n- Number 3\n- Number 4 n4\n\nTest'
    # XML and Markdown formatting within <p>-tag
    my_document = html.fromstring('<html><body><p><b>bold</b>, <i>italics</i>, <tt>tt</tt>, <strike>deleted</strike>, <u>underlined</u>, <a href="test.html">link</a> and additional text to bypass detection.</p></body></html>')
    my_result = extract(copy(my_document), fast=True, include_formatting=False, config=ZERO_CONFIG)
    assert my_result == 'bold, italics, tt, deleted, underlined, link and additional text to bypass detection.'

    my_result = extract(copy(my_document), fast=True, include_formatting=True, config=ZERO_CONFIG)
    assert my_result == '**bold**, *italics*, `tt`, ~~deleted~~, __underlined__, link and additional text to bypass detection.'

    my_result = extract(copy(my_document), fast=True, include_links=True, include_formatting=True, config=ZERO_CONFIG)
    assert my_result == '**bold**, *italics*, `tt`, ~~deleted~~, __underlined__, [link](test.html) and additional text to bypass detection.'

    my_result = extract(copy(my_document), output_format='xml', fast=True, include_formatting=True, config=ZERO_CONFIG)
    assert '<p><hi rend="#b">bold</hi>, <hi rend="#i">italics</hi>, <hi rend="#t">tt</hi>, <del>deleted</del>, <hi rend="#u">underlined</hi>, link and additional text to bypass detection.</p>' in my_result
    assert 'rend="#b"' in my_result and 'rend="#i"' in my_result and 'rend="#t"' in my_result and 'rend="#u"' in my_result and '<del>' in my_result

    my_result = extract(copy(my_document), output_format='xml', include_formatting=True, include_links=True, fast=True, config=ZERO_CONFIG)
    assert '<p><hi rend="#b">bold</hi>, <hi rend="#i">italics</hi>, <hi rend="#t">tt</hi>, <del>deleted</del>, <hi rend="#u">underlined</hi>, <ref target="test.html">link</ref> and additional text to bypass detection.</p>' in my_result
    my_result = extract(my_document, output_format='txt', fast=True, include_formatting=True, config=ZERO_CONFIG)
    assert my_result == '**bold**, *italics*, `tt`, ~~deleted~~, __underlined__, link and additional text to bypass detection.'

    # double <p>-elems
    # could be solved by keeping the elements instead of reconstructing them
    my_document = html.fromstring('<html><body><p>AAA, <p>BBB</p>, CCC.</p></body></html>')
    my_result = extract(my_document, output_format='xml', include_formatting=True, include_links=True, fast=True, config=ZERO_CONFIG)
    assert 'AAA' in my_result and 'BBB' in my_result and 'CCC' in my_result

    # line-break following formatting
    my_document = html.fromstring('<html><body><article><p><strong>Staff Review of the Financial Situation</strong><br>Domestic financial conditions remained accommodative over the intermeeting period.</p></article></body></html>')
    my_result = extract(my_document, output_format='txt', fast=True, config=ZERO_CONFIG)
    assert my_result == 'Staff Review of the Financial Situation\nDomestic financial conditions remained accommodative over the intermeeting period.'
    # title with formatting
    my_document = html.fromstring('<html><body><article><h4 id="1theinoperator">1) The <code>in</code> Operator</h4><p>The easiest way to check if a Python string contains a substring is to use the <code>in</code> operator. The <code>in</code> operator is used to check data structures for membership in Python. It returns a Boolean (either <code>True</code> or <code>False</code>) and can be used as follows:</p></article></body></html>')
    my_result = extract(my_document, output_format='xml', fast=True, include_formatting=True, config=ZERO_CONFIG)
    assert '<head rend="h4">1) The <code>in</code> Operator</head>' in my_result and '<p>The easiest way to check if a Python string contains a substring is to use the <code>in</code> operator. The <code>in</code> operator is used to check data structures for membership in Python. It returns a Boolean (either <code>True</code> or <code>False</code>) and can be used as follows:</p>' in my_result

    my_document = html.fromstring("""
    <html><head><body><article>python code below:
    <pre><code>
def test:
    print('hello')
    print('world')
    </code></pre>
    </article></body></html> 
    """)
    my_result = extract(my_document, output_format='markdown', include_formatting=True)
    assert "python code below:\n```\ndef test:\nprint('hello')\nprint('world')\n```" == my_result

    my_result = extract(my_document, output_format='markdown', include_formatting=True, preserve_space=True)
    assert """python code below:
    ```
def test:
    print('hello')
    print('world')
    
```""" == my_result


def test_extract_with_metadata():
    '''Test extract_with_metadata method'''
    url = 'http://aa.bb/cc.html'
    my_document = html.fromstring("""<html>
        <head></head>
        <body>
        <article>
        <p>AAA, <p>BBB</p>, CCC.</p>
        </article>
        </body>
        </html>
    """)
    parsed_doc = extract_with_metadata(my_document, output_format='txt', include_formatting=True, fast=True, url=url)
    content = parsed_doc.text
    assert 'AAA' in content and 'BBB' in content and 'CCC' in content
    assert url == parsed_doc.url and parsed_doc.date is None and parsed_doc.title is None

    my_document = html.fromstring("""<html>
        <head><title>title</title></head>
        <body>
        <article>
        <div>May 24, 2021</div>
        <p>AAA, <p>BBB</p>, CCC.</p>
        </article>
        </body>
        </html>
    """)
    parsed_doc = extract_with_metadata(my_document, output_format='txt', include_formatting=True, fast=True, url=url)
    content = parsed_doc.text
    assert 'AAA' in content and 'BBB' in content and 'CCC' in content
    assert url == parsed_doc.url and '2021-05-24' == parsed_doc.date and 'title' == parsed_doc.title

    parsed_doc = extract_with_metadata(my_document, output_format='xml')
    assert 'AAA, BBB , CCC.' == parsed_doc.raw_text and 'ee7d2fb6fcf2837d' == parsed_doc.fingerprint
    content = parsed_doc.text
    assert 'AAA' in content and 'BBB' in content and 'CCC' in content

    my_document = html.fromstring("""<html>
        <head><meta http-equiv="content-language" content="es"></head>
        <body>
        <article>
        <p>AAA, <p>BBB</p>, CCC.</p>
        </article>
        </body>
        </html>
    """)
    parsed_doc = extract_with_metadata(my_document, target_language='en', fast=True)
    assert parsed_doc is None

    with pytest.raises(ValueError) as err:
        extract_with_metadata(my_document, output_format="python")


def test_external():
    '''Test external components'''
    options = DEFAULT_OPTIONS
    options.tables = True
    # remove unwanted elements
    mydoc = html.fromstring('<html><body><footer>Test text</footer></body></html>')
    _, _, mylen = sanitize_tree(mydoc, options)
    assert mylen == 0
    mydoc = html.fromstring('<html><body><table><th>Test text</th><tr><td>Test</td></tr></table></body></html>')
    _, _, mylen = sanitize_tree(mydoc, options)
    assert mylen > 0
    # strip fancy tags while including links and images
    mydoc = html.fromstring('<html><body><p>Text here <fancy>Test text</fancy><a href="">with a link</a>.</p><img src="test.jpg"/></body></html>')
    mytree, _, _ = sanitize_tree(mydoc, options)
    assert len(mytree) == 1
    mydoc = html.fromstring('<html><body><p>Text here <fancy>Test text</fancy><a href="">with a link</a>.</p><img src="test.jpg"/></body></html>')
    options.links, options.images = True, True
    mytree, _, _ = sanitize_tree(mydoc, options)
    myelems = {element.tag for element in set(mytree.iter())}
    assert 'graphic' in myelems and 'ref' in myelems
    # test langid
    if LANGID_FLAG is True:
        doc = html.fromstring('<html><body>' + '<p>Non è inglese.</p>'*20 + '</body></html>')
        assert extract(doc, fast=False, target_language='en', deduplicate=False) is None
    # no tables
    with open(path.join(RESOURCES_DIR, "apache.html"), "r", encoding="utf-8") as f:
        teststring = f.read()
    assert 'localhost:80' in extract(teststring, fast=False, include_tables=True)
    assert 'localhost:80' not in extract(teststring, fast=False, include_tables=False)
    with open(path.join(RESOURCES_DIR, "scam.html"), "r", encoding="utf-8") as f:
        teststring = f.read()
    assert extract(teststring, fast=True, include_tables=False) == ''
    assert extract(teststring, fast=False, include_tables=False) == ''
    # invalid XML attributes: namespace colon in attribute key (issue #375). Those attributes should be stripped
    bad_xml = 'Testing<ul style="" padding:1px; margin:15px""><b>Features:</b> <li>Saves the cost of two dedicated phone lines.</li> al station using Internet or cellular technology.</li> <li>Requires no change to the existing Fire Alarm Control Panel configuration. The IPGSM-4G connects directly to the primary and secondary telephone ports.</li>'
    res = extract(bad_xml, output_format='xml')
    assert "Features" in res

def test_images():
    '''Test image extraction function'''
    # file type
    assert is_image_file(None) is False
    assert is_image_file('') is False
    assert is_image_file('test.jpg') is True
    assert is_image_file('test.txt') is False
    assert is_image_file('test.jpg'*2000) is False  # length threshold
    # tag with attributes
    assert handle_image(None) is None
    assert handle_image(html.fromstring('<img src="test.jpg"/>')) is not None
    assert handle_image(html.fromstring('<img data-src="test.jpg" alt="text" title="a title"/>')) is not None
    assert handle_image(html.fromstring('<img other="test.jpg"/>')) is None
    # HTML conversion
    assert handle_textelem(etree.Element('graphic'), [], DEFAULT_OPTIONS) is None
    with open(path.join(RESOURCES_DIR, "http_sample.html"), "r", encoding="utf-8") as f:
        teststring = f.read()
    assert '![Example image](test.jpg)' not in extract(teststring)
    assert '![Example image](test.jpg)' in extract(teststring, include_images=True, fast=True)
    assert '<graphic src="test.jpg" title="Example image"/>' in extract(teststring, include_images=True, fast=True, output_format='xml', config=ZERO_CONFIG)
    assert extract('<html><body><article><img data-src="test.jpg" alt="text" title="a title"/></article></body></html>', include_images=True, fast=True) == '![a title text](test.jpg)'
    assert extract('<html><body><article><p><img data-src="test.jpg" alt="text" title="a title"/></p></article></body></html>', include_images=True, fast=True) == '![a title text](test.jpg)'
    assert extract('<html><body><article><p><img other="test.jpg" alt="text" title="a title"/></p></article></body></html>', include_images=True, fast=True) == ''
    assert extract('<html><body><article><div><p><img data-src="test.jpg" alt="text" title="a title"/></p></div></article></body></html>', include_images=True, fast=True) == '![a title text](test.jpg)'
    assert extract('<html><body><article><div><p><img data-src-small="test.jpg" alt="text" title="a title"/></p></div></article></body></html>', include_images=True, fast=True) == '![a title text](test.jpg)'
    assert extract('<html><body><article><div><p><img src="https://a.b/test.jpg" alt="text" title="a title"/></p></div></article></body></html>', include_images=True, fast=True) == '![a title text](https://a.b/test.jpg)'

    url = 'http://a.b/c/d.html'
    assert extract('<html><body><article><div><p><img src="//a.b/test.jpg" alt="text" title="a title"/></p></div></article></body></html>', url=url, include_images=True, fast=True) == '![a title text](http://a.b/test.jpg)'
    assert extract('<html><body><article><div><p><img src="/a.b/test.jpg" alt="text" title="a title"/></p></div></article></body></html>', url=url, include_images=True, fast=True) == '![a title text](http://a.b/a.b/test.jpg)'
    assert extract('<html><body><article><div><p><img src="./a.b/test.jpg" alt="text" title="a title"/></p></div></article></body></html>', url=url, include_images=True, fast=True) == '![a title text](http://a.b/c/a.b/test.jpg)'
    assert extract('<html><body><article><div><p><img src="../a.b/test.jpg" alt="text" title="a title"/></p></div></article></body></html>', url=url, include_images=True, fast=True) == '![a title text](http://a.b/a.b/test.jpg)'

    assert handle_image(html.fromstring('<img src="data:image/jpeg;base64,iVBORw0KGgoAAAANSUhEUgAAAAUAAAAFCAYAAACNbyblAAAAHElEQVQI12P4//8/w38GIAXDIBKE0DHxgljNBAAO9TXL0Y4OHwAAAABJRU5ErkJggg==" alt="text"></img>')) is None

    # CNN example
    mydoc = html.fromstring('<img class="media__image media__image--responsive" alt="Harry and Meghan last March, in their final royal engagement." data-src-mini="//cdn.cnn.com/cnnnext/dam/assets/210307091919-harry-meghan-commonwealth-day-small-169.jpg" data-src-xsmall="//cdn.cnn.com/cnnnext/dam/assets/210307091919-harry-meghan-commonwealth-day-medium-plus-169.jpg" data-src-small="//cdn.cnn.com/cnnnext/dam/assets/210307091919-harry-meghan-commonwealth-day-large-169.jpg" data-src-medium="//cdn.cnn.com/cnnnext/dam/assets/210307091919-harry-meghan-commonwealth-day-exlarge-169.jpg" data-src-large="//cdn.cnn.com/cnnnext/dam/assets/210307091919-harry-meghan-commonwealth-day-super-169.jpg" data-src-full16x9="//cdn.cnn.com/cnnnext/dam/assets/210307091919-harry-meghan-commonwealth-day-full-169.jpg" data-src-mini1x1="//cdn.cnn.com/cnnnext/dam/assets/210307091919-harry-meghan-commonwealth-day-small-11.jpg" data-demand-load="loaded" data-eq-pts="mini: 0, xsmall: 221, small: 308, medium: 461, large: 781" src="//cdn.cnn.com/cnnnext/dam/assets/210307091919-harry-meghan-commonwealth-day-exlarge-169.jpg" data-eq-state="mini xsmall small medium" data-src="//cdn.cnn.com/cnnnext/dam/assets/210307091919-harry-meghan-commonwealth-day-exlarge-169.jpg">')
    myimage = handle_image(mydoc)
    assert myimage is not None and 'alt' in myimage.attrib and 'src' in myimage.attrib
    # modified CNN example
    mydoc = html.fromstring('<img class="media__image media__image--responsive" alt="Harry and Meghan last March, in their final royal engagement." data-src-mini="//cdn.cnn.com/cnnnext/dam/assets/210307091919-harry-meghan-commonwealth-day-small-169.jpg" data-src-xsmall="//cdn.cnn.com/cnnnext/dam/assets/210307091919-harry-meghan-commonwealth-day-medium-plus-169.jpg" data-src-small="//cdn.cnn.com/cnnnext/dam/assets/210307091919-harry-meghan-commonwealth-day-large-169.jpg" data-src-medium="//cdn.cnn.com/cnnnext/dam/assets/210307091919-harry-meghan-commonwealth-day-exlarge-169.jpg" data-src-large="//cdn.cnn.com/cnnnext/dam/assets/210307091919-harry-meghan-commonwealth-day-super-169.jpg" data-src-full16x9="//cdn.cnn.com/cnnnext/dam/assets/210307091919-harry-meghan-commonwealth-day-full-169.jpg" data-src-mini1x1="//cdn.cnn.com/cnnnext/dam/assets/210307091919-harry-meghan-commonwealth-day-small-11.jpg" data-demand-load="loaded" data-eq-pts="mini: 0, xsmall: 221, small: 308, medium: 461, large: 781">')
    myimage = handle_image(mydoc)
    assert myimage is not None and 'alt' in myimage.attrib and 'src' in myimage.attrib and myimage.get('src').startswith('http')


def test_links():
    '''Test link extraction function'''
    options = DEFAULT_OPTIONS
    options._add_config(ZERO_CONFIG)
    assert handle_textelem(etree.Element('ref'), [], options) is None
    assert handle_formatting(html.fromstring('<a href="testlink.html">Test link text.</a>'), options) is not None
    # empty link
    mydoc = html.fromstring('<html><body><p><a></a><b>Some text.</b></p></body></html>')
    assert extract(mydoc) is not None
    # link with target
    mydoc = html.fromstring('<html><body><p><a href="testlink.html">Test link text.</a> This part of the text has to be long enough.</p></body></html>')
    assert 'testlink.html' not in extract(copy(mydoc))
    assert '[Test link text.](testlink.html) This part of the text has to be long enough.' in extract(copy(mydoc), include_links=True, fast=True, config=ZERO_CONFIG)
    # relative link conversion
    assert '[Test link text.](https://www.example.com/testlink.html) This part of the text has to be long enough.' in extract(copy(mydoc), url='https://www.example.com/', include_links=True, fast=True, config=ZERO_CONFIG)
    # link without target
    mydoc = html.fromstring('<html><body><p><a>Test link text.</a> This part of the text has to be long enough.</p></body></html>')
    assert '[Test link text.] This part of the text has to be long enough.' in extract(copy(mydoc), include_links=True, fast=True, config=ZERO_CONFIG)
    mydoc = html.fromstring('<html><body><article><a>Segment 1</a><h1><a>Segment 2</a></h1><p>Segment 3</p></article></body></html>')
    result = extract(copy(mydoc), output_format='xml', include_links=True, fast=True, config=ZERO_CONFIG)
    assert '1' in result and '2' in result and '3' in result
    with open(path.join(RESOURCES_DIR, "http_sample.html"), "r", encoding="utf-8") as f:
        teststring = f.read()
    assert 'testlink.html' not in extract(teststring, config=ZERO_CONFIG)
    assert '[link](testlink.html)' in extract(teststring, include_links=True, fast=True, config=ZERO_CONFIG)
    assert '<ref target="testlink.html">link</ref>' in extract(teststring, include_links=True, fast=True, output_format='xml', config=ZERO_CONFIG)
    # test license link
    mydoc = html.fromstring('<html><body><p>Test text under <a rel="license" href="">CC BY-SA license</a>.</p></body></html>')
    assert 'license="CC BY-SA license"' in extract(mydoc, include_links=True, fast=True, output_format='xml', config=ZERO_CONFIG, with_metadata=True)

    # link in p, length threshold
    mydoc = html.fromstring(f'<html><body><article><p><a>f{"abcd"*20}</a></p></article></body></html>')
    assert "abc" in extract(copy(mydoc), fast=True, config=ZERO_CONFIG, favor_precision=False)
    assert extract(mydoc, fast=True, config=ZERO_CONFIG, favor_precision=True) == ""


def test_tei():
    '''test TEI-related functions'''
    # open local resources to avoid redownloading at each run
    with open(path.join(RESOURCES_DIR, "httpbin_sample.html"), "r", encoding="utf-8") as f:
        teststring = f.read()
    # download, parse and validate simple html file
    result1 = extract(teststring, "mocked", fast=True, output_format='xmltei', tei_validation=False)
    result2 = extract(teststring, "mocked", fast=True, output_format='xmltei', tei_validation=True)
    assert result1 is not None and result1 == result2
    assert xml.validate_tei(etree.fromstring(result1)) is True
    assert xml.validate_tei(etree.fromstring(teststring)) is False
    # test with another file
    with open(path.join(RESOURCES_DIR, "http_sample.html"), "r", encoding="utf-8") as f:
        teststring = f.read()
    # download, parse and validate simple html file
    result = extract(teststring, "mocked", fast=True, include_comments=True, output_format='xmltei', tei_validation=False)
    assert result is not None # and '<p>license</p>' in result
    assert xml.validate_tei(etree.fromstring(result)) is True
    result = extract(teststring, "mocked", fast=True, include_comments=False, output_format='xmltei', tei_validation=False)
    assert result is not None # and '<p>license</p>' in result
    assert xml.validate_tei(etree.fromstring(result)) is True
    # include ID in metadata
    result = extract(teststring, "mocked", fast=True, output_format='xmltei', tei_validation=False, record_id='0001')
    assert result is not None
    assert xml.validate_tei(etree.fromstring(result)) is True
    # test header + metadata
    tei = etree.Element('TEI', xmlns='http://www.tei-c.org/ns/1.0')
    header = etree.SubElement(tei, 'teiHeader')
    docmeta = Document()
    docmeta.categories, docmeta.tags = [], []
    docmeta.title = 'Title'
    assert xml.write_fullheader(header, docmeta) is not None
    docmeta.sitename = 'Site Name'
    docmeta.date = '2021-01-01'
    assert xml.write_fullheader(header, docmeta) is not None
    docmeta.date = None
    assert xml.write_fullheader(header, docmeta) is not None
    docmeta.hostname = 'hostname'
    assert xml.write_fullheader(header, docmeta) is not None
    docmeta.sitename = None
    docmeta.license = 'CC BY-SA'
    docmeta.url = 'https://test.org/'
    docmeta.categories = ['cat1', 'cat2']
    assert xml.write_fullheader(header, docmeta) is not None
    docmeta.date = '2021-01-01'
    assert xml.write_fullheader(header, docmeta) is not None
    docmeta.title, docmeta.sitename = None, None
    assert xml.write_fullheader(header, docmeta) is not None
    xml_doc = etree.fromstring("<TEI><text><body><div>text</div></body></text></TEI>")
    cleaned = xml.check_tei(xml_doc, "fake_url")
    result = [(elem.tag, elem.text) for elem in cleaned.find(".//div").iter()]
    expected = [("div", None), ("p", "text")]
    assert result == expected
    xml_doc = etree.fromstring("<TEI><text><body><div><div>text1<p>text2</p></div></div></body></text></TEI>")
    cleaned = xml.check_tei(xml_doc, "fake_url")
    result = [(elem.tag, elem.text) for elem in cleaned.find(".//div").iter()]
    expected = [("div", None), ("div", None), ("p", "text1 text2")]
    assert result == expected
    xml_doc = etree.fromstring("<TEI><text><body><div><div>text1<head>text2</head></div></div></body></text></TEI>")
    cleaned = xml.check_tei(xml_doc, "fake_url")
    result = [(elem.tag, elem.text) for elem in cleaned.find(".//div").iter()]
    expected = [("div", None), ("div", None), ("p", "text1"), ("ab", "text2")]
    assert result == expected
    xml_doc = etree.fromstring("<TEI><text><body><div><div>text1<p>text2</p></div>has to be there</div></body></text></TEI>")
    cleaned = xml.check_tei(xml_doc, "fake_url")
    result = [(elem.tag, elem.text, elem.tail) for elem in cleaned.find(".//div/div").iter()]
    expected = [("div", None, None), ("p", "text1 text2 has to be there", None)]
    assert result == expected
    xml_doc = etree.fromstring("<TEI><text><body><div><div>text1<quote>text2</quote></div>has to be there</div></body></text></TEI>")
    cleaned = xml.check_tei(xml_doc, "fake_url")
    result = [(elem.tag, elem.text, elem.tail) for elem in cleaned.find(".//div/div").iter()]
    expected = [("div", None, None), ("p", "text1", None), ("quote", "text2", None), ("p", "has to be there", None)]
    assert result == expected
    xml_doc = etree.fromstring("<TEI><text><body><div><div>text1<p>text2</p>has to be there</div></div></body></text></TEI>")
    cleaned = xml.check_tei(xml_doc, "fake_url")
    result = [(elem.tag, elem.text, elem.tail) for elem in cleaned.find(".//div/div").iter()]
    expected = [("div", None, None), ("p", "text1 text2 has to be there", None)]
    assert result == expected
    htmlstring = html.fromstring("<html><head/><body><div><h2><p>text</p></h2></div></body></html>")
    extracted = extract(htmlstring, url='mocked', fast=True, output_format="xmltei")
    assert xml.validate_tei(etree.fromstring(extracted)) is True
    htmlstring  = html.fromstring("<html><body><article><h1>title</h1><h2>subtitle</h2><p>text</p></article></body></html>")
    extracted = extract(htmlstring, url="mocked", fast=True, output_format="xmltei")
    assert '<ab rend="h1" type="header">title</ab>' in extracted
    assert '<ab rend="h2" type="header">subtitle</ab>' in extracted
    htmlstring = html.fromstring(
    """<html>
        <body><article>
            <h2><div>
              <p>content</p>
              <ul>
                <li>text1</li>
                <li>text2</li>
              </ul>
            </div></h2>
        </article></body>
        </html>"""
    )
    extracted = extract(htmlstring, url="mocked", fast=True, output_format="xmltei")
    assert '<ab rend="h2" type="header">content<list rend="ul"><item>text1' in extracted.replace("\n", "")
    # merge double elements
    tree = html.fromstring(
    """<html>
        <body>
            <p><p>
              <span><p>content</p></span>
            </p></p>
        </body>
        </html>"""
    )
    tree = xml.remove_empty_elements(xml.strip_double_tags(tree))
    result = sanitize(etree.tostring(tree, encoding="unicode")).replace("\n", "")
    assert result == "<html><body><p><span>content</span></p></body></html>"
    tree = html.fromstring(
    """
    <html>
        <body>
            <div>
                <div>
                    <p>
                        <p>text</p>
                    <p>
                </div>
            </div>
        </body>
    </html>
    """
    )
    xml.strip_double_tags(tree)
    assert tree.find(".//div/div") is not None and tree.find(".//p/p") is None
    tree = etree.XML(
    """
    <html><body>
        <div>
            <p>text1<lb/>text2<p>text3</p><lb/>text4</p>
            <p>text5<p>text6</p></p>
        </div>
    </body></html>
    """
    )
    xml.strip_double_tags(tree)
    assert tree.find(".//p/p") is None
    tree = etree.XML(
    """
    <html><body>
        <div>
            <p>text1<lb/>text2<p>text3</p><lb/>text4</p>
            <p>text5<p>text6<p>text7</p></p></p>
        </div>
    </body></html>
    """
    )
    xml.strip_double_tags(tree)
    assert tree.find(".//p/p") is None
    assert "text7" in etree.tostring(tree, encoding="unicode")
    # nested elements with same tag not merged
    tree = html.fromstring(
    """<html>
        <body>
            <div>
                <p>
                  <list>
                    <item>
                        <p>text</p>
                    </item>
                  </list>
                </p>
                <p>
                    <table>
                      <row>
                        <cell>
                          <p>text1</p>
                         </cell>
                      </row>
                    </table>
                </p>
                <p>
                    <note>
                      <p>text2</p>
                    </note>
                </p>
                <p>
                    <quote>
                        <p>text3</p>
                    </quote>
                </p>
                <p>
                    <figure>
                        <p>text4</p>
                    </figure>
                </p>
            </div>
        </body>
    </html>"""
    )
    xml.strip_double_tags(tree)
    for parent_tag in ["item", "cell", "quote", "note", "figure"]:
        assert tree.find(f".//{parent_tag}/p") is not None


def test_htmlprocessing():
    '''test html-related functions'''
    assert xml.xmltotxt(None, include_formatting=False) == ""

    options = DEFAULT_OPTIONS
    options.tables = True
    assert trafilatura.htmlprocessing.tree_cleaning(etree.Element('html'), options) is not None
    assert trafilatura.htmlprocessing.prune_html(etree.Element('unwanted')) is not None
    mydoc = html.fromstring('<html><body><table><a href="">Link</a></table><img src="test.jpg"/><u>Underlined</u><tt>True Type</tt><sub>Text</sub><sup>Text</sup></body></html>')
    options.formatting, options.images, options.links = True, True, True
    myconverted = trafilatura.htmlprocessing.convert_tags(mydoc, options)
    assert myconverted.xpath('.//ref') and myconverted.xpath('.//graphic') and myconverted.xpath('.//hi[@rend="#t"]') and myconverted.xpath('.//table')
    options.images, options.tables = True, False
    myconverted = trafilatura.htmlprocessing.tree_cleaning(mydoc, options)
    assert myconverted.xpath('.//graphic') and not myconverted.xpath('.//table')
    mydoc = html.fromstring('<html><body><article><h1>Test headline</h1><p>Test</p></article></body></html>')
    assert '<head rend="h1">Test headline</head>' in extract(copy(mydoc), output_format='xml', config=ZERO_CONFIG, fast=True)
    assert '<ab rend="h1" type="header">Test headline</ab>' in extract(copy(mydoc), output_format='xmltei', config=ZERO_CONFIG, fast=True)

    # merge with parent function
    element = etree.Element('test')
    xml.delete_element(element)
    assert etree.tostring(element) == b'<test/>'
    element = etree.Element('test')
    xml.merge_with_parent(element)
    assert etree.tostring(element) == b'<test/>'

    mydoc = html.fromstring('<html><body><p><span>A</span><span>B</span><span>C</span></p></body></html>')
    for element in mydoc.iter('span'):
        xml.merge_with_parent(element)
    assert b'<p>A B C</p>' in etree.tostring(mydoc)
    mydoc = html.fromstring('<html><body><p><span>A</span><span>B</span> tail<span>C</span></p></body></html>')
    for element in mydoc.iter('span'):
        xml.merge_with_parent(element)
    assert b'<p>A B tail C</p>' in etree.tostring(mydoc)

    # paywalls
    my_html = '<html><body><main><p>1</p><p id="premium">2</p><p>3</p></main></body></html>'
    assert extract(my_html, config=ZERO_CONFIG, fast=True) == '1\n3'
    assert extract(my_html, config=ZERO_CONFIG, fast=False) == '1\n3'
    # test tail of node deleted if set as text
    node = etree.fromstring("<div><p></p>tail</div>")[0]
    trafilatura.htmlprocessing.process_node(node, options)
    assert node.text == 'tail'
    assert node.tail is None
    node = etree.fromstring("<list><item></item>text in tail</list>")[0]
    trafilatura.htmlprocessing.process_node(node, options)
    assert node.text == "text in tail"
    assert node.tail is None
    line_break = etree.fromstring("<p><lb/>tail</p>")[0]
    trafilatura.htmlprocessing.process_node(line_break, options)
    assert line_break.text is None
    assert line_break.tail == "tail"
    node = etree.fromstring("<div><p>some text</p>tail</div>")[0]
    trafilatura.htmlprocessing.process_node(node, options)
    assert node.text == "some text"
    assert node.tail == "tail"
    node = etree.fromstring("<p><ref target='url'><hi rend='#b'>bold</hi>inner</ref>outer</p>")[0]
    processed = trafilatura.htmlprocessing.handle_textnode(node, options)
    assert processed.tail == "outer"
    node = etree.fromstring("<p><ref target='url'>text</ref>tail</p>")[0]
    processed = trafilatura.htmlprocessing.handle_textnode(node, options)
    assert processed.tail == "tail" and processed.text == "text"
    node = etree.fromstring("<p><ref target='url'></ref>tail</p>")[0]
    processed = trafilatura.htmlprocessing.handle_textnode(node, options)
    assert processed.tail == "" and processed.text == "tail"
    node = etree.fromstring("<p><ref target='url'>text<hi rend='#b'>bold</hi></ref>tail</p>")[0]
    processed = trafilatura.htmlprocessing.handle_textnode(node, options)
    assert processed.tail == "tail" and processed.text == "text"



def test_extraction_options():
    '''Test the different parameters available in extract() and bare_extraction()'''
    my_html = '<html><head><meta http-equiv="content-language" content="EN"/></head><body><div="article-body"><p>Text.<!-- comment --><?php echo "This is a PHP processing instruction"; ?></p></div></body></html>'

    with pytest.raises(ValueError) as err:
        extract(my_html, output_format="python")
    assert extract(my_html, config=NEW_CONFIG) is None
    assert extract(my_html, config=ZERO_CONFIG) is not None
    assert extract(my_html, only_with_metadata=False, output_format='xml', config=ZERO_CONFIG) is not None
    assert extract(my_html, only_with_metadata=True, output_format='xml', config=ZERO_CONFIG) is None
    assert extract(my_html, target_language='de', config=ZERO_CONFIG) is None
    assert extract(my_html, target_language='de', fast=True, config=ZERO_CONFIG) is None

    # justext hardening
    assert etree.tostring(try_justext(html.fromstring(my_html), None, 'de')) == b'<body/>'
    assert etree.tostring(try_justext(None, None, 'de')) == b'<body/>'
    # assert extract(my_html) is None

    # readability
    my_html = '<html><body><p>' + 'Text. '*10 + '</p></body></html>'
    result = etree.tostring(try_readability(html.fromstring(my_html)))
    assert len(result) > 10 and b'Text' in result
    my_html = '<html><body><p>' + 'Text. '*10 + '<embed>Test</embed></p></body></html>'
    result = etree.tostring(try_readability(html.fromstring(my_html)))
    assert b'Test' not in result

    my_html = '<html><head/><body>' + '<p>ABC def ghi jkl.</p>'*1000 + '<p>Posted on 1st Dec 2019<.</p></body></html>'
    assert bare_extraction(my_html, config=ZERO_CONFIG, with_metadata=True).date is not None
    assert bare_extraction(my_html, config=NEW_CONFIG, with_metadata=True).date is None
    assert bare_extraction(my_html, config=NEW_CONFIG, with_metadata=False).date is None


def test_precision_recall():
    '''test precision- and recall-oriented settings'''
    # the test cases could be better
    my_document = html.fromstring('<html><body><p>This here is the text.</p></body></html>')
    assert extract(copy(my_document), favor_precision=True, config=ZERO_CONFIG, fast=True) is not None
    assert extract(copy(my_document), favor_recall=True, config=ZERO_CONFIG, fast=True) is not None

    my_document = html.fromstring('<html><body><div class="article-body"><div class="teaser-content"><p>This here is a teaser text.</p></div><div><p>This here is the text.</p></div></body></html>')
    assert 'teaser text' in extract(copy(my_document), favor_recall=True, config=ZERO_CONFIG, fast=True)
    assert 'teaser text' not in extract(copy(my_document), config=ZERO_CONFIG, fast=True)
    assert 'teaser text' not in extract(copy(my_document), favor_precision=True, config=ZERO_CONFIG, fast=True)

    my_document = html.fromstring('<html><body><article><div><p><a href="test.html">1.</a><br/><a href="test2.html">2.</a></p></div></article></body></html>')
    result = extract(copy(my_document), favor_recall=True, config=ZERO_CONFIG, fast=True)
    assert '1' not in result
    result = extract(copy(my_document), favor_precision=True, config=ZERO_CONFIG, fast=True)
    assert '1' not in result

    my_document = html.fromstring('<html><body><div class="article-body"><p>content</p><p class="link">Test</p></div></body></html>')
    result = extract(copy(my_document), favor_precision=False, config=ZERO_CONFIG, fast=True)
    assert 'content' in result and 'Test' in result
    result = extract(copy(my_document), favor_precision=True, config=ZERO_CONFIG, fast=True)
    assert 'content' in result and 'Test' not in result

    my_document = html.fromstring('<html><body><article><aside><p>Here is the text.</p></aside></article></body></html>')
    result = extract(copy(my_document), favor_recall=False, config=ZERO_CONFIG, fast=True)
    assert result != "Here is the text."
    result = extract(copy(my_document), favor_recall=True, config=ZERO_CONFIG, fast=True)
    assert result == "Here is the text."

    my_document = html.fromstring('<html><body><div><h2>Title</h2><small>Text.</small></div></body></html>')
    result = extract(copy(my_document), favor_recall=True, config=ZERO_CONFIG, fast=False)
    assert len(result) > 0

    my_document = html.fromstring('<html><body><div><span>Text.</span></div></body></html>')
    assert extract(copy(my_document), favor_precision=True, fast=True) == ""
    assert extract(copy(my_document), favor_recall=True, fast=True) == "Text."


def test_table_processing():
    options = DEFAULT_OPTIONS
    table_simple_cell = html.fromstring(
        "<table><tr><td>cell1</td><td>cell2</td></tr><tr><td>cell3</td><td>cell4</td></tr></table>"
    )
    processed_table = handle_table(table_simple_cell, TAG_CATALOG, options)
    result = [(child.tag, child.text) for child in processed_table.iter()]
    assert result == [
        ("table", None),
        ("row", None),
        ("cell", "cell1"),
        ("cell", "cell2"),
        ("row", None),
        ("cell", "cell3"),
        ("cell", "cell4"),
    ]
    # if a cell contains 'exotic' tags, they are cleaned during the extraction
    # process and the content is merged with the parent e.g. <td>
    table_cell_with_children = html.fromstring(
        "<table><tr><td><p>text</p><p>more text</p></td></tr></table>"
    )
    processed_table = handle_table(table_cell_with_children, TAG_CATALOG, options)
    assert (
        etree.tostring(processed_table, encoding="unicode")
        == "<table><row><cell><p>text</p><p>more text</p></cell></row></table>"
    )
    # complex table that hasn't been cleaned yet
    htmlstring = html.fromstring(
        """<html>
              <body><article>
                <table>
                  <tbody>
                    <tr>
                      <td>
                        <small>text<br></small>
                        <h4>more_text</h4>
                      </td>
                      <td><a href='link'>linktext</a></td>
                    </tr>
                  </tbody>
                </table>
              </article></body>
            </html>"""
    )
    processed = extract(
        htmlstring, fast=True, output_format='xml', config=DEFAULT_CONFIG, include_links=True
    )
    result = processed.replace('\n', '').replace(' ', '')
    assert """<table><row><cell>text<head>more_text</head></cell></row></table>""" in result

    table_cell_w_text_and_child = html.fromstring(
        "<table><tr><td>text<lb/><p>more text</p></td></tr></table>"
    )
    processed_table = handle_table(
        table_cell_w_text_and_child, TAG_CATALOG, options
    )
    assert (
        etree.tostring(processed_table, encoding="unicode")
        == "<table><row><cell>text<p>more text</p></cell></row></table>"
    )
    table_cell_with_link = html.fromstring(
        "<table><tr><td><ref='test'>link</ref></td></tr></table>"
    )
    processed_table = handle_table(table_cell_with_link, TAG_CATALOG, options)
    result = [child.tag for child in processed_table.find(".//cell").iterdescendants()]
    assert result == ["p"]
    table_with_head = html.fromstring(
        """<table>
      <tr>
        <th>Month</th>
        <th>Days</th>
      </tr>
      <tr>
        <td>January</td>
        <td>31</td>
      </tr>
      <tr>
        <td>February</td>
        <td>28</td>
      </tr>
    </table>"""
    )
    processed_table = handle_table(
        table_with_head, TAG_CATALOG, options
    )
    first_row = processed_table[0]
    assert len(processed_table) == 3
    assert [
        (child.tag, child.attrib, child.text) for child in first_row.iterdescendants()
    ] == [("cell", {"role": "head"}, "Month"), ("cell", {"role": "head"}, "Days")]

    table_with_head_spanning_two_cols = html.fromstring(
        """<table>
      <tr>
        <th>Name</th>
        <th>Adress</th>
        <th colspan="2">Phone</th>
      </tr>
      <tr>
        <td>Jane Doe</td>
        <td>test@example.com</td>
        <td>phone 1</td>
        <td>phone 2</td>
      </tr>
    </table>"""
    )
    processed_table = handle_table(
        table_with_head_spanning_two_cols,
        TAG_CATALOG,
        options,
    )
    first_row = processed_table[0]
    assert len(first_row) == 3
    assert {child.tag for child in first_row.iterdescendants()} == {"cell"}
    table_cell_with_hi = html.fromstring(
        "<table><tr><td><hi>highlighted text</hi></td></tr></table>"
    )
    processed_table = handle_table(table_cell_with_hi, TAG_CATALOG, options)
    result = etree.tostring(processed_table.find(".//cell"), encoding="unicode")
    assert result == "<cell><hi>highlighted text</hi></cell>"
    table_cell_with_span = html.fromstring(
        "<table><tr><td><span style='sth'>span text</span></td></tr></table>"
    )
    processed_table = handle_table(table_cell_with_span, TAG_CATALOG, options)
    result = etree.tostring(processed_table.find(".//cell"), encoding="unicode")
    assert result == "<cell><p/></cell>"
    # tables with nested elements
    htmlstring = '''<html><body><article>
<table>
<tr><td><b>Present Tense</b></td>
<td>I buy</td>
<td>you buy</td>
<td>he/she/it buys</td>
<td>we buy</td>
<td>you buy</td>
<td>they buy</td>
</tr>
    </table></article></body></html>'''
    my_result = extract(htmlstring, fast=True, output_format='xml', include_formatting=True, config=ZERO_CONFIG)
    assert '''<row>
        <cell>
          <hi>Present Tense</hi>
        </cell>
        <cell>I buy</cell>
        <cell>you buy</cell>
        <cell>he/she/it buys</cell>
        <cell>we buy</cell>
        <cell>you buy</cell>
        <cell>they buy</cell>
      </row>''' in my_result
    assert extract(htmlstring, fast=True, output_format='txt').startswith("| Present Tense | I buy | you buy |")
    # table with links
    # todo: further tests and adjustments
    htmlstring = '<html><body><article><table><tr><td><a href="test.html">' + 'ABCD'*100 + '</a></td></tr></table></article></body></html>'
    result = extract(htmlstring, fast=True, output_format='xml', config=ZERO_CONFIG, include_tables=True, include_links=True)
    assert 'ABCD' not in result
    # nested table
    htmlstring = '<html><body><article><table><th>1</th><table><tr><td>2</td></tr></table></table></article></body></html>'
    result = extract(htmlstring, fast=True, output_format='xml', config=ZERO_CONFIG, include_tables=True)
    # todo: all elements are there, but output not nested
    assert '<cell role="head">1</cell>' in result and '<cell>2</cell>' in result
    nested_table = html.fromstring(
        """
        <table>
        <tr>
        <td>
          <table><tr><td>1</td></tr></table>
        </td>
        </tr>
        </table>"""
    )
    processed_table = handle_table(nested_table, TAG_CATALOG, options)
    result = [
        (el.tag, el.text) if el.text is not None and el.text.strip() else el.tag
        for el in processed_table.iter()
    ]
    #assert result == ["table", "row", "cell", "table", "row", ("cell", "1")]
    assert result == ["table", "row", "cell", ("cell", "1")]
    complex_nested_table = html.fromstring(
    """
    <table>
    <tr>
    <td>
      <table><tr><td>1</td></tr></table>
    </td>
    <td>text1</td>
    </tr>
    <tr><td>text2</td></tr>
    </table>"""
    )
    processed_table = handle_table(complex_nested_table, TAG_CATALOG, options)
    result = [
        (el.tag, el.text) if el.text is not None and el.text.strip() else el.tag
        for el in processed_table.iter()
    ]
    #assert (
    #        result
    #        == ["table", "row", "cell", "table", "row", ("cell", "1"), ("cell", "text1"), "row", ("cell", "text2")]
    #)
    assert result == ['table', 'row', 'cell', ('cell', '1'), ('cell', 'text1'), 'row', ('cell', 'text2')]
    table_with_list = html.fromstring(
    """
    <table><tr><td>
    <p>a list</p>
    <list>
      <item>one</item>
      <item>two</item>
    </list>
    </td>
    </tr></table>
    """)
    processed_table = handle_table(copy(table_with_list), TAG_CATALOG, options)
    result = [
        (el.tag, el.text) if el.text is not None and el.text.strip() else el.tag
        for el in processed_table.iter()
    ]
    assert result == ['table', 'row', 'cell', ('p', 'a list'), 'list']

    options.focus = "recall"
    processed_table = handle_table(copy(table_with_list), TAG_CATALOG, options)
    result = [
        (el.tag, el.text) if el.text is not None and el.text.strip() else el.tag
        for el in processed_table.iter()
    ]
    assert result == ["table", "row", "cell", ("p", "a list"), 'list', ("item", "one"), ("item", "two"),]

    broken_table = html.fromstring("<table><td>cell1</td><tr><td>cell2</td></tr></table>")
    processed_table = handle_table(broken_table, TAG_CATALOG, options)
    result = [el.tag for el in processed_table.iter()]
    assert result == ['table', 'row', 'cell', 'row', 'cell']
    broken_table = html.fromstring("<table><tr><p>text</p></tr><tr><td>cell</td></tr></table>")
    processed_table = handle_table(broken_table, TAG_CATALOG, options)
    result = [el.tag for el in processed_table.iter()]
    assert result == ["table", "row", "cell", ]
    # table nested in figure https://github.com/adbar/trafilatura/issues/301
    htmlstring = '<html><body><article><figure><table><th>1</th><tr><td>2</td></tr></table></figure></article></body></html>'
    result = extract(htmlstring, fast=True, output_format='xml', config=ZERO_CONFIG, include_tables=True)
    assert "1" in result and "2" in result
    # table headers in non-XML formats
    htmlstring = '<html><body><article><table><tr><th>head 1</th><th>head 2</th></tr><tr><td>1</td><td>2</td></tr></table></article></body></html>'
    assert "|---|---|" in extract(htmlstring, fast=True, output_format='txt', config=ZERO_CONFIG, include_tables=True)

    # remove new lines in table cells in text format
    htmlstring = '<html><body><article><table><tr><td>cell<br>1</td><td>cell<p>2</p></td></tr></table></article></body></html>'
    result = extract(htmlstring, fast=True, output_format='txt', config=ZERO_CONFIG, include_tables=True)
    assert "| cell 1 | cell 2 |" in result

    # only one header row is allowed in text format
    htmlstring = '<html><body><article><table><tr><th>a</th><th>b</th></tr><tr><th>c</th><th>d</th></tr></table></article></body></html>'
    result = extract(htmlstring, fast=True, output_format='txt', config=ZERO_CONFIG, include_tables=True)
    assert result.count("---|") == 2

    # handle colspan by appending columns in text format
    htmlstring = '<html><body><article><table><tr><td colspan="2">a</td><td>b</td></tr><tr><td>c</td><td>d</td><td>e</td></tr></table></article></body></html>'
    result = extract(htmlstring, fast=True, output_format='txt', config=ZERO_CONFIG, include_tables=True)
    assert "| a | b | |" in result

    htmlstring = '<html><body><article><table><tr><td span="2">a</td><td>b</td></tr><tr><td>c</td><td>d</td><td>e</td></tr></table></article></body></html>'
    result = extract(htmlstring, fast=True, output_format='txt', config=ZERO_CONFIG, include_tables=True)
    assert "| a | b | |" in result

    htmlstring = '<html><body><article><table><tr><td span="2.1">a</td><td>b</td></tr><tr><td>c</td><td>d</td><td>e</td></tr></table></article></body></html>'
    result = extract(htmlstring, fast=True, output_format='txt', config=ZERO_CONFIG, include_tables=True)
    assert "| a | b | |" in result

    # MemoryError: https://github.com/adbar/trafilatura/issues/657
    htmlstring = '<html><body><article><table><tr><td colspan="9007199254740991">a</td><td>b</td></tr><tr><td>c</td><td>d</td><td>e</td></tr></table></article></body></html>'
    result = extract(htmlstring, fast=True, output_format='txt', config=ZERO_CONFIG, include_tables=True)
    assert result is not None

    htmlstring = '<html><body><article><table><tr><th colspan="9007199254740991">a</th><td>b</td></tr><tr><td>c</td><td>d</td><td>e</td></tr></table></article></body></html>'
    result = extract(htmlstring, fast=True, output_format='txt', config=ZERO_CONFIG, include_tables=True)
    assert result is not None

    # wrong span info
    htmlstring = '<html><body><article><table><tr><td span="-1">a</td><td>b</td></tr><tr><td>c</td><td>d</td><td>e</td></tr></table></article></body></html>'
    result = extract(htmlstring, fast=True, output_format='txt', config=ZERO_CONFIG, include_tables=True)
    assert "| a | b | |" in result

    htmlstring = '<html><body><article><table><tr><td span="abc">a</td><td>b</td></tr><tr><td>c</td><td>d</td><td>e</td></tr></table></article></body></html>'
    result = extract(htmlstring, fast=True, output_format='txt', config=ZERO_CONFIG, include_tables=True)
    assert "| a | b | |" in result

    # links: this gets through (for now)
    htmlstring = '<html><body><article><table><tr><td><a href="link.html">a</a></td></tr></table></article></body></html>'
    result = extract(htmlstring, fast=True, output_format='txt', config=ZERO_CONFIG, include_tables=True)
    assert result == "| a |"

    # link: this is filtered out
    htmlstring = f'<html><body><article><table><tr><td><a href="link.html">{"abc"*100}</a></td></tr></table></article></body></html>'
    result = extract(htmlstring, fast=True, output_format='txt', config=ZERO_CONFIG, include_tables=True)
    assert result == ""
    htmlstring = f'<html><body><article><table><tr><td><a href="link.html">{" "*100}</a></td></tr></table></article></body></html>'
    result = extract(htmlstring, fast=True, output_format='txt', config=ZERO_CONFIG, include_tables=True)
    assert result == ""

    htmlstring = """
                 <html><body><article>
                 <table>
                 <tr><td>a</td><td>b</td><td>c</td></tr>
                 <tr><td>a</td><td colspan="2">
                 <p>b</p>
                 <p>c</p>
                 </td></tr>
                 </table>
                 </article></body></html>
                 """
    result = extract(htmlstring, fast=True, output_format='txt', config=ZERO_CONFIG, include_tables=True)
    assert result == "| a | b | c |\n| a | b c | |"

    htmlstring = """
                 <html><body><article>
                 <table>
                 <tr><td>a</td><td>b</td><td>c</td></tr>
                 <tr><td>a</td><td colspan="2">
                 <p>b</p>
                 <p>c</p>
                 </td></tr>
                 <tr><td>a</td><td colspan="2">
                 <p>b</p>
                 <p>c</p>
                 </td></tr>
                 </table>
                 </article></body></html>
                 """
    result = extract(htmlstring, fast=True, output_format='txt', config=ZERO_CONFIG, include_tables=True)
    assert result == "| a | b | c |\n| a | b c | |\n| a | b c | |"

    htmlstring = """
                 <html><body><article>
                 <table>
                 <tr><td>a</td><td>b</td><td>c</td></tr>
                 <tr>
                    <td>a<img src="http://aa.bb/c.jpg" alt="img"/><span>a</span></td>
                    <td><p>b</p><p>c</p></td>
                    <td>d</td>
                 </tr>
                 </table>
                 </article></body></html>
                 """
    result = extract(htmlstring, fast=True, output_format='markdown', config=ZERO_CONFIG,
                     include_images=True, include_tables=True)
    assert result == "| a | b | c |\n| a ![img](http://aa.bb/c.jpg) a | b c | d |"

    htmlstring = """
                 <html><body><article>
                 <table>
                 <tr><td>a</td><td>b</td><td>c</td></tr>
                 <tr>
                    <td><a href="http://aa.bb/"><img src="http://aa.bb/c.jpg" alt="img"/><span>a</span></a></td>
                    <td><p>b</p><p>c</p></td>
                    <td>d</td>
                 </tr>
                 </table>
                 </article></body></html>
                 """
    result = extract(htmlstring, fast=True, output_format='markdown', config=ZERO_CONFIG,
                     include_images=True, include_tables=True)
    assert result == "| a | b | c |\n| ![img](http://aa.bb/c.jpg) a | b c | d |"

    htmlstring = """
                 <html><body><article>
                 <table>
                 <tr><td>a</td><td>b</td><td>c</td></tr>
                 <tr>
                    <td><img src="http://aa.bb/c.jpg" alt="img"/><span>a</span></td>
                    <td><p>b</p><p>c</p></td>
                    <td>d</td>
                 </tr>
                 </table>
                 </article></body></html>
                 """
    result = extract(htmlstring, fast=True, output_format='markdown', config=ZERO_CONFIG,
                     include_images=True, include_tables=True)
    assert result == "| a | b | c |\n| ![img](http://aa.bb/c.jpg) a | b c | d |"

    htmlstring = """
                 <html><body><article>
                 <table>
                 <tr><td>a</td><td>b</td><td>c</td></tr>
                 <tr>
                    <td><img src="http://aa.bb/c.jpg" alt="img1"/><span>a</span><img src="http://aa.bb/c.jpg" alt="img2"/></td>
                    <td><p>b</p><p>c</p></td>
                    <td>d</td>
                 </tr>
                 </table>
                 </article></body></html>
                 """
    result = extract(htmlstring, fast=True, output_format='markdown', config=ZERO_CONFIG,
                     include_images=True, include_tables=True)
    assert result == "| a | b | c |\n| ![img1](http://aa.bb/c.jpg) a ![img2](http://aa.bb/c.jpg) | b c | d |"


def test_list_processing():
    options = DEFAULT_OPTIONS
    # basic lists
    my_doc = "<html><body><article><p>P 1</p><ul><li>Item 1</li><li>Item 2</li></ul><p>P 2</p></article></body></html>"
    my_result = extract(my_doc, fast=True, output_format='txt', config=ZERO_CONFIG)
    assert my_result == "P 1\n- Item 1\n- Item 2\nP 2"
    # malformed lists (common error)
    result = etree.tostring(handle_lists(etree.fromstring('<list>Description of the list:<item>List item 1</item><item>List item 2</item><item>List item 3</item></list>'), options))
    assert result.count(b'List item') == 3
    assert b"Description" in result
    # nested list
    htmlstring = '''<html><body><article>
<ul>
  <li>Coffee</li>
  <li>Tea
    <ul>
      <li>Black tea</li>
      <li>Green tea</li>
    </ul>
  </li>
  <li>Milk</li>
</ul>
</article></body></html>'''
    my_result = extract(htmlstring, fast=True, output_format='xml', config=ZERO_CONFIG)
    expected = '''
    <list rend="ul">
      <item>Coffee</item>
      <item>Tea
        <list rend="ul">
          <item>Black tea</item>
          <item>Green tea</item>
        </list>
      </item>
      <item>Milk</item>
    </list>'''.replace("\n", "").replace(" ", "")
    assert expected in my_result.replace("\n", "").replace(" ", "")
    # description list
    htmlstring = '''<html><body><article>
 <dl>
  <dt>Coffee</dt>
  <dd>Black hot drink</dd>
  <dt>Milk</dt>
  <dd>White cold drink</dd>
</dl>
</article></body></html>'''
    my_result = extract(htmlstring, fast=True, output_format='xml', config=ZERO_CONFIG)
    assert '''
    <list rend="dl">
      <item rend="dt-1">Coffee</item>
      <item rend="dd-1">Black hot drink</item>
      <item rend="dt-2">Milk</item>
      <item rend="dd-2">White cold drink</item>
    </list>''' in my_result
    list_item_with_child = html.fromstring("<list><item><p>text</p></item></list>")
    processed_list = handle_lists(list_item_with_child, options)
    result = [(child.tag, child.text) if child.text is not None else child.tag for child in processed_list.iter()]
    assert result == ["list", "item", ("p", "text")]
    list_item_with_text_and_child = html.fromstring("<list><item>text1<p>text2</p></item></list>")
    processed_list = handle_lists(list_item_with_text_and_child, options)
    result = [(child.tag, child.text) if child.text is not None else child.tag for child in processed_list.iter()]
    assert result == ["list", ("item", "text1"), ("p", "text2")]
    list_item_with_lb = html.fromstring("<list><item>text<lb/>more text</item></list>")
    processed_list = handle_lists(list_item_with_lb, options)
    result = [(child.tag, child.text) if child.text is not None else child.tag for child in processed_list.iter()]
    assert result == ["list", ("item", "text"), "lb"]
    list_with_text_outside_item = html.fromstring("<list>header<item>text</item></list>")
    processed_list = handle_lists(list_with_text_outside_item, options)
    result = [(child.tag, child.text) if child.text is not None else child.tag for child in processed_list.iter()]
    assert result == ["list", ("item", "header"), ("item", "text")]
    empty_list = html.fromstring("<list>   <item>text</item></list>")
    processed_list = handle_lists(empty_list, options)
    assert len(processed_list) == 1
    list_item_with_tail = html.fromstring("<list><item>text</item>tail</list>")
    processed_list = handle_lists(list_item_with_tail, options)
    assert processed_list[0].text == "text tail"
    list_item_with_child_and_tail = html.fromstring("<list><item><p>text</p></item>tail</list>")
    processed_list = handle_lists(list_item_with_child_and_tail, options)
    item_element = processed_list[0]
    assert item_element.tail is not True
    assert item_element[0].tail == "tail"
    list_item_with_child_and_tail = html.fromstring("<list><item><p>text</p>tail1</item>tail</list>")
    processed_list = handle_lists(list_item_with_child_and_tail, options)
    item_element = processed_list[0]
    assert item_element.tail is not True
    assert item_element[0].tail == "tail1 tail"
    list_item_with_child_and_tail = html.fromstring("<list><item><p>text</p>\n</item>tail</list>")
    processed_list = handle_lists(list_item_with_child_and_tail, options)
    item_element = processed_list[0]
    assert item_element.tail is not True
    assert item_element[0].tail == "tail"
    list_item_with_tail_and_nested_list = html.fromstring("<list><item><list><item>text</item></list></item>tail</list>")
    processed_list = handle_lists(list_item_with_tail_and_nested_list, options)
    target_element = processed_list.find(".//item/list")
    assert target_element.tail == 'tail'


def test_code_blocks():
    highlightjs = '''<div class="s-prose js-post-body" itemprop="text">
<p>Code:</p>
<pre class="lang-sql s-code-block"><code class="hljs language-sql">code\n
<span class="hljs-keyword">highlighted</span> more <span class="hljs-keyword">code</span>
</code></pre>
</div>'''
    testresult = extract(highlightjs, config=ZERO_CONFIG, output_format='xml')
    assert '<code>code\n\nhighlighted more code\n</code>' in testresult and 'quote' not in testresult
    github = '''<div class="highlight highlight-source-shell notranslate position-relative overflow-auto" dir="auto"><pre>$ pip install PyGithub</pre><div class="zeroclipboard-container position-absolute right-0 top-0">
    <clipboard-copy aria-label="Copy" class="ClipboardButton btn js-clipboard-copy m-2 p-0 tooltipped-no-delay" data-copy-feedback="Copied!" data-tooltip-direction="w" value="$ pip install PyGithub" tabindex="0" role="button" style="display: inherit;">
      <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-copy js-clipboard-copy-icon m-2">
    <path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path>
</svg>
      <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-check js-clipboard-check-icon color-fg-success d-none m-2">
    <path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"></path>
</svg>
    </clipboard-copy>
  </div></div>
    '''
    testresult = extract(github, config=ZERO_CONFIG, output_format='xml')
    assert '<code>$ pip install PyGithub</code>' in testresult and 'quote' not in testresult
    inline_code = '<div><p>paragraph</p><p>here is <code>some</code> code</p></div>'
    testresult = extract(inline_code, config=ZERO_CONFIG, output_format='xml')
    assert '<code>some</code>' in testresult and 'quote' not in testresult
    w3schools = '''<div class="w3-example"><h3>Example</h3>
<p>Create a class named Person, use the __init__() function to assign values
for name and age:</p>
<div class="w3-code notranslate pythonHigh"><span class="pythoncolor" style="color:black"><span class="pythonnumbercolor" style="color:red">
</span>  <span class="pythonkeywordcolor" style="color:mediumblue">class</span> Person:<br>&nbsp; <span class="pythonkeywordcolor" style="color:mediumblue">def</span> __init__(self, name, age):<br>&nbsp;&nbsp;&nbsp; <span class="pythonnumbercolor" style="color:red">
</span>  self.name = name<br>&nbsp;&nbsp;&nbsp; self.age = age<br><br>p1 = Person(<span class="pythonstringcolor" style="color:brown">"John"</span>, <span class="pythonnumbercolor" style="color:red">
</span>  <span class="pythonnumbercolor" style="color:red">36</span>)<br><span class="pythonnumbercolor" style="color:red">
</span>  <br><span class="pythonkeywordcolor" style="color:mediumblue">print</span>(p1.name)<br><span class="pythonkeywordcolor" style="color:mediumblue">print</span>(p1.age) </span></div>
</div>'''
    testresult = extract(w3schools, config=ZERO_CONFIG, output_format='xml')
    expected = '''<code>
  class Person:<lb/>\xa0 def __init__(self, name, age):<lb/>\xa0\xa0\xa0 
  self.name = name<lb/>\xa0\xa0\xa0 self.age = age<lb/><lb/>p1 = Person("John", 
  36)<lb/>
  <lb/>print(p1.name)<lb/>print(p1.age) </code>'''
    assert expected in testresult and 'quote' not in testresult
    pip = '''<div><p>Code:</p>
<pre lang="python3"><span class="kn">import</span> <span class="nn">openai</span>
<span class="kn">from</span> <span class="nn">openai_function_call</span> <span class="kn">import</span> <span class="n">openai_function</span></pre></div>'''
    expected = '''<code>import openai
from openai_function_call import openai_function</code>'''
    testresult = extract(pip, config=ZERO_CONFIG, output_format='xml')
    assert expected in testresult and 'quote' not in testresult
    medium_js = '''<div><p>Code:</p>
    <pre class="lw lx ly lz ma nq nr ns bo nt ba bj"><span id="fe48" class="nu mo ev nr b bf nv nw l nx ny" data-selectable-paragraph=""><span class="hljs-keyword">import</span> openai_function<br><br><span class="hljs-meta">@openai_function</span></span></pre>'''
    expected = '''<code>import openai_function<lb/><lb/>@openai_function</code>'''
    testresult = extract(medium_js, config=ZERO_CONFIG, output_format='xml')
    assert expected in testresult and 'quote' not in testresult
    medium_ssr = '''<div><p>Code:</p>
    <pre class="lw lx ly lz ma nq nr ns bo nt ba bj"><span id="fe48" class="nu mo ev nr b bf nv nw l nx ny">import openai_function<br><br>@openai_function<br>def sum(a:int, b:int):<br>  &quot;&quot;&quot;Sum description adds a + b&quot;&quot;&quot;</span></pre>'''
    expected = '''<code>import openai_function<lb/><lb/>@openai_function<lb/>def sum(a:int, b:int):<lb/>  """Sum description adds a + b"""</code>'''
    testresult = extract(medium_ssr, config=ZERO_CONFIG, output_format='xml')
    assert expected in testresult and 'quote' not in testresult
    code_el = '''<div><p>Code:</p>
    <pre><code><span>my code</span></code></pre>'''
    expected = '''<code>my code</code>'''
    testresult = extract(code_el, config=ZERO_CONFIG, output_format='xml')
    assert expected in testresult and 'quote' not in testresult


def test_mixed_content_extraction():
    """
    Test extraction from HTML with mixed content.
    """
    html_content = '<html><body><p>Text here</p><img src="img.jpg"/><video src="video.mp4"/></body></html>'
    expected = "Text here"
    result = extract(html_content, fast=False, config=ZERO_CONFIG)
    assert result.strip() == expected, "Mixed content extraction failed"


def test_nonstd_html_entities():
    """
    Test handling non-standard HTML entities.
    """
    html_content = '<html><body><p>Text &customentity; more text</p></body></html>'
    expected = "Text &customentity; more text"
    result = extract(html_content, fast=False, config=ZERO_CONFIG)
    assert result.strip() == expected, "Non-standard HTML entity handling failed"


def test_large_doc_performance():
    """
    Performance test on large HTML documents.
    """
    large_html = '<html><body>' + '<p>Sample text</p>' * 10000 + '</body></html>'
    start = time.time()
    extract(large_html, fast=False, config=ZERO_CONFIG)
    end = time.time()
    assert end - start < 5, "Large document performance issue"


def test_lang_detection():
    """
    Accuracy of language detection.
    """
    samples = [
        {'html': '<html><body><p>Texto en español</p></body></html>', 'expected': 'es'},
        {'html': '<html><body><p>Texte en français</p></body></html>', 'expected': 'fr'},
    ]
    for sample in samples:
        result = extract(sample['html'], fast=False, config=ZERO_CONFIG)
        detected = language_classifier(result, "")
        assert detected == sample['expected'] or not LANGID_FLAG


def test_config_loading():
    "Check if the config file is read correctly."
    with pytest.raises(FileNotFoundError):
        config = use_config(filename="/bogus-dir/bogus-file.txt")

    config = use_config(filename=path.join(RESOURCES_DIR, "newsettings.cfg"))
    assert config is not None


def test_is_probably_readerable():
    """
    Test is_probably_readerable function.
    """
    assert not is_probably_readerable("ABC")

    very_small_str = "hello there"
    small_str = "hello there " * 11
    large_str = "hello there " * 12
    very_large_str = "hello there " * 50
    linebreaks_str = f"{large_str} <br>" * 10

    very_small_doc = load_html(f"<html><p id='main'>{very_small_str}</p></html>")
    small_doc = load_html(f"<html><p id='main'>{small_str}</p></html>")
    large_doc = load_html(f"<html><p id='main'>{large_str}</p></html>")
    very_large_doc = load_html(f"<html><p id='main'>{very_large_str}</p></html>")
    likely_doc = load_html(
        f"<html><p id='main' class='header'>{very_large_str}</p><p id='header' class='article'>{very_large_str}</p><p id='footer' class='body'>{very_large_str}</p></html>"
    )
    unlikely_doc = load_html(
        f"<html><p id='header'>{very_large_str}</p><p class='footer'>{very_large_str}</p></html>"
    )
    visible_doc = load_html(
        f"<html><p id='main' style='display: block'>{very_large_str}</p><p id='main'>{very_large_str}</p><p id='main' aria-hidden='false'>{very_large_str}</p></html>"
    )
    invisible_doc = load_html(
        f"<html><p id='main' style='display: none'>{very_large_str}</p><p id='main' hidden>{very_large_str}</p><p id='main' aria-hidden='true'>{very_large_str}</p></html>"
    )
    linebreaks_doc = load_html(
        f"<html><div>{linebreaks_str * 10}</div></html>"
    )
    no_linebreaks_doc = load_html(f"<html><div>{large_str * 10}</div></html>")

    # should only declare large documents as readerable when default options
    assert not is_probably_readerable(very_small_doc)
    assert not is_probably_readerable(small_doc)
    assert not is_probably_readerable(large_doc)
    assert is_probably_readerable(very_large_doc)

    # should declare small and large documents as readerable when lower min_content_length
    options = {"min_content_length": 120, "min_score": 0}
    assert not is_probably_readerable(very_small_doc, options)
    assert is_probably_readerable(small_doc, options)
    assert is_probably_readerable(large_doc, options)
    assert is_probably_readerable(very_large_doc, options)

    # should only declare largest document as readerable when higher min_content_length
    options = {"min_content_length": 200, "min_score": 0}
    assert not is_probably_readerable(very_small_doc, options)
    assert not is_probably_readerable(small_doc, options)
    assert not is_probably_readerable(large_doc, options)
    assert is_probably_readerable(very_large_doc, options)

    # should declare large documents as readerable when lower min_score
    options = {"min_content_length": 0, "min_score": 4}
    assert not is_probably_readerable(very_small_doc, options)
    assert is_probably_readerable(small_doc, options)
    assert is_probably_readerable(large_doc, options)
    assert is_probably_readerable(very_large_doc, options)

    # should declare large documents as readerable when higher min_score
    options = {"min_content_length": 0, "min_score": 11.5}
    assert not is_probably_readerable(very_small_doc, options)
    assert not is_probably_readerable(small_doc, options)
    assert is_probably_readerable(large_doc, options)
    assert is_probably_readerable(very_large_doc, options)

    # should check id and class attributes
    assert is_probably_readerable(likely_doc)
    assert not is_probably_readerable(unlikely_doc)

    # should check linebreaks in div elements
    assert is_probably_readerable(linebreaks_doc)
    assert not is_probably_readerable(no_linebreaks_doc)

    called = False

    def visibility_checker_invisible(node):
        nonlocal called
        called = True
        return False

    # should use node visibility checker provided as option - not visible
    options = {"visibility_checker": visibility_checker_invisible}
    assert not is_probably_readerable(very_large_doc, options)
    assert called

    called = False

    def visibility_checker_visible(node):
        nonlocal called
        called = True
        return True

    # should use node visibility checker provided as option - visible
    options = {"visibility_checker": visibility_checker_visible}
    assert is_probably_readerable(very_large_doc, options)
    assert called

    # should use default node visibility checker
    assert is_probably_readerable(visible_doc)
    assert not is_probably_readerable(invisible_doc)

    # https://github.com/mozilla/readability/blob/main/test/test-pages/mozilla-2/source.html#L22
    with open(
        path.join(RESOURCES_DIR, "mozilla.org.firefox.developer.html"),
        "r",
        encoding="utf-8",
    ) as f:
        teststring = f.read()

    doc = load_html(teststring)
    assert not is_probably_readerable(doc)


def test_html_conversion():
    "Test conversion from internal XML to HTML output."
    xml = '''<xml>
    <list>
        <item>Item 1</item>
        <item>Item 2</item>
    </list>
    <p>Text</p>
    <head rend="h1">Heading 1</head>
    <head rend="h2">Heading 2</head>
    <head>No attribute</head>
    <hi rend="#i">Italic</hi>
    <hi rend="#b">Bold</hi>
    <hi>No rend</hi>
    <ref target="https://example.com">Link</ref>
    <ref>No href</ref>
</xml>'''
    tree = etree.fromstring(xml)
    html_tree = trafilatura.htmlprocessing.convert_to_html(copy(tree))
    expected_html = '''<html><body>
    <ul>
        <li>Item 1</li>
        <li>Item 2</li>
    </ul>
    <p>Text</p>
    <h1>Heading 1</h1>
    <h2>Heading 2</h2>
    <h3>No attribute</h3>
    <i>Italic</i>
    <strong>Bold</strong>
    <i>No rend</i>
    <a href="https://example.com">Link</a>
    <a href="">No href</a>
</body></html>'''
    assert etree.tostring(html_tree, method='html').decode() == expected_html

    html = "<html><body><article><h1>Title</h1><p>Text.</p></article></body></html>"
    excepted_html = """<html>
  <body>
    <h1>Title</h1>
    <p>Text.</p>
  </body>
</html>"""
    result = extract(html, output_format="html", config=ZERO_CONFIG)
    assert result == excepted_html

    html = "<html><body><article><h1>Title 1</h1><p>Text.</p></article></body></html>"
    excepted_html = """<html>
  <head>
    <meta name="title" content="Title 1"/>
    <meta name="fingerprint" content="f6fd180b8fbe3670"/>
  </head>
  <body>
    <h1>Title 1</h1>
    <p>Text.</p>
  </body>
</html>"""
    result = extract(html, output_format="html", config=ZERO_CONFIG, with_metadata=True)
    assert result == excepted_html


def test_deprecations():
    "Test deprecated function parameters."
    htmlstring = "<html><body><article>ABC</article></body></html>"
    assert extract(htmlstring, no_fallback=True, config=ZERO_CONFIG) is not None
    assert bare_extraction(htmlstring, no_fallback=True, config=ZERO_CONFIG) is not None
    assert bare_extraction(htmlstring, as_dict=True, config=ZERO_CONFIG) is not None
    with pytest.raises(ValueError):
        extract(htmlstring, max_tree_size=100)
    with pytest.raises(ValueError):
        bare_extraction(htmlstring, max_tree_size=100)



if __name__ == '__main__':
    test_deprecations()
    test_config_loading()
    test_trim()
    test_input()
    test_formatting()
    test_extract_with_metadata()
    test_exotic_tags()
    test_images()
    test_links()
    test_htmlprocessing()
    test_extraction_options()
    test_precision_recall()
    test_xmltocsv()
    test_tojson()
    test_python_output()
    test_external()
    test_tei()
    test_table_processing()
    test_list_processing()
    test_code_blocks()
    test_mixed_content_extraction()
    test_nonstd_html_entities()
    test_large_doc_performance()
    test_lang_detection()
    test_is_probably_readerable()
    test_html_conversion()
