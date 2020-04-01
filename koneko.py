"""
TODO: handle posts with multiple images:
    Need an indicator in gallery view (need to rewrite lscat first)
TODO: if post has multiple images, there should be a preview in image view
TODO: unit tests

Browse pixiv in the terminal using kitty's icat to display images (in the
terminal!)

Requires [kitty](https://github.com/kovidgoyal/kitty) on Linux. It uses the
magical `kitty +kitten icat` 'kitten' to display images.

Uses [pixivpy](https://github.com/upbit/pixivpy/), install with
`pip install pixivpy`
"""

import os
import sys
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
import re
import itertools
import imghdr
from configparser import ConfigParser
from contextlib import contextmanager
from pixivpy3 import *

# - Non interactive, invisible to user (backend) functions
# - General functions (can be applied anywhere)
import time
import functools


def timer(func):
    @functools.wraps(func)  # Preserve original func.__name__
    def wrapper(*args, **kwargs):
        t0 = time.time()
        value = func(*args, **kwargs)
        t1 = time.time()
        total = t1 - t0
        with open("/home/twenty/Workspace/pixiv/time.txt", "a") as the_file:
            the_file.write(f"{func.__name__!r}() time: {total}\n")
        return value

    return wrapper


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


def spin(done):
    for char in itertools.cycle("|/-\\"):  # Infinite loop
        print(char, flush=True, end="\r")
        if done.wait(0.1):
            break
    print(" " * len(char), end="\r")  # clears the spinner


def spinner(func):
    """
    https://github.com/fluentpython/example-code/blob/master/18-asyncio-py3.7/spinner_asyncio.py
    """

    def wrapper(*args, **kwargs):
        done = threading.Event()
        spinner = threading.Thread(target=spin, args=(done,))
        spinner.start()
        result = func(*args, **kwargs)  # run slow function, blocking
        done.set()
        spinner.join()
        return result

    return wrapper


# - Logging in functions
# @timer
def setup(out_queue):
    """
    Logins to pixiv in the background, using credentials from config file

    Parameters
    ----------
    out_queue : queue.Queue()
        queue for storing logged-in api object
    """
    api = AppPixivAPI()
    # Read config.ini file
    config_object = ConfigParser()
    config_object.read(f"{os.path.expanduser('~/.config/koneko/')}config.ini")
    config = config_object["Credentials"]

    # print("Logging in...")
    api.login(config["Username"], config["Password"])
    out_queue.put(api)
    # return api


# - Other backend functions, not general
def get_url_and_filename(post_json, size, get_filename=False):
    """
    size : str
        One of: ("square-medium", "medium", "large")
    """
    url = post_json["image_urls"][size]
    if not get_filename:
        return url
    filename = url.split("/")[-1]
    return url, filename


class LastPageException(Exception):
    pass


@spinner
def prefetch_next_page(current_page_num, artist_user_id):
    """
    current_page_num : int
        It is the CURRENT page number, before incrementing
    """
    print("   Prefetching next page...", flush=True, end="\r")
    next_url = all_pages_cache[str(current_page_num)]["next_url"]
    if not next_url:  # this is the last page
        raise LastPageException

    parse_page = api.user_illusts(**api.parse_qs(next_url))
    all_pages_cache[str(current_page_num + 1)] = parse_page
    current_page_illusts = parse_page["illusts"]
    download_illusts(current_page_illusts, current_page_num + 1, artist_user_id)

    print("  " * 26)
    return current_page_illusts


@spinner
def get_pages_url_in_post(post_json, size="medium"):
    """
    Formerly check_multiple_images_in_post(); for when posts have multiple images
    """
    number_of_pages = post_json.page_count
    if number_of_pages > 1:
        print(f"Page 1/{number_of_pages}")
        list_of_pages = post_json.meta_pages
        page_urls = []
        for i in range(number_of_pages):
            page_urls.append(get_url_and_filename(list_of_pages[i], size))
    else:
        page_urls = None

    return number_of_pages, page_urls


