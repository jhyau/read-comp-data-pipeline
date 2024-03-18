import os,sys
import argparse

# import the OpenAI Python library for calling the OpenAI API
from openai import OpenAI
import os

def has_keyword(check: str, keywords: list):
	for key in keywords:
		if check.find(key) != -1:
			return True
	return False

KEYWORDS = ["law", "legal", "statute", "legislative", "judicial", "legislation", "legislature", "government", "court", "due process", "jurisprudence", "jury", "tribunal"]

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "<OpenAI API key>"))

parser = argparse.ArgumentParser(description='Pass args for querying GPT')
parser.add_argument("--model", default="gpt-3.5-turbo", type=str,
	help="Model to query")
parser.add_argument('--data_path', default="./scraped_wiki_article_data", type=str,
	help="path to directory of scraped files")
args = parser.parse_args()
print(args)

all_files = os.listdir(args.data_path)
for file in all_files:
	line_num = 0
	index = file.find(".txt")
	title = file[:index].replace("_", " ")

	print(f"Going through file: {file}")
	# Read in the textfile
	title_is_law = has_keyword(file, KEYWORDS)
	with open(os.path.join(args.data_path, file), "r") as f:
		# Go through each line
		for line in f:
			if line_num == 0:
				# Get the proper title
				title = line.split("\t")[0]
			# Query
			if title_is_law or has_keyword(line, KEYWORDS):
				header, description = line.split("\t")
				print(f"Querying {args.model} with line: {line}")
				prompt = f"Generate law topics under {title}"

				if line_num > 0:
					# Not the first line
					headers = header.split(" - ")
					for i in range(len(headers)):
						if i == len(headers) - 1:
							# The most specfic subheader
							prompt += f", specifically related to {headers[i]}"
						else:
							prompt += f" under {headers[i]}"
				if description != "":
					# Make sure description is not empty
					prompt += f" given this short description: {description}"
				
				# Query the model
				print(f"Prompt: {prompt}")
				response = client.chat.completions.create(
				    model=args.model,
				    messages=[
				        {"role": "system", "content": "You are a law topic generator"},
				        {"role": "user", "content": f"{prompt}"},
				    ],
				    temperature=0,
				)
				# Get the response
				print("Response:")
				print(response.choices[0].message.content)
				# break
			line_num += 1
	break

print(f"FINISHED QUERYING MODEL {args.model}")