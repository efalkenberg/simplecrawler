"""
A basic crawler that takes a URL and crawls all
URLs visible from the entry point.

Does not:
- have a nice code layout, this is just one file
- Respect robots.txt
- Follow redirects
- Handle hosts different than `www`
- Be a good citizen
- Distribute crawling in any way
"""

import argparse
import os
import re
import requests
import unittest
from collections import deque
from datetime import datetime
from urllib.parse import urlparse

USER_AGENTS = dict(DEFAULT="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/129.0.0.0 Safari/537.36",
                   IOS="Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) "
                       "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                       "Version/18.1 Mobile/15E148 Safari/604.1",
                   ANDROID="Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/117.0.0.0 Mobile Safari/537.36")


class Crawler:
    """
    Your super duper crawler from space
    """
    __seen = []
    __ignore = []
    __queue = deque()
    __filename = ""
    __root = ""
    __root_folder = ""
    __regex = ""
    __crawl_desktop_macos_chrome = True
    __crawl_mobile_ios = False
    __crawl_mobile_android = False

    preferred_host = "www"
    preferred_protocol = "https"

    def __init__(self, domain: str, output_directory: str, **kwargs) -> None:
        self.__set_root(domain)
        now = datetime.now()

        self.__root_folder = f"{output_directory}/{now.year}-{now.month}-{now.day}_{now.hour}-{now.minute}-{now.second}"
        if not os.path.exists(self.__root_folder):
            os.makedirs(self.__root_folder)

        if "crawl_desktop_macos_chrome" in kwargs:
            self.__crawl_desktop_macos_chrome = kwargs["crawl_desktop_macos_chrome"]
        if "crawl_mobile_ios" in kwargs:
            self.__crawl_mobile_ios = kwargs["crawl_mobile_ios"]
        if "crawl_mobile_android" in kwargs:
            self.__crawl_mobile_android = kwargs["crawl_mobile_android"]

    def __set_root(self, domain):
        self.__root = f"{self.preferred_protocol}://{self.preferred_host}.{domain}/"
        print_debug(f"__root set to `{self.__root}`")
        self.__regex = f"href=['\"](/|{self.__root})(.*?)['\"]"

    def crawl(self):
        self.__queue.append(self.__root)
        i = 0
        while len(self.__queue) > 0:
            url = self.__queue.popleft()
            if self.__crawl_desktop_macos_chrome:
                self.__crawl(url)
            if self.__crawl_mobile_ios:
                self.__crawl(url, "IOS")
            if self.__crawl_mobile_android:
                self.__crawl(url, "ANDROID")
            # print_debug(f"seen:{len(self.__seen)} in queue:{len(self.__queue)}")

    def __crawl(self, url: str, user_agent="DEFAULT"):
        headers = {
            "User-Agent": USER_AGENTS[user_agent]
        }
        r = requests.get(url, headers=headers)
        if r.status_code is None or r.status_code != 200:
            if r.status_code == 403 and "/cdn-cgi/" in r.text:
                # Cloudflare's bot detection and blockage
                # Note: there are some know hacks, but we'll be good
                # citizen here
                # https://www.zenrows.com/blog/bypass-cloudflare
                print_error(f"Oh noes, Cloudflare blocked us from crawling {url}")
            else:
                print_error(f"Invalid status code ({r.status_code}) for {url}")
                print_error(f"Text ({r.text})")
                return
        else:
            if "Content-Type" not in r.headers:
                # print_error(f"No content type for {url}")
                return
            if "text/html" not in r.headers["Content-Type"]:
                # print_error(f"Invalid content type ({r.headers['Content-Type']}) for {url}")
                return
            print_debug(f"Downloaded {url} ({user_agent})")
            self.persist(url, r.text, user_agent)

            # parse the content for additional urls:
            matches = re.findall(self.__regex, r.text)
            for match in matches:
                if len(match) == 2:
                    # prefix the root for relative urls
                    if match[0] == "/":
                        link = self.__root + match[1]
                    else:
                        link = match[0] + match[1]

                    # append to the seen list and the worker queue,
                    # so that it will be picked up by `crawl` in
                    # its worker loop
                    if link not in self.__seen and link not in self.__ignore:
                        self.__seen.append(link)
                        self.__queue.append(link)

    def persist(self, url: str, content: str, user_agent: str):
        file_path = persistable_path_from_url(self.__root_folder, url, user_agent)
        path, _ = os.path.split(file_path)
        # create the folder structure and put (for now)
        # an empty file at the given path
        if not os.path.exists(path):
            os.makedirs(path)

        with open(file_path, 'w') as file:
            file.write(content)


