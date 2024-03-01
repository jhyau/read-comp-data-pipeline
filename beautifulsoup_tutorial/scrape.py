"""Scrape metadata attributes from a requested URL."""
import re
from typing import Optional

from bs4 import BeautifulSoup, Comment
from requests import Response


def get_list_elements(list_items: BeautifulSoup):
    """
    Get all elements in ul, ol, or dl into one line
    """
    print("bulleted list detected!")
    elements = []
    if list_items.extract().name == "ul" or list_items.extract().name == "ol":
        children = list_items.find_all("li")
    else:
        # dl case
        children = list_items.find_all("dt")
    for gc in children:
        # Even though docs say with .find() can't find a given tag, it returns None,
        # seems like it actually returns -1
        elements.append(gc.get_text())
    # Join the strings together with comma
    return ", ".join(elements)


def tag_visible(element):
    """
    From here: https://stackoverflow.com/questions/1936466/how-to-scrape-only-visible-webpage-text-with-beautifulsoup
    New version, just use <BeautifulSoup>.strings
    https://stackoverflow.com/a/41140750
    """
    if element.parent.name in ['style', 'script', 'head', 'title', 'meta', '[document]']:
        return False
    if isinstance(element, Comment):
        return False
    # elif re.match(r"[\s\r\n]+",str(element)):
    #     # eliminate white spaces and new lines
    #     return False
    return True


def text_from_html(body):
    soup = BeautifulSoup(body, 'html.parser')
    # texts = soup.find_all(string=True)
    texts = soup.strings
    # print(type(texts[0]))
    # visible_texts = filter(tag_visible, texts)  
    return u" ".join(t.strip() for t in texts)


def get_wikipedia_first_heading(html: BeautifulSoup) -> Optional[str]:
    """
    If page title doesn't exist, look for first heading instead
    NOTE: Sometimes .string returns empty if there are more children tags, use get_text() instead
    """
    heading = html.find("h1", id="firstHeading")
    if heading is not None and heading != -1:
        print("wikipedia first heading since page title doesn't exist: " + heading.get_text())
        return heading.get_text()
    else:
        return None


def get_wikipedia_page_title(html: BeautifulSoup) -> Optional[str]:
    """
    Find the span with class "mw-page-title-main"
    """
    title = html.find("span", class_="mw-page-title-main")
    if title is not None and title != -1:
        print("wikipedia page title: " + title.get_text())
        return title.string
    else:
        return None


def get_wikipedia_page_main_content(html: BeautifulSoup) -> Optional[BeautifulSoup]:
    """
    Find the div with the wikipedia page's main content
    Subsection headlines are span with class "mw-headline"
    Returns None if the corresponding class is not found
    """
    overall_div = html.find("div", class_="mw-content-ltr mw-parser-output")
    if overall_div is not None and overall_div != -1:
        return overall_div
    else:
        return None


def get_wikipedia_body_content(html: BeautifulSoup) -> Optional[BeautifulSoup]:
    """
    If the main content div doesn't exist, look for main body content instead
    """
    body = html.find("div", id="mw-content-text")
    if body is not None and body != -1:
        print("wikipedia body content since main content div doesn't exist")
        return body
    else:
        return None



def scrape_page_metadata(resp: Response, url: str) -> dict:
    """
    Parse page & return metadata.

    :param Response resp: Raw HTTP response.
    :param str url: URL of targeted page.

    :return: dict
    """
    html = BeautifulSoup(resp.content, "html.parser")
    metadata = {
        "title": get_title(html),
        "description": get_description(html),
        "image": get_image(html),
        "favicon": get_favicon(html, url),
        "theme_color": get_theme_color(html),
    }
    return metadata


def get_title(html: BeautifulSoup) -> Optional[str]:
    """
    Scrape page title with multiple fallbacks.

    :param BeautifulSoup html: Parsed HTML object.
    :param str url: URL of targeted page.

    :returns: Optional[str]
    """
    title = html.title.string
    if title:
        return title
    elif html.find("meta", property="og:title"):
        return html.find("meta", property="og:title").get("content")
    return html.find("h1").string


def get_description(html: BeautifulSoup) -> Optional[str]:
    """
    Scrape page description.

    :param BeautifulSoup html: Parsed HTML object.
    :param str url: URL of targeted page.

    :returns: Optional[str]
    """
    description = html.find("meta", property="description")
    if description:
        return description.get("content")
    elif html.find("meta", property="og:description"):
        return html.find("meta", property="og:description").get("content")
    return html.p.string


def get_image(html: BeautifulSoup) -> Optional[str]:
    """
    Scrape preview image.

    :param BeautifulSoup html: Parsed HTML object.

    :returns: Optional[str]
    """
    image = html.find("meta", property="image")
    if image:
        return image.get("content")
    elif html.find("meta", {"property": "og:image"}):
        return html.find("meta", {"property": "og:image"}).get("content")
    return html.img.src


def get_favicon(html: BeautifulSoup, url: str) -> Optional[str]:
    """
    Scrape favicon from `icon`, or fallback to conventional favicon.

    :param Response resp: Raw HTTP response.
    :param str url: URL of targeted page.

    :returns: Optional[str]
    """
    if html.find("link", attrs={"rel": "icon"}):
        return html.find("link", attrs={"rel": "icon"}).get("href")
    elif html.find("link", attrs={"rel": "shortcut icon"}):
        return html.find("link", attrs={"rel": "shortcut icon"}).get("href")
    return f"{url.rstrip('/')}/favicon.ico"


def get_theme_color(html: BeautifulSoup) -> Optional[str]:
    """
    Scrape brand color.

    :param BeautifulSoup html: Parsed HTML object.

    :returns: Optional[str]
    """
    if html.find("meta", {"name": "theme-color"}):
        return html.find("meta", {"name": "theme-color"}).get("content")