@spinner
def user_illusts_spinner(artist_user_id):
    # There's a delay here
    # Threading won't do anything meaningful here...
    print("   Fetching user illustrations...", flush=True, end="\r")
    return api.user_illusts(artist_user_id)


# - Download functions
def async_download(url, img_name, new_file_name=None):
    """
    Downloads given url, rename if needed

    Parameters
    ----------
    url : str
        Url to download
    img_name : str
        Name of downloaded image without renaming (yet)
    new_file_name : str or None
        Desired new name of the image, if you want to rename it
    """
    api.download(url)
    if new_file_name:
        os.rename(f"{img_name}", f"{new_file_name}")


# @timer
@spinner
def download_illusts(current_page_illusts, current_page_num, artist_user_id):
    """
    Download the illustrations on one page of given artist id

    Parameters
    ----------
    current_page_illusts : JsonDict
        JsonDict holding lots of info on all the images in the current page
    current_page_num : int
        Page as in artist illustration profile pages. Starts from 1
    artist_user_id : int

    Returns
    -------
    urls : List of str
        List of urls in current page
    download_path : str
    """
    urls = []
    file_names = []
    for i in range(len(current_page_illusts)):
        # Or square medium
        urls.append(get_url_and_filename(current_page_illusts[i], "medium"))
        file_names.append(current_page_illusts[i]["title"])

    download_path = f"/tmp/koneko/{artist_user_id}/{current_page_num}/"
    download_core(download_path, urls, rename_images=True, file_names=file_names)

    return urls, download_path


# @timer
@spinner
def download_large(artist_user_id, current_page_num, url, filename):
    large_dir = f"/tmp/koneko/{artist_user_id}/{current_page_num}/large/"
    filepath = f"{large_dir}{filename}"
    make_path_and_download(large_dir, url, filename)


def make_path_and_download(large_dir, url, filename, try_make_dir=True):
    # TODO: duplicated with async_download()?
    # Ans: this is for downloading one image. Using threads will slow it down
    if try_make_dir:
        os.makedirs(large_dir, exist_ok=True)
    if not os.path.isfile(filename):
        print("   Downloading illustration...", flush=True, end="\r")
        with cd(large_dir):
            api.download(url)


@spinner
def download_large_vp(image_id):
    post_json = api.illust_detail(image_id)["illust"]
    url, filename = get_url_and_filename(post_json, "large", True)
    artist_user_id = post_json["user"]["id"]

    large_dir = f"/tmp/koneko/{artist_user_id}/individual/"
    make_path_and_download(large_dir, url, filename)
    return artist_user_id, filename, post_json


def get_url_and_filename_full(url, png=False):
    """
    The difference between this and get_url_and_filename() is that this
    is for transforming a url from get_url_and_filename() into the original
    resolution url. ("Large" res isn't the largest)

    url : str
        url should be from get_url_and_filename()
    """
    url = re.sub(r"_p0_master\d+", "_p0", url)
    url = re.sub(r"c\/\d+x\d+_\d+_\w+\/img-master", "img-original", url)
    # If it doesn't work, try changing to png
    # Feh will fail opening the image, but no way to get its exit code...
    if png:
        url = url.replace("jpg", "png")
    filename = url.split("/")[-1]
    return url, filename


def download_full_core(url, png=False):
    url, filename = get_url_and_filename_full(url, png)
    make_path_and_download(
        f"{os.path.expanduser('~')}/Downloads/", url, filename, try_make_dir=False
    )
    return filename


@spinner
def download_full(png=False, **kwargs):
    if "post_json" in kwargs.keys():
        post_json = kwargs["post_json"]
    elif "image_id" in kwargs.keys():
        current_image = api.illust_detail(kwargs["image_id"])
        post_json = current_image.illust
    url = get_url_and_filename(post_json, "large")

    filename = download_full_core(url, png)
    return f"/home/twenty/Downloads/{filename}"  # Filepath


