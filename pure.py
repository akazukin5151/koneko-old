"""
Collection of functions that are pure and side effect free
    (Excluding print)
"""

import re
import os
import time
import functools
import itertools
import threading
from contextlib import contextmanager

import funcy
import cytoolz


@contextmanager
def cd(newdir):
    """
    Change current script directory, do something, change back to old directory
    See https://stackoverflow.com/questions/431684/how-do-i-change-the-working-directory-in-python/24176022#24176022

    Parameters
    ----------
    newdir : str
        New directory to cd into inside 'with'
    """
    prevdir = os.getcwd()
    os.chdir(os.path.expanduser(newdir))
    try:
        yield
    finally:
        os.chdir(prevdir)


def spin(done, message):
    for char in itertools.cycle("|/-\\"):  # Infinite loop
        print(message, char, flush=True, end="\r")
        if done.wait(0.1):
            break
    print(" " * len(char), end="\r")  # clears the spinner


@funcy.decorator
def spinner(call, message=""):
    """
    See http://hackflow.com/blog/2013/11/03/painless-decorators/
    """
    done = threading.Event()
    spinner = threading.Thread(target=spin, args=(done, message))
    spinner.start()
    result = call()
    done.set()
    spinner.join()
    return result


def split_backslash_last(string):
    """
    Intended for splitting url to get filename, but it has lots of applications...
    """
    return string.split("/")[-1]


def generate_filepath(filename):
    filepath = f"{os.path.expanduser('~')}/Downloads/{filename}"
    return filepath


def prefix_filename(old_name, new_name, number):
    img_ext = old_name.split(".")[-1]
    number_prefix = str(number).rjust(2, "0")
    new_file_name = f"{number_prefix}_{new_name}.{img_ext}"
    return new_file_name


def find_number_map(x, y):
    if not (x >= 1 and y >= 1):
        return False
    # 5 = number of cols; 6 = number of rows, 30 images
    number_map = list(cytoolz.partition_all(5, range(30)))

    try:
        # coordinates are 1-based index
        number = number_map[y - 1][x - 1]
    except IndexError:
        print("Invalid number!\n")
        return False
    return number


def print_multiple_imgs(illusts_json):
    for (index, json) in enumerate(illusts_json):
        pages = json["page_count"]
        if pages > 1:
            print(f"#{index} has {pages} pages", end=", ")
    print("")


@cytoolz.curry
def url_given_size(post_json, size):
    """
    size : str
        One of: ("square-medium", "medium", "large")
    """
    return post_json["image_urls"][size]


@cytoolz.curry
def post_title(current_page_illusts, post_number):
    return current_page_illusts[post_number]["title"]


def medium_urls(current_page_illusts):
    get_medium_url = url_given_size(size="square_medium")
    urls = list(map(get_medium_url, current_page_illusts))
    return urls


def post_titles_in_page(current_page_illusts):
    post_titles = post_title(current_page_illusts)
    titles = list(map(post_titles, range(len(current_page_illusts))))
    return titles


@spinner("")
def page_urls_in_post(post_json, size="medium"):
    """Get the number of pages and each of their urls in a multi-image post."""
    number_of_pages = post_json["page_count"]
    if number_of_pages > 1:
        print(f"Page 1/{number_of_pages}")
        list_of_pages = post_json["meta_pages"]
        page_urls = []
        for i in range(number_of_pages):
            page_urls.append(url_given_size(list_of_pages[i], size))
    else:
        page_urls = None

    return number_of_pages, page_urls


def change_url_to_full(post_json, png=False):
    """
    The 'large' resolution url isn't the largest. This uses changes the url to
    the highest resolution available
    """
    url = url_given_size(post_json, "large")
    url = re.sub(r"_p0_master\d+", "_p0", url)
    url = re.sub(r"c\/\d+x\d+_\d+_\w+\/img-master", "img-original", url)

    # If it doesn't work, try changing to png
    if png:
        url = url.replace("jpg", "png")
    return url

# No longer used
@funcy.decorator
def catch_ctrl_c(call):
    """
    See http://hackflow.com/blog/2013/11/03/painless-decorators/
    """
    try:
        result = call()
    except KeyboardInterrupt:
        os.system("clear")
    else:
        return result
