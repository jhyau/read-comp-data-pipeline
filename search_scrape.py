import argparse
import io
import re
import os,sys
import time
from typing import Optional

from beautifulsoup_tutorial.fetch import fetch_html_from_url
from beautifulsoup_tutorial.scrape import *

from bs4 import BeautifulSoup, Comment, NavigableString

from requests.exceptions import ConnectionError

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


def is_metadata_page(url: str):
	"""
	Find if url contains "/wiki/", then look for colon after that
	"""
	idx = url.find("/wiki/")
	if idx == -1:
		return False
	else:
		# Get substring starting from right after wiki
		tokens_after_wiki = url[idx+6:].split("/")
		if len(tokens_after_wiki) > 0 and tokens_after_wiki[0].find(":") != -1:
			print(f"Found a metadata page!!! Filter out: {url}")
			return True
		else:
			return False

def filter_wikipedia_a_links(a: BeautifulSoup):
	# Ignore a tags that don't have href
	# Ignore "edit" urls and urls that point to part of the same page with "#"
	# Ignore "improve this article" links
	# Ignore urls with "File" that usually points to some asset like an image
	# Ignore any urls that end with ".svg" or ".jpg", which are images
	# Ignore urls that are about contributing to wikipedia, "Wikipedia:"
	# Ignore template pages, "Template:"
	# Ignore urls about help for setting up/writing wikipedia articles, "Help:"
	# Ignore urls about categories, "Category:"
	# Ignore urls about the quality of the articles for now, "Talk:"
	# TODO: for now, ignore non-wikipedia urls
	return a.has_attr("href") and a.get_text().lower().find("edit") == -1 \
	and a.get_text().lower().find("improve this article") == -1 \
	and a["href"].find("File:") == -1 \
	and a["href"].find("Wikipedia:") == -1 \
	and a["href"].find("Template:") == -1 \
	and a["href"].find("Template_talk:") == -1 \
	and a["href"].find("Help:") == -1 \
	and a["href"].find("Category:") == -1 \
	and a["href"].find("Talk:") == -1 \
	and a["href"].find("User:") == -1 \
	and a["href"].find("User_talk:") == -1 \
	and a["href"].find("Special:Contributions") == -1 \
	and not is_metadata_page(a["href"]) \
	and not a["href"].endswith(".svg") \
	and not a["href"].endswith(".jpg") \
	and not a["href"].endswith(".png") \
	and not a["href"].endswith(".js") \
	and not a["href"].endswith(".mp3") \
	and not a["href"].endswith(".mp4") \
	and not a["href"].startswith("#") \
	and a["href"].lower().find("edit") == -1 \
	and not (a["href"].startswith("http") and a["href"].find("wikipedia.org") == -1)


def accepted_url(url: str):
	return url.find("File:") == -1 \
	and url.find("Wikipedia:") == -1 \
	and url.find("Template:") == -1 \
	and url.find("Template_talk:") == -1 \
	and url.find("Help:") == -1 \
	and url.find("Category:") == -1 \
	and url.find("Talk:") == -1 \
	and url.find("User:") == -1 \
	and url.find("User_talk:") == -1 \
	and url.find("Special:Contributions") == -1 \
	and url.lower().find("edit") == -1 \
	and not is_metadata_page(url) \
	and not url.endswith(".svg") \
	and not url.endswith(".jpg") \
	and not url.endswith(".png") \
	and not url.endswith(".js") \
	and not url.endswith(".mp3") \
	and not url.endswith(".mp4") \
	and not url.startswith("#") \
	and not (url.startswith("http") and url.find("wikipedia.org") == -1)