def download_core(download_path, urls, rename_images=False, file_names=None):
    # TODO: asynchronously display images (call lsix) after every
    # downloaded pic. No need to wait for all of them to be downloaded
    # Requires a rewrite of lsix, because I only want it to display the
    # latest image and not create a new montage of all images so far.
    # A custom implementation of the gallery in icat seems to be better
    os.makedirs(download_path, exist_ok=True)
    with cd(download_path):
        with ThreadPoolExecutor(max_workers=3) as executor:
            for (index, url) in enumerate(urls):
                img_name = url.split("/")[-1]

                if rename_images:
                    img_ext = img_name.split(".")[-1]
                    if index < 10:
                        # Assumes 10 < number of files < 100
                        number_prefix = str(index).rjust(2, "0")
                    else:
                        number_prefix = str(index)
                    new_file_name = f"{number_prefix}_{file_names[index]}.{img_ext}"

                else:
                    new_file_name = img_name

                if not os.path.isfile(new_file_name):
                    # print(f"Downloading {new_file_name}...")
                    print("   Downloading illustrations...", flush=True, end="\r")
                    future = executor.submit(
                        async_download, url, img_name, new_file_name
                    )


@spinner
def download_multi(artist_user_id, image_id, page_urls):
    """
    page_urls : List of str
        List of all image urls; images are part of a single (multi-image) post
    """
    list_of_names = [i.split("/")[-1] for i in page_urls]
    download_path = f"/tmp/koneko/{artist_user_id}/individual/{image_id}/"
    download_core(download_path, page_urls)
    return list_of_names


# - End non interactive, invisible to user (backend) functions


# - Non interactive, visible to user functions
# @timer
def show_artist_illusts(path):
    """
    This assumes you're in the directory where both koneko.py and lscat is in
    """
    lscat_path = os.getcwd()
    with cd(path):
        os.system(f"{lscat_path}/lscat")


def open_image(post_json, artist_user_id, number, current_page_num):
    """
    Opens image given by the number (medium-res), downloads large-res and
    display that

    Parameters
    ----------
    post_json : JsonDict
        description
    number : int
        The number prefixed in each image
    artist_user_id : int
    current_page_num : int
    """
    if number < 10:
        search_string = f"0{number}_"
    else:
        search_string = f"{number}_"

    # display the already-downloaded medium-res image first, then download and
    # display the large-res
    os.system("clear")
    os.system(
        f"kitty +kitten icat --silent /tmp/koneko/{artist_user_id}/{current_page_num}/{search_string}*"
    )

    url, filename = get_url_and_filename(post_json, "large", True)
    download_large(artist_user_id, current_page_num, url, filename)

    # TODO: non blocking command input.
    # open medium res image
    # run download_large on a separate thread
    # in the meantime, continue:
    #   run get_pages_url_in_post()
    #   run image_prompt()        <------ INPUT IS BLOCKING, BELOW NEVER RUNS
    # when download_large finishes, display the large image (run below command)

    # Can't put input into separate thread, as it will not correctly receive
    # the input
    # Can't display large image on a separate thread, as icat doesn't detect
    # kitty and fails
    # Only solution is to get image_prompt() to interrupt when it receives a
    # signal that download_large() has finished

    os.system(
        f"kitty +kitten icat --silent /tmp/koneko/{artist_user_id}/{current_page_num}/large/{filename}"
    )


def open_image_vp(artist_user_id, filename):
    os.system(
        f"kitty +kitten icat --silent /tmp/koneko/{artist_user_id}/individual/{filename}"
    )


# - End non interactive, visible to user functions


# - Interactive functions (frontend)
# - Prompt functions
def begin_prompt():
    print(
        "\n        Select action:\n\
        1. View artist illustrations\n\
        2. Open pixiv post\n\n\
        q. Quit\n"
    )
    command = input("Enter a number: ")
    return command


def artist_user_id_prompt():
    artist_user_id = input("Enter artist ID or url:\n")
    return artist_user_id