def persistable_path_from_url(local_root: str, url: str, user_agent: str) -> str:
    """
    Converts the given url to a local path that can be used to
    store crawled data.
    """
    parsed_url = urlparse(url)

    # Replace dots in the host and domain part with underscores
    modified_netloc = re.sub(r'\.', '_', parsed_url.netloc)

    # Reconstruct the URL with the modified netloc
    modified_url = parsed_url._replace(netloc=modified_netloc).geturl()

    # strip the protocol part
    filepath = re.sub(r"https?:\/\/", "", modified_url)

    # prefix with the local root folder
    filepath = f"{local_root}/{user_agent}/{filepath}"

    # consider `#` as not relevant, they are mainly anchors
    # to deep link into sections of a page
    # example: index.html#news
    filepath = filepath.split("#")[0]

    # clean up trailing slashes, folders will be
    # handled separately. This URL returned `200`
    # before so we treat it as a file
    # example: https://www.example.org/docs/
    if filepath.endswith("/"):
        filepath = filepath[:-1]

    # make urls with get parameters filesystem safe
    # note: there is no stable sorting for the
    # get parameters so there might be duplicates
    # e.g.
    #   convert     `page?id=5&lang=en`
    #   to          `page-id_5-lang_en.html`
    if "?" in filepath:
        filepath = re.sub(r"(\?|&)", "-", filepath)
        filepath = re.sub(r"(=)", "_", filepath)
        filepath += ".html"

    # for filepaths without an extension,
    # add `.html` to make it easier to inspect
    if "." not in filepath.split("/")[-1]:
        filepath += ".html"

    return filepath


def print_debug(msg):
    print(f"🍺 [{datetime.now()}] {msg}")


def print_error(msg):
    print(f"🚨 [{datetime.now()}] {msg}")


def main():
    parser = argparse.ArgumentParser(description="A simple web crawler")
    parser.add_argument("domain", type=str, help="The domain to crawl")
    parser.add_argument("--output_dir", type=str, default="data",
                        help="The directory to store the crawled data")
    parser.add_argument("--disable_chrome_macos",
                        action="store_true",
                        help="If set, will not crawl with Chrome macOS useragent")
    parser.add_argument("--enable_ios",
                        action="store_true",
                        help="If set, will (also) crawl with iOS useragent")
    parser.add_argument("--enable_android",
                        action="store_true",
                        help="If set, will (also) crawl with Android useragent")
    args = parser.parse_args()

    print_debug(f"Domain: {args.domain}")
    print_debug(f"Output directory {args.output_dir}")
    crawler = Crawler(args.domain, args.output_dir,
                      crawl_desktop_macos_chrome=not args.disable_chrome_macos,
                      crawl_mobile_ios=args.enable_ios,
                      crawl_mobile_android=args.enable_android)
    crawler.crawl()


if __name__ == "__main__":
    main()

#
# class TestCrawler(unittest.TestCase):
#     def test_persistable_path_from_url(self):
#         test_local_root = "data/2024-11-6_14-53-4"
#         input1 = "http://www.example.com/a/b/c.html"
#         output1 = "data/2024-11-6_14-53-4/www_example_com/a/b/c.html"
#         self.assertEqual(output1, persistable_path_from_url(test_local_root, input1))
#
#         input2 = "http://www.example.com/a/b/c"
#         output2 = "data/2024-11-6_14-53-4/www_example_com/a/b/c.html"
#         self.assertEqual(output2, persistable_path_from_url(test_local_root, input2))
#
#         input3 = "http://www.example.com/a/b/index.php?id=1000&lang=en"
#         output3 = "data/2024-11-6_14-53-4/www_example_com/a/b/index.php-id_1000-lang_en.html"
#         self.assertEqual(output3, persistable_path_from_url(test_local_root, input3))
#
#         input4 = "http://www.test.example.com/a/b/index.php?id=1000&lang=en"
#         output4 = "data/2024-11-6_14-53-4/www_test_example_com/a/b/index.php-id_1000-lang_en.html"
#         self.assertEqual(output4, persistable_path_from_url(test_local_root, input4))