def explore_page(name: str, href: str, seen_urls: list, data_path: str, logger: io.TextIOWrapper):
	"""
	Retrieve all the content on the page
	Prevent duplicates by verifying it's not in the seen_urls list
	writer: io.TextIOWrapper
	"""
	# Load the web page
	full_url = prepare_full_url(href)

	# Try loading page 3 times with 3 second sleep. If not, then log as page that didn't get scraped
	response = None
	retry = 3
	while (response is None):
		if retry == 0:
			# Can't scrape this page, log it and return
			logger.write("$$$$$$$$$$$$$$ Retried 3 times, unable to scrape page: " + full_url + "\n")
			print(f"Retried 3 times, unable to scrape page {full_url}. Returning")
			return
		try:
			response = fetch_html_from_url(full_url)
			html = BeautifulSoup(response.content, "html.parser")
		except Exception as e:
			print(f"Exception: {e}. Sleep for 30 seconds...")
			response = None
			time.sleep(30)
			retry -= 1

	# Wait 3 seconds between each request
	# time.sleep(3)
	# If url redirected to a previously seen url, then return. No need to explore this page
	if identify_redirecting_urls(seen_urls, response) or href in seen_urls or not accepted_url(response.url):
		print(f"*********Redirected or already seen url or should be filtered out. Returning***************")
		logger.write(f"*********Redirected or already seen url or should be filtered out. Returning***************\n")
		return

	# Mark this url as seen
	seen_urls.append(href)
	print("Exploring url: ", full_url)
	print("seen urls list: ", seen_urls)
	logger.write("Exploring url: " + full_url + "\n")
	logger.write("seen urls list: " + str(seen_urls) + "\n")

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
	# visible_text = text_from_html(response.content)
	# print("=============visible text==============")
	# print(visible_text)

	# If overall_div is still None, then can't scrape this page
	if overall_div is None:
		logger.write("overall_div is None. Returning...\n")
		print("overall_div is None. Returning")
		return

	# Create new text file for this article
	if title is None:
		# Can't find title
		# raise Exception("Title couldn't be found for article!")
		logger.write("Title couldn't be found for article! Returning\n")
		print("Title couldn't be found for article!")
		return

	# Extract all the content on the page
	# Set any header type tags to be the "topic" and the text within to be the description
	# Separate topic and description with a tab "\t"

	overall_visible_str_cat = u" ".join(overall_div.strings)
	# Remove all double spaces, replace with single space
	overall_visible_str_cat = overall_visible_str_cat.replace("  ", " ")
	# print(overall_visible_str_cat)

	containsLaw = False
	# This won't work since the term "notes" can show up earlier, not just at the header
	# Should have at least 2 of these terms to pass
	# notes_idx = overall_visible_str_cat.lower().find("notes")
	# references_idx = overall_visible_str_cat.lower().find("references")
	# if notes_idx == -1 and references_idx != -1:
	# 	idx = references_idx
	# elif notes_idx != -1 and references_idx == -1:
	# 	idx = notes_idx
	# elif notes_idx != -1 and references_idx != -1:
	# 	idx = min(notes_idx, references_idx)
	# else:
	# idx = len(overall_visible_str_cat)
	# print("Idx to check if article is about law: " + str(idx))
	law_check = overall_visible_str_cat.lower().find("law") != -1
	legal_check = overall_visible_str_cat.lower().find("legal") != -1
	statute_check = overall_visible_str_cat.lower().find("statute") != -1
	legislative_check = overall_visible_str_cat.lower().find("legislative") != -1
	judicial_check = overall_visible_str_cat.lower().find("judicial") != -1
	legislation_check = overall_visible_str_cat.lower().find("legislation") != -1
	gov_check = overall_visible_str_cat.lower().find("government") != -1
	court_check = overall_visible_str_cat.lower().find("court") != -1
	due_process = overall_visible_str_cat.lower().find("due process") != -1
	jurisprudence = overall_visible_str_cat.lower().find("jurisprudence") != -1
	jury = overall_visible_str_cat.lower().find("jury") != -1
	checks = [law_check, legal_check, statute_check, legislative_check, judicial_check, legislation_check, gov_check, \
	court_check, due_process, jurisprudence]

	num_pass = sum(checks)
	print(f"number of law checks that pass: {num_pass} / {len(checks)}")
	if num_pass >= 2:
		print(f"Contains law: {law_check}")
		print(f"Contains legal: {legal_check}")
		print(f"Contains statute: {statute_check}")
		print(f"Contains legislative: {legislative_check}")
		print(f"Contains judicial: {judicial_check}")
		print(f"Contains legislation: {legislation_check}")
		print(f"Contains government: {gov_check}")
		print(f"Contains court: {court_check}")
		print(f"Contains due process: {due_process}")
		print(f"Contains jurisprudence: {jurisprudence}")
		print(f"Contains jury: {jury}")
		logger.write(f"Contains law: {law_check}\n")
		logger.write(f"Contains legal: {legal_check}\n")
		logger.write(f"Contains statute: {statute_check}\n")
		logger.write(f"Contains legislative: {legislative_check}\n")
		logger.write(f"Contains judicial: {judicial_check}\n")
		logger.write(f"Contains legislation: {legislation_check}\n")
		logger.write(f"Contains government: {gov_check}\n")
		logger.write(f"Contains court: {court_check}\n")
		logger.write(f"Contains due process: {due_process}\n")
		logger.write(f"Contains jurisprudence: {jurisprudence}\n")
		logger.write(f"Contains jury: {jury}\n")
		containsLaw = True

	if not containsLaw:
		print(f"Does not contain law or legal content: {full_url} \n")
		logger.write(f"Does not contain law or legal content: {full_url} \n")
		return

	# Replace spaces in article with underscore, replace / with hyphen
	article_path = os.path.join(data_path, title.replace(" ", "_").replace("/", "-"))
	if os.path.exists(article_path + ".txt"):
		writer = open(article_path + "_SeenUrls" + str(len(seen_urls)) + ".txt", "w")
	else:
		writer = open(article_path + ".txt", "w")

	# ul for bulleted unordered list, ol for ordered list, dl for description list
	# Go through all children in the overall_div
	print("\n")
	# final_output = ""
	# for t in overall_div.find_all(string=True):
	# 	if (tag_visible(t)):
	# 		print(f"line: {t.get_text()} , and tag: {t.name}")
	# 		# final_output += t.get_text() + " "
	# 	else:
	# 		print("not visible")
	# print(final_output)

	# Find all headers, creating a list of headers where each element is a tuple of (header, list of parents)
	# Sometimes there's no "[edit]" in the header, need to handle that case
	headers_have_edit = False
	all_h = overall_div.find_all(re.compile('^h[1-6]$'))
	header_strs_only = []
	header_map_list = []
	# Include the title in header_map_list to handle first text written out to file
	header_map_list.append((title, []))
	prev_h2 = ""
	prev_h3 = ""
	prev_h4 = ""
	prev_h5 = ""
	for elem in all_h:
		index = elem.get_text().find("[edit]")
		if index == -1:
			key = elem.get_text().strip()
		else:
			headers_have_edit = True
			key = elem.get_text()[:index].strip()
		# each header in to the list in a tuple, with a list of its parents
		header_strs_only.append(key)
		if elem.name == "h2":
			# No parents for h2, since h1 is the title
			prev_h2 = key
			header_map_list.append((key, []))	
		elif elem.name == "h3":
			# One parent, h2
			prev_h3 = key
			header_map_list.append((key, [prev_h2]))
		elif elem.name == "h4":
			# TWo parents, h2 and h3
			prev_h4 = key
			header_map_list.append((key, [prev_h2, prev_h3]))
		elif elem.name == "h5":
			# Three parents, h2, h3, and h4
			prev_h5 = key
			header_map_list.append((key, [prev_h2, prev_h3, prev_h4]))
		elif elem.name == "h6":
			# Four parents: h2, h3, h4, and h5
			header_map_list.append((key, [prev_h2, prev_h3, prev_h4, prev_h5]))
			
	# print(all_h)
	print("\n")
	print("List of headers: " + str(header_map_list))
	logger.write("\nList of headers: " + str(header_map_list) + "\n")

	# Ignore info in tables(?)
	table_strings = []
	all_tables = overall_div.find_all("table")
	for tbody in all_tables:
		# print("&&&&&&&&&&&&&&&&&&&Table string&&&&&&&&&&&&&&&&&")
		table_str = u" ".join(tbody.strings)
		table_str = table_str.replace("  ", " ").replace("\n", " ").strip()
		# print(table_str)
		logger.write("&&&&&&&&&&&&&&&&&&&Table string&&&&&&&&&&&&&&&&&\n")
		logger.write(table_str + "\n")
		table_strings.append(table_str)

	# TODO: ignore info in figures?

	header = title
	hdr_index = 0 # Headers must be found in order, otherwise it's not a header
	description = ""
	num = len(overall_visible_str_cat.split("\n"))
	print(f"Number of tokens split by newline: {num}")
	logger.write(f"Number of tokens split by newline: {num}\n")
	# Iterate through the tokens in the concatenated string of all visible text in overal_div (main body content)
	# split by newline
	# Remove anything in brackets like "[<stuff>]", can be reference or something else for Wikipedia article
	# https://stackoverflow.com/questions/22225006/how-to-replace-only-the-contents-within-brackets-using-regular-expressions
	for text in overall_visible_str_cat.split("\n"):
		print("line: " + text)
		logger.write("line: " + text + "\n")
		if text.find("[ edit ]") != -1 or text.strip() in header_strs_only:
			if hdr_index == len(header_strs_only):
				print("Went through all headers, continue")
				logger.write("Went through all headeres, continue\n")
				description += text + " "
				continue
			print("found header...")
			logger.write("found header...\n")
			
			if text.strip() != header_strs_only[hdr_index] \
			and text[:text.find("[ edit ]")].strip() != header_strs_only[hdr_index]:
				print(f"Wrong order, this is not a header: {text.strip()}")
				logger.write(f"Wrong order, this is not a header: {text.strip()}\n")
				description += text + " "
				continue

			# This is a header
			# Find all parents if it is a subheader
			assert(header_map_list[hdr_index][0] == header)
			total_header = ""
			for h in header_map_list[hdr_index][1]:
				total_header += h + " - "
			total_header += header
			
			# Remove string from tables
			# TODO: remove unicode characters?
			# string_clean = re.sub(r"[^\x00-\x7F]+", "", description)
			# print(string_clean)
			for s in table_strings:
				if description.find(s) != -1:
					print(f"FOUND TABLE STRING IN DESCRIPTION: {s}")
					logger.write(f"FOUND TABLE STRING IN DESCRIPTION: {s}\n")
					description = description.replace(s, "")

			# Remove references in "[]"
			# TODO: if the description is empty, like for a h2 without any subtext, don't include in the output file
			description = re.sub(r"\[.*?\]", "", description)
			writer.write(total_header + "\t" + description.strip() + "\n")
			if text.find("[ edit ]") != -1:
				header = text[:text.find("[ edit ]")].strip() # substring up to [edit]
			else:
				header = text.strip()
			description = ""
			hdr_index += 1 # increment to next expected header

			# TODO: For now, ignore the info in "Notes" and "References" to external urls
			# Also ignore "See Also" sections?
			if header.find("References") != -1 or header.find("Notes") != -1:
				print("Found references or Notes, breaking...")
				logger.write("Found references or Notes, breaking...\n")
				break
		else:
			description += text + " "
	
	# Write out the final header's info if didn't end earlier
	if description != "":
		print("Final header and description")
		total_header = ""
		for h in header_map_list[-1][1]:
			total_header += h + " - "
		total_header += header

		for s in table_strings:
			if description.find(s) != -1:
				print(f"FOUND TABLE STRING IN DESCRIPTION: {s}")
				logger.write(f"FOUND TABLE STRING IN DESCRIPTION: {s}\n")
				description = description.replace(s, "")

		description = re.sub(r"\[.*?\]", "", description)
		writer.write(total_header + "\t" + description.strip() + "\n")

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
	# return

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
			logger.write("neighboring url to crawl through next: " + link + "\n\n")
			explore_page(n, link, seen_urls, data_path, logger)
			