# - Prompt functions with logic
def image_prompt(image_id, artist_user_id, **kwargs):
    """
    Image view commands:
    b -- go back to the gallery
    n -- view next image in post (only for posts with multiple pages)
    p -- view previous image in post (same as above)
    d -- download this image
    o -- open pixiv post in browser
    h -- show this help

    q -- quit (with confirmation)

    """
    try:  # Posts with multiple pages
        page_urls = kwargs["page_urls"]
        current_page_num_post = kwargs["current_page_num_post"]
        number_of_pages = kwargs["number_of_pages"]
        list_of_names = kwargs["list_of_names"]
    except KeyError:
        pass

    try:  # Gallery view -> next page(s) -> image prompt -> back
        current_page_num = kwargs["current_page_num"]
        current_page = kwargs["current_page"]
    except KeyError:  # Comes from mode 2
        current_page_num = 1

    while True:
        image_prompt_command = input("Enter an image view command: ")
        if image_prompt_command == "b":
            if current_page_num > 1:
                # TODO: shouldn't need to do all the checks like prefetch
                # That means all data from gallery prompt has to be passed
                # to here
                artist_illusts_mode(
                    artist_user_id, current_page_num, current_page=current_page
                )
            else:
                artist_illusts_mode(artist_user_id, current_page_num)

        elif image_prompt_command == "q":
            answer = input("Are you sure you want to exit? [y/N]:\n")
            if answer == "y" or not answer:
                sys.exit(0)
            else:
                continue

        elif image_prompt_command == "o":
            link = f"https://www.pixiv.net/artworks/{image_id}"
            os.system(f"xdg-open {link}")
            print(f"Opened {link} in browser")

        elif image_prompt_command == "d":
            filepath = download_full(image_id=image_id)
            png = imghdr.what(filepath)
            if not png:
                os.remove(filepath)
                download_full(png=True, image_id=image_id)
            print(f"Image downloaded at {filepath}\n")

        elif image_prompt_command == "n":
            if not page_urls:
                print("This is the only page in the post!")
                continue
            if current_page_num_post + 1 == number_of_pages:
                print("This is the last image in the post!")
            else:
                current_page_num_post += 1  # Be careful of 0 index
                # IDEAL: image prompt should not be blocked while downloading
                # But I think delaying the prompt is better than waiting for an image
                # to download when you load it
                if not list_of_names:  # From gallery; download next image
                    list_of_names = download_multi(
                        artist_user_id,
                        image_id,
                        page_urls[: current_page_num_post + 1],
                    )

                open_image_vp(
                    artist_user_id, f"{image_id}/{list_of_names[current_page_num_post]}"
                )

                # Downloads the next image
                list_of_names = download_multi(
                    artist_user_id, image_id, page_urls[: current_page_num_post + 2],
                )
                print(f"Page {current_page_num_post+1}/{number_of_pages}")
                # TODO: enter {number} to jump to image number (for multi-image posts)

        elif image_prompt_command == "p":
            if not page_urls:
                print("This is the only page in the post!")
                continue
            if current_page_num_post == 0:
                print("This is the first image in the post!")
            else:
                current_page_num_post -= 1
                open_image_vp(
                    artist_user_id, f"{image_id}/{list_of_names[current_page_num_post]}"
                )
                print(f"Page {current_page_num_post+1}/{number_of_pages}")

        elif image_prompt_command == "h":
            print(image_prompt.__doc__)
        else:
            print("Invalid command")
            print(image_prompt.__doc__)


