from beautifulsoup_tutorial.fetch import fetch_html_from_url
from beautifulsoup_tutorial.scrape import scrape_page_metadata, get_wikipedia_page_title, get_wikipedia_page_main_content

from bs4 import BeautifulSoup

URL = "https://en.wikipedia.org/wiki/List_of_areas_of_law"
BASE_URL = "https://en.wikipedia.org"

def explore_page(html: BeautifulSoup, name: str, href: str):
	# ul for bulleted unordered list, ol for ordered list, dl for description list
	#Go through all children in the overall_div
	for child in html.children:
		print(child.extract().name)
		if (child.extract().name == "ul"):
			print("bulleted list detected!")
			for gc in child.children:
				print(gc)
				print(gc.get_text())
				# Even though docs say with .find() can't find a given tag, it returns None,
				# seems like it actually returns -1
				if (gc.find("a") is not None and gc.find("a") != -1):
					# Found "a" tag in this element
					print("href: " + gc.find("a")["href"])


def starting_run():
	resp = fetch_html_from_url(URL)
	html = BeautifulSoup(resp.content, "html.parser")
	# Get the wikipedia page visible title
	title = get_wikipedia_page_title(html)
	# Get the main content div
	overall_div = get_wikipedia_page_main_content(html)

	# Finding all p tags within the div
	overall_p = overall_div.find_all("p")
	for p in overall_p:
		print(p.get_text())
	# headline = html.find("span", class_="mw-headline")
	# print("headline: " + headline.string)

	# Find all tag a for hrefs in the main content that will need to be crawled through
	# The pages might have citations, where the href is pointing to somewhere in the same page with
	# href="#cite note-1" for example which leads to non-wikipedia page.
	# Also they have "edit" links, ignore those
	all_a = overall_div.find_all("a")

	unseen_urls = []
	seen_urls = []

	for a in all_a:
		# Ignore "edit" urls and urls that point to part of the same page with "#"
		# TODO: for now, ignore non-wikipedia urls
		if (a.get_text().find("edit") == -1 and not a["href"].startswith("#")
			and not (a["href"].startswith("https") and a["href"].find("wikipedia") == -1)):
			unseen_urls.append((a.get_text(), a["href"]))

	# DFS
	print(unseen_urls)
	for url in unseen_urls:
		seen_urls.append(url)


starting_run()