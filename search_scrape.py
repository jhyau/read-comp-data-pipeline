import argparse
import io
import re
import os,sys
import time
import datetime
import wikipedia
from typing import Optional

from beautifulsoup_tutorial.fetch import fetch_html_from_url
from beautifulsoup_tutorial.scrape import *

from bs4 import BeautifulSoup, Comment, NavigableString

from requests.exceptions import ConnectionError
from wikipedia.exceptions import DisambiguationError, PageError, RedirectError

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
	# and not is_metadata_page(a["href"]) \
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
	# and not is_metadata_page(url) \
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
	and not url.endswith(".svg") \
	and not url.endswith(".jpg") \
	and not url.endswith(".png") \
	and not url.endswith(".js") \
	and not url.endswith(".mp3") \
	and not url.endswith(".mp4") \
	and not url.startswith("#") \
	and not (url.startswith("http") and url.find("wikipedia.org") == -1)


def get_headers_hierarchy(page: wikipedia.WikipediaPage):
	# Attempt to get a hierarchy of headers
	response = None
	retry = 3
	while (response is None):
		if (retry == 0):
			# Can't load page
			print("3 tries. Unable to fetch/get the page for headers hierarchy. Returning empty list")
			return []
		try:
			response = fetch_html_from_url(page.url)
			html = BeautifulSoup(response.content, "html.parser")
		except Exception as e:
			print(f"Exception: {e}. Sleep for 300 seconds (5 minutes)...")
			page = None
			time.sleep(300)
			retry -= 1

	# Get the main content div
	overall_div = get_wikipedia_page_main_content(html)
	# TODO: handle when overall_div is None
	if overall_div is None:
		overall_div = get_wikipedia_body_content(html)
	# If overall_div still none, then return
	if overall_div is None:
		print("Unable to get body content of page for headeres hierarchy. Returnig empty list")
		return []

	# Sometimes there's no "[edit]" in the header, need to handle that case
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
	return header_map_list, header_strs_only


def create_logger_name(date: datetime.datetime, data_path:str):
	"""
	Create logger path for the loggers during the DFS
	"""
	return os.path.join(data_path, f"{date.year}_{date.month}_{date.day}_{date.hour}_log.txt")


def create_log_dir(current_time: datetime.datetime, data_path: str):
	log_dir = os.path.join(data_path, "log")
	current_log_dir = os.path.join(log_dir, f"{current_time.year}-{current_time.month}-{current_time.day}")
	return current_log_dir


