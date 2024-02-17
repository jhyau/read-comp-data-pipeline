import io
from typing import Optional

from beautifulsoup_tutorial.fetch import fetch_html_from_url
from beautifulsoup_tutorial.scrape import scrape_page_metadata, get_wikipedia_page_title, get_wikipedia_page_main_content, get_wikipedia_first_heading

from bs4 import BeautifulSoup

URL = "https://en.wikipedia.org/wiki/List_of_areas_of_law"
REDIRECTING_URL = "https://en.wikipedia.org/wiki/Corporate_compliance_law"
ANOTHER_URL = "https://en.wikipedia.org/wiki/Category:Corporate_law"
BASE_URL = "https://en.wikipedia.org"


def is_href_in_neighbors(href: str, neighbors: list):
	for name,url in neighbors:
		if url == href:
			return True
	return False


def identify_redirecting_urls(seen_urls: list, resp: Optional[str]):
	"""
	If a url redirects to a url that was already seen before, mark it a true
	"""
	for href in seen_urls:
		if href.startswith("/"):
			full_url = BASE_URL + href
		else:
			full_url = href
		if remove_pound_from_urls(resp.url) == full_url:
			print("*****Detected redirected url*********")
			return True
	return False


def remove_pound_from_urls(url: str):
	"""
	If the url has a pound sign to point to a specific section of a page, remove that pound sign
	and just save the main page url
	"""
	pound = url.find("#") 
	if (pound != -1):
		return url[:pound]
	else:
		return url


def filter_wikipedia_a_links(a: BeautifulSoup):
	# Ignore a tags that don't have href
	# Ignore "edit" urls and urls that point to part of the same page with "#"
	# TODO: for now, ignore non-wikipedia urls
	return a.has_attr("href") and a.get_text().find("edit") == -1 and not a["href"].startswith("#") and not (a["href"].startswith("http") and a["href"].find("wikipedia") == -1)


def explore_page(name: str, href: str, seen_urls: list, writer: io.TextIOWrapper):
	"""
	Retrieve all the content on the page
	Prevent duplicates by verifying it's not in the seen_urls list
	"""
	# Load the web page
	if href.startswith("/"):
		full_url = remove_pound_from_urls(BASE_URL + href)
	else:
		full_url = remove_pound_from_urls(href)
	response = fetch_html_from_url(full_url)
	html = BeautifulSoup(response.content, "html.parser")

	# If url redirected to a previously seen url, then return. No need to explore this page
	if identify_redirecting_urls(seen_urls, response) or href in seen_urls:
		return

	# Mark this url as seen
	seen_urls.append(href)
	print("Exploring url: ", full_url)

	# Get the wikipedia page visible title
	title = get_wikipedia_page_title(html)
	if title is None:
		title = get_wikipedia_first_heading(html)
	# Get the main content div
	overall_div = get_wikipedia_page_main_content(html)

	# Extract all the content on the page
	# If the page doesn't ever mention "law" or "legal", then treat as unrelated content and skip the page

	# ul for bulleted unordered list, ol for ordered list, dl for description list
	# Go through all children in the overall_div
	# for child in overall_div.children:
	# 	print(child.extract().name)
	# 	if (child.extract().name == "ul"):
	# 		print("bulleted list detected!")
	# 		for gc in child.children:
	# 			print(gc)
	# 			print(gc.get_text())
	# 			# Even though docs say with .find() can't find a given tag, it returns None,
	# 			# seems like it actually returns -1
	# 			if (gc.find("a") is not None and gc.find("a") != -1):
	# 				# Found "a" tag in this element
	# 				print("href: " + gc.find("a")["href"])

	# Get all tag a elements
	neighbors = []
	all_a = overall_div.find_all("a")
	for a in all_a:
		# Ignore "edit" urls and urls that point to part of the same page with "#"
		# If the url redirects to a url that was seen before in seen_urls, ignore
		# TODO: for now, ignore non-wikipedia urls
		if filter_wikipedia_a_links(a) and not is_href_in_neighbors(remove_pound_from_urls(a["href"]), neighbors):
			neighbors.append((a.get_text(), remove_pound_from_urls(a["href"])))

	# recurse through all the unseen tag a elements on this page
	for n,link in neighbors:
		if link not in seen_urls:
			# print("neighboring url to crawl through next: ", link)
			explore_page(n, link, seen_urls, writer)
			


def starting_run():
	resp = fetch_html_from_url(URL)
	html = BeautifulSoup(resp.content, "html.parser")
	# Get the wikipedia page visible title
	title = get_wikipedia_page_title(html)
	if title is None:
		title = get_wikipedia_first_heading(html)
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

	# Keeps track of (text in <a> tag, href)
	unseen_urls = []

	# Only keep track of href
	seen_urls = []

	for a in all_a:
		# Ignore "edit" urls and urls that point to part of the same page with "#"
		# TODO: for now, ignore non-wikipedia urls
		# For urls that have # in the middle, not at the beginning, to point to a specific section of another page,
		# remove anything after # to get the main link to the article
		# print(a)
		if (filter_wikipedia_a_links(a)):
			unseen_urls.append((a.get_text(), remove_pound_from_urls(a["href"])))

	# write content into a textfile output
	writer = open("wikipedia_law_scrape_info.txt", "a")

	# DFS
	print(unseen_urls)
	for url in unseen_urls:
		# if url[1].lower().find("trust") == -1:
		# 	continue
		# seen_urls.append(url)
		# response = fetch_html_from_url(BASE_URL + url[1])
		# page_html = BeautifulSoup(response.content, "html.parser")
		explore_page(url[0], url[1], seen_urls, writer)

	# Close the writer
	writer.close()


starting_run()