def gallery_prompt(
    current_page_illusts, current_page, current_page_num, artist_user_id
):
    """
    Gallery commands:
    {number} -- display that image; corresponds to number
        prefixed on filenames
    o{number} -- open pixiv post in browser
    d{number} -- download image in large resolution
    n -- view the next page
    p -- view the previous page
    h -- show this help
    q -- exit

    Examples:
        9   --->    Display the ninth image (in image view)
        o9  --->    Open the ninth image's post in browser
        d9  --->    Download the ninth image, in large resolution
    """
    # Fixes: Gallery -> next page -> image prompt -> back -> prev page
    if current_page_num == 1:
        # There's no need to pass it around because it'll never be changed
        # outside of gallery_prompt().
        global all_pages_cache
        all_pages_cache = {"1": current_page}

        # Prefetch the next page on first gallery load
        try:
            prefetch_next_page(current_page_num, artist_user_id)
        except LastPageException:
            pass
    else:  # Gallery -> next -> image prompt -> back
        # all_pages_cache[str(current_page_num)] = current_page
        pass

    print(f"Page {current_page_num}")
    while True:
        gallery_command = input("Enter a gallery command: ")
        if gallery_command == "q":
            answer = input("Are you sure you want to exit? [y/N]:\n")
            if answer == "y" or not answer:
                sys.exit(0)
            else:
                continue

        elif gallery_command[0] == "o":
            image_id = current_page_illusts[int(gallery_command[1:])]["id"]
            link = f"https://www.pixiv.net/artworks/{image_id}"
            os.system(f"xdg-open {link}")
            print(f"Opened {link}!\n")
            continue

        elif gallery_command[0] == "d":
            post_json = current_page_illusts[int(gallery_command[1:])]
            filepath = download_full(post_json=post_json)
            print(f"Image downloaded at {filepath}\n")
            continue

        elif gallery_command == "n":
            # First time pressing n: will always be 2
            download_path = f"/tmp/koneko/{artist_user_id}/{current_page_num+1}/"
            try:
                show_artist_illusts(download_path)
            except FileNotFoundError:
                print("This is the last page!")
                continue
            current_page_num += 1  # Only increment if successful
            print(f"Page {current_page_num}")

            try:
                # After showing gallery, pre-fetch the next page
                prefetch_next_page(current_page_num - 1, artist_user_id)
            except LastPageException:
                print("This is the last page!")
                continue

        elif gallery_command == "p":
            if current_page_num > 1:
                # It's -2 because current_page_num starts at 1
                current_page = all_pages_cache[str(current_page_num - 1)]
                current_page_illusts = current_page["illusts"]
                current_page_num -= 1
                # download_path should already be set
                download_path = f"/tmp/koneko/{artist_user_id}/{current_page_num}/"
                show_artist_illusts(download_path)
                print(f"Page {current_page_num}")

            else:
                print("This is the first page!")

        elif gallery_command == "h":
            print(gallery_prompt.__doc__)

        else:  # main_command is an int
            try:
                current_page = all_pages_cache[str(current_page_num)]
                current_page_illusts = current_page["illusts"]
                post_json = current_page_illusts[int(gallery_command)]
                image_id = post_json.id

                open_image(
                    post_json, artist_user_id, int(gallery_command), current_page_num
                )

                # TODO: it's async now but still blocking, as the result
                # is needed to pass to function
                # Threading won't even do anything meaningful here
                # with ThreadPoolExecutor(max_workers=3) as executor:
                #    future = executor.submit(
                #        get_pages_url_in_post,
                #        post_json
                #    )
                #
                # number_of_pages, page_urls = future.result()

                number_of_pages, page_urls = get_pages_url_in_post(post_json, "large")

                image_prompt(
                    image_id,
                    artist_user_id,
                    current_page_num=current_page_num,
                    current_page=current_page,
                    page_urls=page_urls,
                    current_page_num_post=0,
                    number_of_pages=number_of_pages,
                    list_of_names=None,
                )

            except ValueError:
                print("Invalid command")
                print(gallery_prompt.__doc__)


# - End interactive (frontend) functions


# - Mode and loop functions (some interactive and some not)
def artist_illusts_mode(artist_user_id, current_page_num=1, fast=False, **kwargs):
    if not fast:
        if current_page_num == 1:
            current_page = user_illusts_spinner(artist_user_id)
        else:
            current_page = kwargs["current_page"]
        current_page_illusts = current_page["illusts"]

        urls, download_path = download_illusts(
            current_page_illusts, current_page_num, artist_user_id
        )

    show_artist_illusts(download_path)
    gallery_prompt(
        current_page_illusts, current_page, current_page_num, artist_user_id,
    )