def explore_page(name: str, seen_urls: list, seen_page_titles: set, data_path: str, logger: io.TextIOWrapper, \
	prev_datetime: datetime.datetime, failure_counter: int):
	"""
	Retrieve all the content on the page
	Prevent duplicates by verifying it's not in the seen_urls list
	writer: io.TextIOWrapper
	"""
	# Check if logger is open
	if logger.closed:
		print("Logger is closed. Opening up logger again")
		current_time = datetime.datetime.now()
		current_log_dir = create_log_dir(current_time, data_path)
		current_log_path = create_logger_name(current_time, current_log_dir)
		logger = open(current_log_path, "a")
	# Load the web page
	# Try loading page 3 times with 5 minute sleep. If not, then log as page that didn't get scraped
	page = None
	retry = 3
	while (page is None):
		if retry == 0:
			# Can't scrape this page, log it and return
			logger.write("$$$$$$$$$$$$$$ Retried 3 times, unable to scrape page: " + name + "\n")
			print(f"Retried 3 times, unable to scrape page {name}. Returning")
			failure_counter += 1 # TODO: since this is an int, this won't update in recursive calls...
			# Also maybe should keep track of the urls that have failed to load multiple times
			return failure_counter, logger, ""
		try:
			# response = fetch_html_from_url(full_url)
			# html = BeautifulSoup(response.content, "html.parser")
			page = wikipedia.page(name)
		except DisambiguationError as e:
			# Page is a disambiguation page
			e1 = f"DisambiguationError for {name}. Trying with auto_suggest set to false...\n"
			print(e1)
			logger.write(e1)
			try:
				page = wikipedia.page(name, auto_suggest=False)
			except Exception as f:
				error = f"Error: {f}. This page: {name}, is a disambiguation page. Returning...\n"
				logger.write(error)
				print(error)
				return failure_counter, logger, ""
		except PageError as e:
			# Page doesn't exist, however sometimes this error is due to auto_suggest being true
			# Try calling again with auto_suggest set to false
			e1 = f"Page error for {name}. Trying with auto_suggest set to false...\n"
			print(e1)
			logger.write(e1)
			try:
				page = wikipedia.page(name, auto_suggest=False)
			except Exception as f:
				error = f"Error: {f}. This page: {name}, doesn't exist. Returning...\n"
				logger.write(error)
				print(error)
				return failure_counter, logger, ""
		except RecursionError as err:
			# Reached maximum depth of recursion for python (default 1000)
			# To increase, can do sys.setrecursionlimit(n) but this is dangerous because it can lead to overflow/crash
			# Raise exception to the recursive call and search through branch instead
			error = f"RecursionError: {err}. Raising exception to return to previous level\n"
			print(error)
			if logger.closed:
				current_time = datetime.datetime.now()
				current_log_dir = create_log_dir(current_time, data_path)
				logger = open(current_log_dir, "a")
			logger.write(error)
			return failure_counter, logger, error
			#raise err
		except ValueError as e:
			# ValueError: I/O operation on closed file.
			# open the current datetime as logger
			current_time = datetime.datetime.now()
			e_str = f"ValueError in recursive call: {e} at {str(current_time)}. Open logger at current time\n"
			if logger.closed:
				current_log_dir = create_log_dir(current_time, data_path)
				logger = open(current_log_dir, "a")
			print(e_str)
			logger.write(e_str)
		except Exception as e:
			print(f"Exception: {e}. Sleep for 300 seconds (5 minutes)...")
			page = None
			time.sleep(300)
			retry -= 1

	# Set up logger in hourly increments. Save each day's logs in its own subdirectory
	current_time = datetime.datetime.now()
	current_log_dir = create_log_dir(current_time, data_path)
	if prev_datetime.day != current_time.day or prev_datetime.month != current_time.month or prev_datetime.year != current_time.year:
		# Create new directory for log of new day/month/year
		print("Creating new logger subdirectory")
		os.makedirs(current_log_dir, exist_ok=True)
	
	if prev_datetime.hour != current_time.hour:
		# Only write out seen urls and seen page titles at the end of the current hour's log once
		logger.write("seen urls list: " + str(seen_urls) + "\n")
		logger.write("seen page titles list: " + str(seen_page_titles) + "\n")
		# Close the logger and create a new one
		logger.close()
		log_path = create_logger_name(current_time, current_log_dir)
		print(f"New hour reached. Closing previous logger and creating new logger: {log_path}")
		logger = open(log_path, "a")
	
	# Wait 3 seconds between each request
	# time.sleep(3)
	# If url redirected to a previously seen url, then return. No need to explore this page
	# redirect check identify_redirecting_urls(seen_urls, response)
	if page.url in seen_urls or not accepted_url(page.url):
		print(f"*********Redirected or already seen url or should be filtered out. Returning***************")
		logger.write(f"*********Redirected or already seen url or should be filtered out. Returning***************\n")
		return failure_counter, logger, ""

	# Mark this url as seen
	seen_urls.append(page.url)
	seen_page_titles.add(name)
	# print("seen urls list: ", seen_urls)
	# print("seen page titles set: ", seen_page_titles)
	print(f"Exploring url: {page.url} at {str(current_time)}")
	print("Failure counter so far: " + str(failure_counter))
	logger.write("Exploring url: " + page.url + " at " + str(current_time) +"\n")
	logger.write(f"Failure counter so far: {failure_counter}\n")

	# Get the wikipedia page visible title
	title = page.title

	# If the page doesn't ever mention "law" or "legal", then treat as unrelated content and skip the page
	# Note that sometimes some things are in b tag for bold...
	# Retrieve all visible text from the page
	# visible_text = text_from_html(response.content)

	# Create new text file for this article
	if title is None or title == "":
		# Can't find title
		logger.write("Title couldn't be found for article! Returning\n")
		print("Title couldn't be found for article!")
		return failure_counter, logger, ""

	# Extract all the content on the page
	# Set any header type tags to be the "topic" and the text within to be the description
	# Separate topic and description with a tab "\t"
	overall_visible_str_cat = page.content

	containsLaw = False
	# This won't work since the term "notes" can show up earlier, not just at the header
	# Should have at least 2 of these terms to pass
	law_check = overall_visible_str_cat.lower().find("law") != -1
	legal_check = overall_visible_str_cat.lower().find("legal") != -1
	statute_check = overall_visible_str_cat.lower().find("statute") != -1
	legislative_check = overall_visible_str_cat.lower().find("legislative") != -1
	judicial_check = overall_visible_str_cat.lower().find("judicial") != -1
	legislation_check = overall_visible_str_cat.lower().find("legislation") != -1
	legislature_check = overall_visible_str_cat.lower().find("legislature") != -1
	gov_check = overall_visible_str_cat.lower().find("government") != -1
	court_check = overall_visible_str_cat.lower().find("court") != -1
	due_process = overall_visible_str_cat.lower().find("due process") != -1
	jurisprudence = overall_visible_str_cat.lower().find("jurisprudence") != -1
	jury = overall_visible_str_cat.lower().find("jury") != -1
	checks = [law_check, legal_check, statute_check, legislative_check, judicial_check, legislation_check, gov_check, \
	court_check, due_process, jurisprudence, legislature_check, jury]

	num_pass = sum(checks)
	print(f"number of law checks that pass: {num_pass} / {len(checks)}")
	if num_pass >= 2:
		print(f"Contains law: {law_check}")
		print(f"Contains legal: {legal_check}")
		print(f"Contains statute: {statute_check}")
		print(f"Contains legislative: {legislative_check}")
		print(f"Contains judicial: {judicial_check}")
		print(f"Contains legislation: {legislation_check}")
		print(f"Contains legislature: {legislature_check}")
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
		logger.write(f"Contains legislature: {legislature_check}\n")
		logger.write(f"Contains government: {gov_check}\n")
		logger.write(f"Contains court: {court_check}\n")
		logger.write(f"Contains due process: {due_process}\n")
		logger.write(f"Contains jurisprudence: {jurisprudence}\n")
		logger.write(f"Contains jury: {jury}\n")
		containsLaw = True

	if not containsLaw:
		print(f"Does not contain law or legal content: {page.url} \n")
		logger.write(f"Does not contain law or legal content: {page.url} \n")
		return failure_counter, logger, ""

	# Replace spaces in article with underscore, replace / with hyphen
	article_path = os.path.join(data_path, title.replace(" ", "_").replace("/", "-"))
	if os.path.exists(article_path + ".txt"):
		writer = open(article_path + "_SeenUrls" + str(len(seen_urls)) + ".txt", "w")
	else:
		writer = open(article_path + ".txt", "w")
	print("\n")

	# Find all headers, creating a list of headers where each element is a tuple of (header, list of parents)
	# header_map_list, header_strs_only = get_headers_hierarchy(page)
	# print("\n")
	# print("List of headers: " + str(header_map_list))
	print("From wikipediaPage sections for headers: " + str(page.sections))
	# logger.write("\nList of headers: " + str(header_map_list) + "\n")
	logger.write("From wikipediaPage sections for headers: " + str(page.sections) + "\n")

	# Ignore info in figures
	header = title
	# hdr_index = 0 # Headers must be found in order, otherwise it's not a header
	description = ""
	prev_h2 = ""
	prev_h3 = ""
	prev_h4 = ""
	prev_h5 = ""
	prev_h6 = ""

	num = len(overall_visible_str_cat.split("\n"))
	print(f"Number of tokens split by newline: {num}")
	logger.write(f"Number of tokens split by newline: {num}\n")
	# Iterate through the tokens in the concatenated string of all visible text in overal_div (main body content)
	# split by newline
	# Remove anything in brackets like "[<stuff>]", can be reference or something else for Wikipedia article
	# https://stackoverflow.com/questions/22225006/how-to-replace-only-the-contents-within-brackets-using-regular-expressions
	for text in overall_visible_str_cat.split("\n"):
		# print("line: " + text)
		logger.write("line: " + text + "\n")
		if text.find("====== ") != -1:
			# found h6 header
			print(f"found h6 header {text}")
			logger.write(f"found h6 header {text}\n")

			total_header = ""
			if prev_h2 != "":
				total_header += prev_h2
			if prev_h3 != "":
				total_header += " - " + prev_h3
			if prev_h4 != "":
				total_header += " - " + prev_h4
			if prev_h5 != "":
				total_header += " - " + prev_h5
			if prev_h6 != "":
				total_header += " - " + prev_h6
			if total_header == "":
				total_header += header
			writer.write(total_header + "\t" + description.strip() + "\n")
			# Reset
			header = text.replace("===", "").strip()
			prev_h6 = header
			description = ""
		elif text.find("===== ") != -1:
			# found h5 header
			print(f"found h5 header {text}")
			logger.write(f"found h5 header {text}\n")

			total_header = ""
			if prev_h2 != "":
				total_header += prev_h2
			if prev_h3 != "":
				total_header += " - " + prev_h3
			if prev_h4 != "":
				total_header += " - " + prev_h4
			if prev_h5 != "":
				total_header += " - " + prev_h5
			if prev_h6 != "":
				total_header += " - " + prev_h6
			if total_header == "":
				total_header += header
			writer.write(total_header + "\t" + description.strip() + "\n")
			# Reset
			header = text.replace("===", "").strip()
			prev_h5 = header
			prev_h6 = ""
			description = ""
		elif text.find("==== ") != -1:
			# found h4 header
			print(f"found h4 header {text}")
			logger.write(f"found h4 header {text}\n")

			total_header = ""
			if prev_h2 != "":
				total_header += prev_h2
			if prev_h3 != "":
				total_header += " - " + prev_h3
			if prev_h4 != "":
				total_header += " - " + prev_h4
			if prev_h5 != "":
				total_header += " - " + prev_h5
			if prev_h6 != "":
				total_header += " - " + prev_h6
			if total_header == "":
				total_header += header
			writer.write(total_header + "\t" + description.strip() + "\n")
			# Reset
			header = text.replace("====", "").strip()
			prev_h4 = header
			prev_h5 = ""
			prev_h6 = ""
			description = ""
		elif text.find("=== ") != -1:
			# found h3 header
			print(f"found h3 header {text}")
			logger.write(f"found h3 header {text}\n")

			total_header = ""
			if prev_h2 != "":
				total_header += prev_h2
			if prev_h3 != "":
				total_header += " - " + prev_h3
			if prev_h4 != "":
				total_header += " - " + prev_h4
			if prev_h5 != "":
				total_header += " - " + prev_h5
			if prev_h6 != "":
				total_header += " - " + prev_h6
			if total_header == "":
				total_header += header
			writer.write(total_header + "\t" + description.strip() + "\n")
			# Reset
			header = text.replace("===", "").strip()
			prev_h3 = header
			prev_h4 = ""
			prev_h5 = ""
			prev_h6 = ""
			description = ""
		# if text.find("[ edit ]") != -1 or text.strip() in header_strs_only:
		elif text.find("== ") != -1:
			# h2 header
			print(f"found h2 header {text}")
			logger.write(f"found h2 header {text}\n")

			# This is a h2 header
			# Find all parents if it is a subheader
			# assert(header_map_list[hdr_index][0] == header)
			total_header = ""
			if prev_h2 != "":
				total_header += prev_h2
			if prev_h3 != "":
				total_header += " - " + prev_h3
			if prev_h4 != "":
				total_header += " - " + prev_h4
			if prev_h5 != "":
				total_header += " - " + prev_h5
			if prev_h6 != "":
				total_header += " - " + prev_h6
			if total_header == "":
				total_header += header

			# Remove references in "[]"
			# description = re.sub(r"\[.*?\]", "", description)
			writer.write(total_header + "\t" + description.strip() + "\n")
			# if text.find("[ edit ]") != -1:
			# 	header = text[:text.find("[ edit ]")].strip() # substring up to [edit]
			# else:
			# 	header = text.strip()
			header = text.replace("==", "").strip()
			prev_h2 = header
			prev_h3 = ""
			prev_h4 = ""
			prev_h5 = ""
			prev_h6 = ""
			description = ""
			# hdr_index += 1 # increment to next expected header

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
		# for h in header_map_list[-1][1]:
		# 	total_header += h + " - "
		# total_header += header
		total_header = ""
		if prev_h2 != "":
			total_header += prev_h2
		if prev_h3 != "":
			total_header += " - " + prev_h3
		if prev_h4 != "":
			total_header += " - " + prev_h4
		if prev_h5 != "":
			total_header += " - " + prev_h5
		if prev_h6 != "":
			total_header += " - " + prev_h6
		if total_header == "":
			total_header += header

		# description = re.sub(r"\[.*?\]", "", description)
		writer.write(total_header + "\t" + description.strip() + "\n")

	# Close the writer
	writer.close()
	# return

	# Find neighbors from list of wikipedia page links on the current page, excluding metadata pages
	logger.write(f"Upcoming neighbors: {str(page.links)}\n")
	for n in page.links:
		if n not in seen_page_titles:
			if logger.closed:
				current_time = datetime.datetime.now()
				current_log_dir = create_log_dir(current_time, data_path)
				current_log_path = create_logger_name(current_time, current_log_dir)
				logger = open(current_log_path, "a")
			print("neighboring page to crawl through next: ", n)
			logger.write("neighboring page to crawl through next: " + n + "\n\n")
			try:
				# Need to update failure_counter and logger whenever new loggers are created
				failure_counter, logger, msg = explore_page(n, seen_urls, seen_page_titles, data_path, logger, current_time, failure_counter)
				if msg.find("RecursionError") != -1:
					# Return to previous depth
					print(f"Found RecursionError msg, max depth reached. Return to previous depth: {msg}")
					if logger.closed:
						# If logger is closed, open it again
						current_log_dir = create_log_dir(current_time, data_path)
						current_log_path = create_logger_name(current_time, current_log_dir)
						logger = open(current_log_path, "a")
					logger.write(f"Found RecursionError, max depth reached. Return to previous depth: {msg}\n")
					return failure_counter, logger, ""
			except RecursionError as err:
				# The recurse has reached max recursion depth. Go back to previous depth
				print(f"Recursion at max depth reached. Return to previous depth: {err}")
				if logger.closed:
					# If logger is closed, open it again
					current_log_dir = create_log_dir(current_time, data_path)
					current_log_path = create_logger_name(current_time, current_log_dir)
					logger = open(current_log_path, "a")
				logger.write(f"Recursion at max depth reached. Return to previous depth: {err}\n")
				return failure_counter, logger, f"RecursionError: {err}. Recursion at max depth reached. Return to previous"
			


