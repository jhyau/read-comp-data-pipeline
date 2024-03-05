"""Fetch raw HTML from a URL."""
from typing import Optional

import requests
from requests.exceptions import HTTPError


def fetch_html_from_url(url: str) -> Optional[str]:
    """
    Fetch raw HTML from a URL.

    :param str url: URL to `GET` contents from.

    :return: Optional[str]
    Original User-Agent: "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0"
    """
    try:
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
            "User-Agent": "CoolBot/0.0 (https://example.org/coolbot/; coolbot@example.org)",
        }
        return requests.get(url, headers=headers, timeout=7)
    except HTTPError as e:
        print(f"HTTP error occurred: {e}")
    except Exception as e:
        print(f"Unexpected error occurred: {e}")

        # Try again with slightly different header? --> Didn't work
        # print("****Trying again with different header****")
        # headers2 = {
        #     "Access-Control-Allow-Origin": "*",
        #     "Access-Control-Allow-Methods": "GET",
        #     "Access-Control-Allow-Headers": "Content-Type",
        #     "Access-Control-Max-Age": "3600",
        #     "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0",
        # }
        # return requests.get(url, headers=headers2, timeout=7)
