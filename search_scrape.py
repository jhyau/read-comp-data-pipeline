import argparse
import io
import os,sys
from typing import Optional

from beautifulsoup_tutorial.fetch import fetch_html_from_url
from beautifulsoup_tutorial.scrape import *

from bs4 import BeautifulSoup, Comment, NavigableString

URL = "https://en.wikipedia.org/wiki/List_of_areas_of_law"
REDIRECTING_URL = "https://en.wikipedia.org/wiki/Corporate_compliance_law"
ANOTHER_URL = "https://en.wikipedia.org/wiki/Category:Corporate_law"
BASE_URL = "https://en.wikipedia.org"


def prepare_full_url(href: str) -> str:
	if href.startswith("/"):
		full_url = remove_pound_from_urls(BASE_URL + href)
	else:
		full_url = remove_pound_from_urls(href)
	return full_url


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
		compare = remove_pound_from_urls(resp.url)
		if compare == full_url or full_url.startswith(compare):
			print("*****Detected redirected url*********")
			print("full_url: ", full_url)
			print("resp.url: ", resp.url)
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
	# Ignore "improve this article" links
	# Ignore urls with "File" that usually points to some asset like an image
	# Ignore any urls that end with ".svg" or ".jpg", which are images
	# Ignore urls that are about contributing to wikipedia, "Wikipedia:"
	# Ignore template pages, "Template:"
	# Ignore urls about help for setting up/writing wikipedia articles, "Help:"
	# TODO: for now, ignore non-wikipedia urls
	return a.has_attr("href") and a.get_text().lower().find("edit") == -1 \
	and a.get_text().lower().find("improve this article") == -1 \
	and a["href"].find("File:") == -1 \
	and a["href"].find("Wikipedia:") == -1 \
	and a["href"].find("Template:") == -1 \
	and a["href"].find("Help:") == -1 \
	and not a["href"].endswith(".svg") \
	and not a["href"].endswith(".jpg") \
	and not a["href"].endswith(".png") \
	and not a["href"].endswith(".js") \
	and not a["href"].endswith(".mp3") \
	and not a["href"].endswith(".mp4") \
	and not a["href"].startswith("#") \
	and a["href"].lower().find("edit") == -1 \
	and not (a["href"].startswith("http") and a["href"].find("wikipedia.org") == -1)