def starting_run():
	parser = argparse.ArgumentParser(description='Pass in starting URL for wikipedia law scraping')
	parser.add_argument("--search_query", default="law/legal topics", type=str,
		help="Query to search in wikipedia")
	parser.add_argument("--num_results", default=100, type=int,
		help="Max number of results to return from the search query")
	parser.add_argument("--seen_urls", default=None, type=str,
		help="Text file with a list of seen urls")
	parser.add_argument("--seen_page_titles", default=None, type=str,
		help="Text file with a list of seen page titles")
	parser.add_argument("--path_to_existing_articles", default=None, type=str, nargs="*",
		help="Directory path to folder of already scraped articles")
	# parser.add_argument('--url', default=URL, type=str,
	#                     help='wikipedia URL to start scraping for law/legal content ')
	parser.add_argument('--data_path', default="./scraped_wiki_article_data", type=str,
		help="path to create an output directory to save the scraped files")
	# parser.add_argument('--sum', dest='accumulate', action='store_const',
	#                     const=sum, default=max,
	#                     help='sum the integers (default: find the max)')
	args = parser.parse_args()
	print(args)

	# Search for a topic in wikipedia (default limits to 10 results)
	search_result = wikipedia.search(args.search_query, results=args.num_results)
	# resp = fetch_html_from_url(args.url)
	# html = BeautifulSoup(resp.content, "html.parser")

	# Find all tag a for hrefs in the main content that will need to be crawled through
	# The pages might have citations, where the href is pointing to somewhere in the same page with
	# href="#cite note-1" for example which leads to non-wikipedia page.
	# Also they have "edit" links, ignore those
	# all_a = overall_div.find_all("a")

	# Keeps track of (text in <a> tag, href)
	# Keep track of the seen urls from each page visit
	if args.seen_urls is not None:
		with open(args.seen_urls, "r") as f:
			line = f.readline()
			# Identify the start and end square brackets
			start = line.find("[")+1 if line.find("[") != -1 else 0
			end = line.find("]") if line.find("]") != -1 else len(line)
			substr = line[start:end]
			tokens = substr.split(",")
			seen_urls = [x.replace("'", "").strip() for x in tokens]
		print(f"Have seen urls loaded. Total num: {len(seen_urls)}")
	else:
		seen_urls = []

	# write content into a textfile output
	data_path = args.data_path
	os.makedirs(data_path, exist_ok=True)

	# Keep track of seen article titles from wikipedia.page.links
	seen_page_titles = []
	if args.seen_page_titles is not None:
		with open(args.seen_page_titles, "r") as f:
			line = f.readline()
			# Identify the start and end square brackets
			start = line.find("[")+1 if line.find("[") != -1 else 0
			end = line.find("]") if line.find("]") != -1 else len(line)
			substr = line[start:end]
			tokens = substr.split(",")
			seen_page_titles = [x.replace("'", "").strip() for x in tokens]
	
	if args.path_to_existing_articles is not None:
		# Load the directory with files
		for path in args.path_to_existing_articles:
			files = os.listdir(path)
			for file_name in files:
				idx = file_name.find(".txt")
				# Saved output files have spaces in article with underscore, replace / with hyphen
				title = file_name[:idx].replace("_", " ")
				# title2 = title + "_SeenUrls" + str(len(seen_urls)) + ".txt"
				if title not in seen_page_titles:
					seen_page_titles.append(title)
	seen_page_titles = set(seen_page_titles) # prevent duplicates
	print(f"Total number of seen page titles: {len(seen_page_titles)}")
	
	# Logger
	# Split logger files by datetime so it doesn't all output to one gigantic log
	start_time = datetime.datetime.now()
	log_dir = os.path.join(data_path, "log")
	os.makedirs(log_dir, exist_ok=True)
	current_log_dir = create_log_dir(start_time, data_path)
	os.makedirs(current_log_dir, exist_ok=True)

	log_path = os.path.join(current_log_dir, f"start_{start_time.year}_{start_time.month}_{start_time.day}_{start_time.hour}_log.txt")
	logger = open(log_path, "w")
	logger.write("args: " + str(args))
	logger.write("start time: " + str(start_time) + "\n")

	# DFS
	# counter to keep track of how many pages had exceptions that were unable to be loaded
	failure_counter = 0
	# depth = 0

	print(search_result)
	logger.write("unseen links: " + str(search_result) + "\n")
	count = 0
	for page_title in search_result:
		# if (count == 1):
		# 	break
		# explore_page(url[0], url[1], seen_urls, data_path, logger)
		try:
			print("From starting page, exploring page: ", page_title)
			if logger.closed:
				# If logger is closed, open it again
				current_time = datetime.datetime.now()
				current_log_dir = create_log_dir(current_time, data_path)
				current_log_path = create_logger_name(current_time, current_log_dir)
				logger = open(current_log_path, "a")
			logger.write("From starting page, exploring page: " + str(page_title) + "\n")
			failure_counter, logger, msg = explore_page(page_title, seen_urls, seen_page_titles, data_path, logger, start_time, failure_counter)
		except ValueError as e:
			# ValueError: I/O operation on closed file.
			# open the current datetime as logger
			current_time = datetime.datetime.now()
			e_str = f"ValueError: {e} at {str(current_time)}. Open logger at current time\n"
			print(e_str)
			if logger.closed:
				current_log_dir = create_log_dir(current_time, data_path)
				current_log_path = create_logger_name(current_time, current_log_dir)
				logger = open(current_log_path, "a")
			logger.write(e_str)
		except Exception as err:
			err_str = f"An error occurred at top level: {err}\n"
			print(err_str)
			if logger.closed:
				# If logger is closed, open it again
				current_time = datetime.datetime.now()
				current_log_dir = create_log_dir(current_time, data_path)
				current_log_path = create_logger_name(current_time, current_log_dir)
				logger = open(current_log_path, "a")
			logger.write(err_str)
		count += 1
	
	if not logger.closed:
		# Close logger if it's open
		logger.close()
	# Final logger
	# TODO: split logger files by datetime so it doesn't all output to one gigantic log
	end_time = datetime.datetime.now()
	current_log_dir = os.path.join(log_dir, f"{end_time.year}-{end_time.month}-{end_time.day}")
	os.makedirs(current_log_dir, exist_ok=True)

	end_log_path = os.path.join(current_log_dir, f"end_{end_time.year}_{end_time.month}_{end_time.day}_{end_time.hour}_log.txt")
	end_logger = open(end_log_path, "w")
	end_logger.write("end time: " + str(end_time) + "\n")
	print(f"!!!!!!!!!!!!!Finished!!!!!!!!!! Number of main urls searched through: {count}")
	end_logger.write(f"Finished!!!!!!!!!! Number of main urls searched through: {count}")
	print(f"Number of failure cases: {failure_counter} / {count}")
	end_logger.write(f"Number of failure cases: {failure_counter} / {count}\n")
	end_logger.close()

	# Write seen_urls out to a text file
	with open(os.path.join(data_path, "seen_urls.txt"), "w") as file:
		file.write(str(seen_urls))
	
	# Write seen_page_titles out to a text file
	with open(os.path.join(data_path, "seen_page_titles.txt"), "w") as f:
		f.write(str(seen_page_titles))
	print("END")