def view_post_mode(image_id):
    artist_user_id, filename, post_json = download_large_vp(image_id)
    open_image_vp(artist_user_id, filename)

    number_of_pages, page_urls = get_pages_url_in_post(post_json, "large")

    if number_of_pages == 1:
        list_of_names = None
    else:
        list_of_names = download_multi(artist_user_id, image_id, page_urls[:2])

    image_prompt(
        image_id,
        artist_user_id,
        page_urls=page_urls,
        current_page_num_post=0,
        number_of_pages=number_of_pages,
        list_of_names=list_of_names,
    )

    artist_illusts_mode(artist_user_id)


def artist_illusts_mode_loop(prompted, **kwargs):
    while True:
        if prompted:
            artist_user_id = artist_user_id_prompt()
            os.system("clear")
            if "pixiv" in artist_user_id:
                artist_user_id = artist_user_id.split("/")[-1]
            # After the if, input must either be int or invalid
            try:
                int(artist_user_id)
            except ValueError:
                print("Invalid user ID!")
                continue
        else:
            artist_user_id = kwargs["artist_user_id"]

        api_thread.join()  # Wait for api to finish
        global api
        api = api_queue.get()  # Assign api to PixivAPI object

        artist_illusts_mode(artist_user_id)


def view_post_mode_loop(prompted, **kwargs):
    while True:
        if prompted:
            url_or_id = input("Enter pixiv post url or ID:\n")
            os.system("clear")
            if "pixiv" in url_or_id:
                image_id = url_or_id.split("/")[-1]
            else:
                image_id = url_or_id
            # After the if, input must either be int or invalid
            try:
                int(image_id)
            except ValueError:
                print("Invalid image ID!")
                continue
        else:
            image_id = kwargs["image_id"]

        api_thread.join()  # Wait for api to finish
        global api
        api = api_queue.get()  # Assign api to PixivAPI object

        view_post_mode(image_id)


def main_loop(prompted, **kwargs):
    while True:
        if prompted:
            main_command = begin_prompt()
        else:
            main_command = kwargs["main_command"]

        if main_command == "1":
            try:
                artist_illusts_mode_loop(prompted, **kwargs)
            except KeyboardInterrupt:
                continue

        elif main_command == "2":
            try:
                view_post_mode_loop(prompted, **kwargs)
            except KeyboardInterrupt:
                continue

        elif main_command == "q":
            answer = input("Are you sure you want to exit? [y/N]:\n")
            if answer == "y" or not answer:
                break

        else:
            print("Invalid command!")
            continue


def main():
    # It'll never be changed after logging in
    global api, api_queue, api_thread
    api_queue = queue.Queue()
    api_thread = threading.Thread(target=setup, args=(api_queue,))
    api_thread.start()  # Start logging in

    # During this part, the API can still be logging in but we can proceed
    # TODO: put a cute anime girl here with icat
    os.system("clear")

    # Direct command line arguments, skip begin_prompt()
    if len(sys.argv) == 2:
        prompted = False
        url = sys.argv[1]
        if "users" in url:
            artist_user_id = url.split("/")[-1].split("\\")[-1][1:]
            main_command = "1"
            kwargs = {"artist_user_id": artist_user_id, "main_command": main_command}

        elif "artworks" in url:
            image_id = url.split("/")[-1].split("\\")[0]
            main_command = "2"
            kwargs = {"image_id": image_id, "main_command": main_command}

        elif "illust_id" in url:
            image_id = re.findall(r"&illust_id.*", url)[0].split("=")[-1]
            main_command = "2"
            kwargs = {"image_id": image_id, "main_command": main_command}

    elif len(sys.argv) > 3:
        print("Too many arguments!")
        sys.exit(1)

    else:
        prompted = True
        kwargs = {}

    try:
        main_loop(prompted, **kwargs)
    except KeyboardInterrupt:
        print("\n")
        answer = input("Are you sure you want to exit? [y/N]:\n")
        if answer == "y" or not answer:
            sys.exit(1)


if __name__ == "__main__":
    main()