def explore_page(name: str, href: str, seen_urls: list, data_path: str):
	"""
	Retrieve all the content on the page
	Prevent duplicates by verifying it's not in the seen_urls list
	writer: io.TextIOWrapper
	"""
	# Load the web page
	full_url = prepare_full_url(href)
	response = fetch_html_from_url(full_url)
	html = BeautifulSoup(response.content, "html.parser")

	# If url redirected to a previously seen url, then return. No need to explore this page
	if identify_redirecting_urls(seen_urls, response) or href in seen_urls:
		return

	# Mark this url as seen
	seen_urls.append(href)
	print("Exploring url: ", full_url)
	print("seen urls list: ", seen_urls)

	# Get the wikipedia page visible title
	title = get_wikipedia_page_title(html)
	if title is None:
		title = get_wikipedia_first_heading(html)
	# Get the main content div
	overall_div = get_wikipedia_page_main_content(html)
	# TODO: handle when overall_div is None
	if overall_div is None:
		overall_div = get_wikipedia_body_content(html)

	# If the page doesn't ever mention "law" or "legal", then treat as unrelated content and skip the page
	# Note that sometimes some things are in b tag for bold...
	# Retrieve all visible text from the page
	containsLaw = False
	visible_text = text_from_html(response.content)
	# print("=============visible text==============")
	# print(visible_text)
	if visible_text.lower().find("law") != -1 or visible_text.lower().find("legal") != -1 \
	or visible_text.lower().find("statute") != -1 \
	or visible_text.lower().find("legislative") != -1:
		containsLaw = True
	
	if not containsLaw:
		print(f"Does not contain law or legal content: {full_url} \n")
		return

	# Create new text file for this article
	if title is None:
		# Can't find title
		raise Exception("Title couldn't be found for article!")

	# Replace spaces in article with underscore
	article_path = os.path.join(data_path, title.replace(" ", "_"))
	writer = open(article_path + ".txt", "w")

	# Extract all the content on the page
	# Set any header type tags to be the "topic" and the text within to be the description
	# Separate topic and description with a tab "\t"
	print("\n")
	# texts = overall_div.findAll(string=True)
	# visible_texts = list(filter(tag_visible, texts))
	# print(u" ".join(t.strip() for t in visible_texts))

	overall_visible_str_cat = u" ".join(overall_div.strings)
	print(overall_visible_str_cat)

	# ul for bulleted unordered list, ol for ordered list, dl for description list
	# Go through all children in the overall_div
	print("\n")
	# final_output = ""
	# for t in overall_div.findAll(string=True):
	# 	if (tag_visible(t)):
	# 		print(f"line: {t.get_text()} , and tag: {t.name}")
	# 		# final_output += t.get_text() + " "
	# 	else:
	# 		print("not visible")
	# print(final_output)

	# Find all headers, creating a map of h2 --> list of subheaders
	all_h = overall_div.find_all(re.compile('^h[1-6]$'))
	headers = {}
	prev_h2 = ""
	for elem in all_h:
		index = elem.get_text().find("[edit]")
		if index == -1:
			key = elem.get_text()
		else:
			key = elem.get_text()[:index]
		# store h2 header as key, have list of subheaders as value
		if elem.name == "h2":
			prev_h2 = key
			headers[prev_h2] = []
		elif elem.name != "h1":
			headers[prev_h2].append(key)
	print(all_h)
	print("\n")
	print("map of h2 headers to subheaders: " + str(headers))

	header = title
	description = ""
	subheaders = []
	prev_h2_header = ""
	# Iterate through the tokens in the concatenated string of all visible text in overal_div (main body content)
	# split by newline
	# TODO: remove anything in brackets like "[<stuff>]", can be reference or something else for Wikipedia article
	# TODO: maybe also remove anything in "<stuff>"?
	for text in overall_visible_str_cat.split("\n"):
		print("line: " + text)
		if text.find("[ edit ]") != -1:
			print("found header...")
			# This is a header
			# If it's a subheader of a h2 header, include that information
			if header in subheaders:
				print("found subheader")
				header = prev_h2_header + " - " + header
			writer.write(header + "\t" + description.strip() + "\n")
			header = text[:text.find("[ edit ]")].strip() # substring up to [edit]
			description = ""

			# TODO: For now, ignore the info in "Notes" and "References" to external urls
			# Also ignore "See Also" sections?
			if header.find("References") != -1 or header.find("Notes") != -1:
				break

			# Check if this header is a key (h2)
			if header in headers:
				print("Found h2 header")
				subheaders = headers[header]
				prev_h2_header = header
		else:
			description += text + " "
	# for child in visible_texts:
	# 	# print(child.name + ": " + child.get_text() + " parent: " + parent_name)
	# 	print(str(type(child)) + " : " + str(child.name) + " : " + child.get_text())
	# 	# Find if NavigableString
	# 	if (isinstance(child, NavigableString)):
	# 		print(child.name)
	# 		print(str(child.string))
	# 	# Find header
	# 	if (str(child.name).startswith("h")):
	# 		# write out the previous header and description before overwriting
	# 		writer.write(header + "\t" + description + "\n")
	# 		header = child.get_text()
	# 		description = ""

	# 		# If header is "References", then stop scraping page (considered to be done)
	# 		# TODO: do we want to get references content?
	# 		if header == "References" or header == "":
	# 			break
	# 	elif (str(child.extract().name) == "ul" or str(child.extract().name) == "ol" or str(child.extract().name) == "dl"):
	# 		elems_str = get_list_elements(child)
	# 		print(elems_str)
	# 	# elif not tag_visible(child):
	# 	# 	# Problem is parent of a BeautifulSoup object is defined as None
	# 	# 	# https://beautiful-soup-4.readthedocs.io/en/latest/#parent
	# 	# 	print("skipping this tag...")
	# 	# 	# If the child's text is not visible content, ignore
	# 	# 	continue
	# 	elif (str(child.name) in ['style', 'script', 'head', 'meta', '[document]']):
	# 		# Don't need to use any info here
	# 		print("skipping")
	# 		continue
	# 	elif (isinstance(child, Comment)):
	# 		# Don't store comment info
	# 		print("skipping")
	# 		continue
	# 	else:
	# 		description += child.get_text()
	# 		# print("bulleted list detected!")
	# 		# for gc in child.children:
	# 		# 	print(gc)
	# 		# 	print(gc.get_text())
	# 		# 	# Even though docs say with .find() can't find a given tag, it returns None,
	# 		# 	# seems like it actually returns -1
	# 		# 	if (gc.find("a") is not None and gc.find("a") != -1):
	# 		# 		# Found "a" tag in this element
	# 		# 		print("href: " + gc.find("a")["href"])

	# Close the writer
	writer.close()
	return

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
			print("neighboring url to crawl through next: ", link)
			# explore_page(n, link, seen_urls, writer)
			


def starting_run():
	parser = argparse.ArgumentParser(description='Pass in starting URL for wikipedia law scraping')
	parser.add_argument('--url', default=URL, type=str,
	                    help='wikipedia URL to start scraping for law/legal content ')
	# parser.add_argument('--sum', dest='accumulate', action='store_const',
	#                     const=sum, default=max,
	#                     help='sum the integers (default: find the max)')
	args = parser.parse_args()

	resp = fetch_html_from_url(args.url)
	html = BeautifulSoup(resp.content, "html.parser")
	# Get the wikipedia page visible title
	title = get_wikipedia_page_title(html)
	if title is None:
		title = get_wikipedia_first_heading(html)
	# Get the main content div
	overall_div = get_wikipedia_page_main_content(html)

	# Finding all p tags within the div
	# overall_p = overall_div.find_all("p")
	# for p in overall_p:
	# 	print(p.get_text())
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
	data_path = "./scraped_wiki_article_data"
	os.makedirs(data_path, exist_ok=True)
	#writer = open("wikipedia_law_scrape_info.txt", "a")

	# DFS
	print(unseen_urls)
	count = 0
	for url in unseen_urls:
		if (count == 10):
			break
		# if url[1].lower().find("trust") == -1:
		# 	continue
		# seen_urls.append(url)
		# response = fetch_html_from_url(BASE_URL + url[1])
		# page_html = BeautifulSoup(response.content, "html.parser")
		print("From starting page, exploring url: ", url)
		explore_page(url[0], url[1], seen_urls, data_path)
		count += 1

	# Close the writer
	#writer.close()


starting_run()