def bfs():
	"""
	BFS to scrape the wikipedia articles
	"""
	parser = argparse.ArgumentParser(description='Pass in starting URL for wikipedia law scraping')
	parser.add_argument("--search_query", default="law/legal topics", type=str,
		help="Query to search in wikipedia")
	parser.add_argument("--num_results", default=100, type=int,
		help="Max number of results to return from the search query")
	parser.add_argument("--seen_urls", default=None, type=str,
		help="Text file with a list of seen urls")
	parser.add_argument("--seen_page_titles", default=None, type=str,
		help="Text file with a list of seen page titles")
	parser.add_argument("--path_to_existing_articles", default=None, type=str, nargs="*",
		help="Directory path to folder of already scraped articles")
	parser.add_argument('--start_page', default=None, type=str,
	                    help='wikipedia name page to start at')
	parser.add_argument('--data_path', default="./scraped_wiki_article_data", type=str,
		help="path to create an output directory to save the scraped files")
	parser.add_argument("--bfs_level", default=None, type=int,
		help="max level of bfs depth")
	args = parser.parse_args()
	print(args)

	# Keep track of the seen urls from each page visit
	if args.seen_urls is not None:
		with open(args.seen_urls, "r") as f:
			line = f.readline()
			# Identify the start and end square brackets
			start = line.find("[")+1 if line.find("[") != -1 else 0
			end = line.find("]") if line.find("]") != -1 else len(line)
			substr = line[start:end]
			tokens = substr.split(",")
			seen_urls = [x.replace("'", "").strip() for x in tokens]
		print(f"Have seen urls loaded. Total num: {len(seen_urls)}")
	else:
		seen_urls = []

	# write content into a textfile output
	data_path = args.data_path
	os.makedirs(data_path, exist_ok=True)

	# Keep track of seen article titles from wikipedia.page.links
	seen_page_titles = []
	if args.seen_page_titles is not None:
		with open(args.seen_page_titles, "r") as f:
			line = f.readline()
			# Identify the start and end square brackets
			start = line.find("[")+1 if line.find("[") != -1 else 0
			end = line.find("]") if line.find("]") != -1 else len(line)
			substr = line[start:end]
			tokens = substr.split(",")
			seen_page_titles = [x.replace("'", "").strip() for x in tokens]
	
	if args.path_to_existing_articles is not None:
		# Load the directory with files
		for path in args.path_to_existing_articles:
			files = os.listdir(path)
			for file_name in files:
				idx = file_name.find(".txt")
				# Saved output files have spaces in article with underscore, replace / with hyphen
				title = file_name[:idx].replace("_", " ")
				# title2 = title + "_SeenUrls" + str(len(seen_urls)) + ".txt"
				if title not in seen_page_titles:
					seen_page_titles.append(title)
	seen_page_titles = set(seen_page_titles) # remove duplicates
	print(f"Total number of seen page titles: {len(seen_page_titles)}")
	
	# Logger
	# Split logger files by datetime so it doesn't all output to one gigantic log
	start_time = datetime.datetime.now()
	log_dir = os.path.join(data_path, "log")
	os.makedirs(log_dir, exist_ok=True)
	current_log_dir = create_log_dir(start_time, data_path)
	os.makedirs(current_log_dir, exist_ok=True)

	log_path = os.path.join(current_log_dir, f"start_{start_time.year}_{start_time.month}_{start_time.day}_{start_time.hour}_log.txt")
	logger = open(log_path, "w")
	logger.write("args: " + str(args))
	logger.write("start time: " + str(start_time) + "\n")

	# Search for a query and get result
	if args.start_page is None:
		unseen_links = wikipedia.search(args.search_query, results=args.num_results)
	else:
		# Use the given article name as starting point
		unseen_links = [args.start_page]

	print(unseen_links)
	logger.write("unseen links: " + str(unseen_links) + "\n")

	# Cap the level of BFS
	bfs_level_cap = args.bfs_level
	if bfs_level_cap is not None:
		last_link_in_level = unseen_links[-1]
	else:
		last_link_in_level = None

	# Counters
	failure_counter = 0
	count = 0
	prev_datetime = datetime.datetime.now()

	# BFS
	while (unseen_links):
		# Check if logger is open
		if logger.closed:
			print("Logger is closed. Opening up logger again")
			current_time = datetime.datetime.now()
			current_log_dir = create_log_dir(current_time, data_path)
			logger = open(current_log_dir, "a")
		# Act as queue, pop off the oldest item first
		name = unseen_links.pop(0)
		print(f"Number of unseen_links left: {len(unseen_links)}")
		logger.write(f"Number of unseen_links left: {len(unseen_links)}\n")

		# Explore the page
		# Load the web page
		# Try loading page 3 times with 5 minute sleep. If not, then log as page that didn't get scraped
		page = None
		retry = 3
		try:
			while (page is None):
				if retry == 0:
					# Can't scrape this page, log it and return
					logger.write("$$$$$$$$$$$$$$ Retried 3 times, unable to scrape page: " + name + "\n")
					print(f"Retried 3 times, unable to scrape page {name}. Returning")
					failure_counter += 1 # TODO: since this is an int, this won't update in recursive calls...
					# Also maybe should keep track of the urls that have failed to load multiple times
					raise Exception("RetryError: retry 3 times failed")
				try:
					# response = fetch_html_from_url(full_url)
					# html = BeautifulSoup(response.content, "html.parser")
					page = wikipedia.page(name)
				except DisambiguationError as e:
					# Page is a disambiguation page
					e1 = f"DisambiguationError for {name}. Trying with auto_suggest set to false...\n"
					print(e1)
					logger.write(e1)
					try:
						page = wikipedia.page(name, auto_suggest=False)
					except Exception as f:
						error = f"Error: {f}. This page: {name}, is a disambiguation page. Returning...\n"
						logger.write(error)
						print(error)
						raise e
				except PageError as e:
					# Page doesn't exist, however sometimes this error is due to auto_suggest being true
					# Try calling again with auto_suggest set to false
					e1 = f"Page error for {name}. Trying with auto_suggest set to false...\n"
					print(e1)
					logger.write(e1)
					try:
						page = wikipedia.page(name, auto_suggest=False)
					except Exception as f:
						error = f"Error: {f}. This page: {name}, doesn't exist. Returning...\n"
						logger.write(error)
						print(error)
						raise e
				except ValueError as e:
					# ValueError: I/O operation on closed file.
					# open the current datetime as logger
					current_time = datetime.datetime.now()
					e_str = f"ValueError in recursive call: {e} at {str(current_time)}. Open logger at current time\n"
					if logger.closed:
						current_log_dir = create_log_dir(current_time, data_path)
						logger = open(current_log_dir, "a")
					print(e_str)
					logger.write(e_str)
					page = None
					retry -= 1
				except ConnectionError as e:
					# Check if it's "Connection reset by peer". If so, then break and stop the scraping
					if str(e).find("Connection reset by peer") != -1:
						raise e
					else:
						print(f"ConnectionError: {e}. Sleep for 300 seconds (5 minutes)...")
						page = None
						time.sleep(300)
						retry -= 1
				except Exception as e:
					print(f"Exception: {e}. Sleep for 300 seconds (5 minutes)...")
					page = None
					time.sleep(300)
					retry -= 1
		except ConnectionError as e:
			# This must be a "Connection reset by peer" error. Break the loop
			print(f"ConnectionError: {str(e)}. Breaking outer while search loop...")
			logger.write(f"ConnectionError: {str(e)}. Breaking outer while search loop...")
			break
		except Exception as e:
			# There was some error when trying to open the page. continue to next page
			continue

		# Set up logger in hourly increments. Save each day's logs in its own subdirectory
		current_time = datetime.datetime.now()
		current_log_dir = create_log_dir(current_time, data_path)
		if prev_datetime.day != current_time.day or prev_datetime.month != current_time.month or prev_datetime.year != current_time.year:
			# Create new directory for log of new day/month/year
			print("Creating new logger subdirectory")
			os.makedirs(current_log_dir, exist_ok=True)
		
		if prev_datetime.hour != current_time.hour:
			# Only write out seen urls and seen page titles at the end of the current hour's log once
			logger.write("seen urls list: " + str(seen_urls) + "\n")
			logger.write("seen page titles set: " + str(seen_page_titles) + "\n")
			# Close the logger and create a new one
			logger.close()
			log_path = create_logger_name(current_time, current_log_dir)
			print(f"New hour reached. Closing previous logger and creating new logger: {log_path}")
			logger = open(log_path, "a")
		
		# If url redirected to a previously seen url, then return. No need to explore this page
		# redirect check identify_redirecting_urls(seen_urls, response)
		if page.url in seen_urls or not accepted_url(page.url):
			print(f"*********Redirected or already seen url {page.url} or should be filtered out. Returning***************")
			logger.write(f"*********Redirected or already seen url {page.url} or should be filtered out. Returning***************\n")
			continue

		# Mark this url as seen
		try:
			if page.url not in seen_urls:
				seen_urls.append(page.url)
		except Exception as err:
			print(f"Can't add anymore urls to seen_urls: {page.url}")
		
		try:
			# If unable to add anymore items into set
			seen_page_titles.add(name)
		except Exception as error:
			print(f"Unable to add anymore names to seen_page_titles set: {name}")
		print(f"Exploring url: {page.url} at {str(current_time)}")
		print("Failure counter so far: " + str(failure_counter))
		logger.write("Exploring url: " + page.url + " at " + str(current_time) +"\n")
		logger.write(f"Failure counter so far: {failure_counter}\n")

		# Get the wikipedia page visible title
		title = page.title

		# Create new text file for this article
		if title is None or title == "":
			# Can't find title
			logger.write("Title couldn't be found for article! Returning\n")
			print("Title couldn't be found for article!")
			continue

		# Extract all the content on the page
		# Set any header type tags to be the "topic" and the text within to be the description
		# Separate topic and description with a tab "\t"
		overall_visible_str_cat = page.content
		containsLaw = False
		# If the page doesn't ever mention "law" or "legal", then treat as unrelated content and skip the page
		# This won't work since the term "notes" can show up earlier, not just at the header
		# Should have at least 2 of these terms to pass
		law_check = overall_visible_str_cat.lower().find("law") != -1
		legal_check = overall_visible_str_cat.lower().find("legal") != -1
		statute_check = overall_visible_str_cat.lower().find("statute") != -1
		legislative_check = overall_visible_str_cat.lower().find("legislative") != -1
		judicial_check = overall_visible_str_cat.lower().find("judicial") != -1
		legislation_check = overall_visible_str_cat.lower().find("legislation") != -1
		legislature_check = overall_visible_str_cat.lower().find("legislature") != -1
		gov_check = overall_visible_str_cat.lower().find("government") != -1
		court_check = overall_visible_str_cat.lower().find("court") != -1
		due_process = overall_visible_str_cat.lower().find("due process") != -1
		jurisprudence = overall_visible_str_cat.lower().find("jurisprudence") != -1
		jury = overall_visible_str_cat.lower().find("jury") != -1
		tribunal_check = overall_visible_str_cat.lower().find("tribunal") != -1
		checks = [law_check, legal_check, statute_check, legislative_check, judicial_check, legislation_check, gov_check, \
		court_check, due_process, jurisprudence, legislature_check, jury, tribunal_check]

		num_pass = sum(checks)
		print(f"number of law checks that pass: {num_pass} / {len(checks)}")
		if num_pass >= 2:
			print(f"Contains law: {law_check}")
			print(f"Contains legal: {legal_check}")
			print(f"Contains statute: {statute_check}")
			print(f"Contains legislative: {legislative_check}")
			print(f"Contains judicial: {judicial_check}")
			print(f"Contains legislation: {legislation_check}")
			print(f"Contains legislature: {legislature_check}")
			print(f"Contains government: {gov_check}")
			print(f"Contains court: {court_check}")
			print(f"Contains due process: {due_process}")
			print(f"Contains jurisprudence: {jurisprudence}")
			print(f"Contains jury: {jury}")
			print(f"Contains tribunal: {tribunal_check}")
			logger.write(f"Contains law: {law_check}\n")
			logger.write(f"Contains legal: {legal_check}\n")
			logger.write(f"Contains statute: {statute_check}\n")
			logger.write(f"Contains legislative: {legislative_check}\n")
			logger.write(f"Contains judicial: {judicial_check}\n")
			logger.write(f"Contains legislation: {legislation_check}\n")
			logger.write(f"Contains legislature: {legislature_check}\n")
			logger.write(f"Contains government: {gov_check}\n")
			logger.write(f"Contains court: {court_check}\n")
			logger.write(f"Contains due process: {due_process}\n")
			logger.write(f"Contains jurisprudence: {jurisprudence}\n")
			logger.write(f"Contains jury: {jury}\n")
			logger.write(f"Contains tribunal: {tribunal_check}")
			containsLaw = True

		if not containsLaw:
			print(f"Does not contain law or legal content: {page.url} \n")
			logger.write(f"Does not contain law or legal content: {page.url} \n")
			continue

		# Replace spaces in article with underscore, replace / with hyphen
		article_path = os.path.join(data_path, title.replace(" ", "_").replace("/", "-"))
		if os.path.exists(article_path + ".txt"):
			writer = open(article_path + "_SeenUrls" + str(len(seen_urls)) + ".txt", "w")
		else:
			writer = open(article_path + ".txt", "w")
		print("\n")
		print("From wikipediaPage sections for headers: " + str(page.sections))
		logger.write("From wikipediaPage sections for headers: " + str(page.sections) + "\n")

		# Ignore info in figures
		header = title
		description = ""
		prev_h2 = ""
		prev_h3 = ""
		prev_h4 = ""
		prev_h5 = ""
		prev_h6 = ""

		num = len(overall_visible_str_cat.split("\n"))
		print(f"Number of tokens split by newline: {num}")
		logger.write(f"Number of tokens split by newline: {num}\n")
		# Iterate through the tokens in the concatenated string of all visible text in overal_div (main body content)
		# split by newline
		# Remove anything in brackets like "[<stuff>]", can be reference or something else for Wikipedia article
		# https://stackoverflow.com/questions/22225006/how-to-replace-only-the-contents-within-brackets-using-regular-expressions
		for text in overall_visible_str_cat.split("\n"):
			# print("line: " + text)
			logger.write("line: " + text + "\n")
			if text.find("====== ") != -1:
				# found h6 header
				print(f"found h6 header {text}")
				logger.write(f"found h6 header {text}\n")

				total_header = ""
				if prev_h2 != "":
					total_header += prev_h2
				if prev_h3 != "":
					total_header += " - " + prev_h3
				if prev_h4 != "":
					total_header += " - " + prev_h4
				if prev_h5 != "":
					total_header += " - " + prev_h5
				if prev_h6 != "":
					total_header += " - " + prev_h6
				if total_header == "":
					total_header += header
				writer.write(total_header + "\t" + description.strip() + "\n")
				# Reset
				header = text.replace("===", "").strip()
				prev_h6 = header
				description = ""
			elif text.find("===== ") != -1:
				# found h5 header
				print(f"found h5 header {text}")
				logger.write(f"found h5 header {text}\n")

				total_header = ""
				if prev_h2 != "":
					total_header += prev_h2
				if prev_h3 != "":
					total_header += " - " + prev_h3
				if prev_h4 != "":
					total_header += " - " + prev_h4
				if prev_h5 != "":
					total_header += " - " + prev_h5
				if prev_h6 != "":
					total_header += " - " + prev_h6
				if total_header == "":
					total_header += header
				writer.write(total_header + "\t" + description.strip() + "\n")
				# Reset
				header = text.replace("===", "").strip()
				prev_h5 = header
				prev_h6 = ""
				description = ""
			elif text.find("==== ") != -1:
				# found h4 header
				print(f"found h4 header {text}")
				logger.write(f"found h4 header {text}\n")

				total_header = ""
				if prev_h2 != "":
					total_header += prev_h2
				if prev_h3 != "":
					total_header += " - " + prev_h3
				if prev_h4 != "":
					total_header += " - " + prev_h4
				if prev_h5 != "":
					total_header += " - " + prev_h5
				if prev_h6 != "":
					total_header += " - " + prev_h6
				if total_header == "":
					total_header += header
				writer.write(total_header + "\t" + description.strip() + "\n")
				# Reset
				header = text.replace("====", "").strip()
				prev_h4 = header
				prev_h5 = ""
				prev_h6 = ""
				description = ""
			elif text.find("=== ") != -1:
				# found h3 header
				print(f"found h3 header {text}")
				logger.write(f"found h3 header {text}\n")

				total_header = ""
				if prev_h2 != "":
					total_header += prev_h2
				if prev_h3 != "":
					total_header += " - " + prev_h3
				if prev_h4 != "":
					total_header += " - " + prev_h4
				if prev_h5 != "":
					total_header += " - " + prev_h5
				if prev_h6 != "":
					total_header += " - " + prev_h6
				if total_header == "":
					total_header += header
				writer.write(total_header + "\t" + description.strip() + "\n")
				# Reset
				header = text.replace("===", "").strip()
				prev_h3 = header
				prev_h4 = ""
				prev_h5 = ""
				prev_h6 = ""
				description = ""
			# if text.find("[ edit ]") != -1 or text.strip() in header_strs_only:
			elif text.find("== ") != -1:
				# h2 header
				print(f"found h2 header {text}")
				logger.write(f"found h2 header {text}\n")

				# This is a h2 header
				# Find all parents if it is a subheader
				# assert(header_map_list[hdr_index][0] == header)
				total_header = ""
				if prev_h2 != "":
					total_header += prev_h2
				if prev_h3 != "":
					total_header += " - " + prev_h3
				if prev_h4 != "":
					total_header += " - " + prev_h4
				if prev_h5 != "":
					total_header += " - " + prev_h5
				if prev_h6 != "":
					total_header += " - " + prev_h6
				if total_header == "":
					total_header += header

				# Remove references in "[]"
				# description = re.sub(r"\[.*?\]", "", description)
				writer.write(total_header + "\t" + description.strip() + "\n")
				# if text.find("[ edit ]") != -1:
				# 	header = text[:text.find("[ edit ]")].strip() # substring up to [edit]
				# else:
				# 	header = text.strip()
				header = text.replace("==", "").strip()
				prev_h2 = header
				prev_h3 = ""
				prev_h4 = ""
				prev_h5 = ""
				prev_h6 = ""
				description = ""
				# hdr_index += 1 # increment to next expected header

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
			# for h in header_map_list[-1][1]:
			# 	total_header += h + " - "
			# total_header += header
			total_header = ""
			if prev_h2 != "":
				total_header += prev_h2
			if prev_h3 != "":
				total_header += " - " + prev_h3
			if prev_h4 != "":
				total_header += " - " + prev_h4
			if prev_h5 != "":
				total_header += " - " + prev_h5
			if prev_h6 != "":
				total_header += " - " + prev_h6
			if total_header == "":
				total_header += header

			# description = re.sub(r"\[.*?\]", "", description)
			writer.write(total_header + "\t" + description.strip() + "\n")

		# Close the writer
		writer.close()
		count += 1
		# return

		# Find neighbors from list of wikipedia page links on the current page, excluding metadata pages
		logger.write(f"Upcoming neighbors: {str(page.links)}\n")

		# Add unseen neighbors to queue
		if bfs_level_cap is None or bfs_level_cap > 0:
			for n in page.links:
				if n not in seen_page_titles:
					unseen_links.append(n)
		else:
			print("Hit BFS level cap, not adding additional neighbors")
			logger.write("Hit BFS level cap, not adding additional neighbors")
		# If max BFS depth is set, decrement whenever a level of search is done
		if last_link_in_level is not None and name == last_link_in_level:
			bfs_level_cap -= 1
			last_link_in_level = unseen_links[-1]
			print(f"Hit the last link in the current level. Decrementing bfs_level_cap: {bfs_level_cap}")
			logger.write(f"Hit the last link in the current level. Decrementing bfs_level_cap: {bfs_level_cap}\n")
		# update datetime
		prev_datetime = current_time

	# main while loop ended
	if not logger.closed:
		# Close logger if it's open
		logger.close()
	# Final logger
	end_time = datetime.datetime.now()
	current_log_dir = os.path.join(log_dir, f"{end_time.year}-{end_time.month}-{end_time.day}")
	os.makedirs(current_log_dir, exist_ok=True)

	end_log_path = os.path.join(current_log_dir, f"end_{end_time.year}_{end_time.month}_{end_time.day}_{end_time.hour}_log.txt")
	end_logger = open(end_log_path, "w")
	end_logger.write("end time: " + str(end_time) + "\n")
	print(f"!!!!!!!!!!!!!Finished!!!!!!!!!! Number of main urls searched through: {count}")
	end_logger.write(f"Finished!!!!!!!!!! Number of main urls searched through: {count}")
	print(f"Number of failure cases: {failure_counter} / {count}")
	end_logger.write(f"Number of failure cases: {failure_counter} / {count}\n")
	end_logger.close()

	# Write seen_urls out to a text file
	with open(os.path.join(data_path, "seen_urls.txt"), "w") as file:
		file.write(str(seen_urls))
	
	# Write seen_page_titles out to a text file
	with open(os.path.join(data_path, "seen_page_titles.txt"), "w") as f:
		f.write(str(seen_page_titles))
	print("BFS END")

bfs()

#starting_run()

# Logger
# log_path = os.path.join("./scraped_wiki_article_data", "log.txt")
# logger = open(log_path, "w")
# counter = 0
# explore_page("Hong Kong", [], [], "./scraped_wiki_article_data", logger, datetime.datetime.now(), counter)