def starting_run():
	parser = argparse.ArgumentParser(description='Pass in starting URL for wikipedia law scraping')
	parser.add_argument('--url', default=URL, type=str,
	                    help='wikipedia URL to start scraping for law/legal content ')
	parser.add_argument('--data_path', default="./scraped_wiki_article_data", type=str,
		help="path to create an output directory to save the scraped files")
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
	data_path = args.data_path
	os.makedirs(data_path, exist_ok=True)

	# Logger
	log_path = os.path.join(data_path, "log.txt")
	logger = open(log_path, "w")

	# DFS
	print(unseen_urls)
	logger.write("unseen urls: " + str(unseen_urls) + "\n")
	count = 0
	for url in unseen_urls:
		# if (count == 10):
		# 	break
		# if url[1].lower().find("trust") == -1:
		# 	continue
		print("From starting page, exploring url: ", url)
		logger.write("From starting page, exploring url: " + str(url) + "\n")
		explore_page(url[0], url[1], seen_urls, data_path, logger)
		count += 1
	print(f"!!!!!!!!!!!!!Finished!!!!!!!!!! Number of main urls searched through: {count}")
	logger.write(f"!!!!!!!!!!!!!Finished!!!!!!!!!! Number of main urls searched through: {count}")
	logger.close()

starting_run()

# Logger
# log_path = os.path.join("./scraped_wiki_article_data", "log.txt")
# logger = open(log_path, "w")
# explore_page("Hong Kong", "/wiki/Hong_Kong", [], "./scraped_wiki_article_data", logger)
