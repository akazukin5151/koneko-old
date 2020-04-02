"""
TODO: handle posts with multiple images:
    Need an indicator in gallery view (need to rewrite lscat first)
IMPROVEMENT: if post has multiple images, there should be a preview in image view
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
import cytoolz
from pixivpy3 import AppPixivAPI
from pure import cd, spinner
from lscat import main as lscat


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


# - Other backend functions; all pure functions except for last one
@cytoolz.curry
def get_url(post_json, size):
    """
    size : str
        One of: ("square-medium", "medium", "large")
    """
    return post_json["image_urls"][size]


def split_backslash_last(str):
    """
    Intended for splitting url to get filename, but it has lots of applications...
    """
    return str.split("/")[-1]


@cytoolz.curry
def get_title(current_page_illusts, post_number):
    return current_page_illusts[post_number]["title"]


def get_medium_urls_in_page(current_page_illusts):
    get_medium_url = get_url(size="medium")
    urls = list(map(get_medium_url, current_page_illusts))
    return urls


def get_titles_in_page(current_page_illusts):
    get_titles = get_title(current_page_illusts)
    titles = list(map(get_titles, range(len(current_page_illusts))))
    return titles


@spinner("")
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
            page_urls.append(get_url(list_of_pages[i], size))
    else:
        page_urls = None

    return number_of_pages, page_urls


@spinner("Fetching user illustrations... ")
def get_user_illusts_spinner(artist_user_id):
    # There's a delay here
    # Threading won't do anything meaningful here...
    # IMPROVEMENT: Caching it (in non volatile storage) might work
    # print("   Fetching user illustrations...", flush=True, end="\r")
    return api.user_illusts(artist_user_id)


def get_full_image_details(png=False, **kwargs):
    """
    Downloads one image in full resolution (the highest; equivalent to saving
    it manually through browser). Works from either image or gallery mode
    """
    if "post_json" in kwargs.keys():
        post_json = kwargs["post_json"]
    elif "image_id" in kwargs.keys():
        current_image = api.illust_detail(kwargs["image_id"])
        post_json = current_image.illust

    url = change_url_to_full(post_json, png)
    filename = split_backslash_last(url)
    filepath = generate_filepath(filename)
    return url, filename, filepath


def change_url_to_full(post_json, png=False):
    url = get_url(post_json, "large")
    url = re.sub(r"_p0_master\d+", "_p0", url)
    url = re.sub(r"c\/\d+x\d+_\d+_\w+\/img-master", "img-original", url)

    # If it doesn't work, try changing to png
    if png:
        url = url.replace("jpg", "png")
    return url


def generate_filepath(filename):
    filepath = f"{os.path.expanduser('~')}/Downloads/{filename}"
    return filepath


def prefix_filename(old_name, new_name, number):
    img_ext = old_name.split(".")[-1]
    number_prefix = str(number).rjust(2, "0")
    new_file_name = f"{number_prefix}_{new_name}.{img_ext}"
    return new_file_name


class LastPageException(Exception):
    pass


@spinner("")  # No message because it conflicts with download_illusts()
def prefetch_next_page(current_page, current_page_num, artist_user_id, all_pages_cache):
    """
    current_page_num : int
        It is the CURRENT page number, before incrementing
    """
    download_path = f"/tmp/koneko/{artist_user_id}/{current_page_num}/"
    print("   Prefetching next page...", flush=True, end="\r")
    next_url = current_page["next_url"]
    if not next_url:  # this is the last page
        raise LastPageException

    parse_page = api.user_illusts(**api.parse_qs(next_url))
    all_pages_cache[str(current_page_num + 1)] = parse_page
    current_page_illusts = parse_page["illusts"]

    if not os.path.isdir(download_path) and len(os.listdir(download_path)) != 0:
        download_illusts(current_page_illusts, current_page_num + 1, artist_user_id)

    print("  " * 26)
    return all_pages_cache


# - Download functions
# - Core download functions (for async)
def async_download_core(download_path, urls, rename_images=False, file_names=None):
    """
    Core logic for async downloading
    """
    oldnames = list(map(split_backslash_last, urls))
    if rename_images:
        newnames = list(map(prefix_filename, oldnames, file_names, range(len(urls))))
    else:
        newnames = oldnames

    os.makedirs(download_path, exist_ok=True)
    with cd(download_path), ThreadPoolExecutor(max_workers=30) as executor:
        urls_to_download = list(itertools.filterfalse(os.path.isfile, urls))

        # Curried submit function doesn't work...
        for (i, url) in enumerate(urls_to_download):
            executor.submit(async_download, url, oldnames[i], newnames[i])


def async_download(url, img_name, new_file_name=None):
    """
    Actually downloads given url, rename if needed. For use inside
    async_download_core
    """
    # print(f"Downloading {img_name}")
    api.download(url)
    if new_file_name:
        os.rename(f"{img_name}", f"{new_file_name}")


# - Wrappers around the core functions for async download
# @timer
@spinner(" Downloading illustrations...  ")
def download_illusts(current_page_illusts, current_page_num, artist_user_id):
    """
    Download the illustrations on one page of given artist id (using threads)

    Parameters
    ----------
    current_page_illusts : JsonDict
        JsonDict holding lots of info on all the images in the current page
    current_page_num : int
        Page as in artist illustration profile pages. Starts from 1
    artist_user_id : int
    """
    urls = get_medium_urls_in_page(current_page_illusts)
    titles = get_titles_in_page(current_page_illusts)
    download_path = f"/tmp/koneko/{artist_user_id}/{current_page_num}/"

    async_download_core(download_path, urls, rename_images=True, file_names=titles)


@spinner("")
def async_download_spinner(download_path, page_urls):
    async_download_core(download_path, page_urls)


# - Core function for downloading one image
def download_core(large_dir, url, filename, try_make_dir=True):
    """
    Actually downloads given url (non async, for single images)
    Q: duplicated with async_download()?
    A: this is for downloading one image. Using threads will slow it down
    Q: Reduce code duplication by using a 'async' param?
    A: hard to do that because threads are contained with 'with ThreadPoolExecutor'
    """
    if try_make_dir:
        os.makedirs(large_dir, exist_ok=True)
    if not os.path.isfile(filename):
        print("   Downloading illustration...", flush=True, end="\r")
        with cd(large_dir):
            api.download(url)


# @timer
@spinner("")
def download_core_spinner(large_dir, url, filename):
    download_core(large_dir, url, filename)


# - End non interactive, invisible to user (backend) functions


# - Non interactive, visible to user functions
# @timer
def show_artist_illusts(path):
    """
    This assumes you're in the directory where both koneko.py and lscat is in
    """
    lscat_path = os.getcwd()
    with cd(path):
        # os.system(f"{lscat_path}/lscat")
        lscat(path)


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

    url = get_url(post_json, "large")
    filename = split_backslash_last(url)

    large_dir = f"/tmp/koneko/{artist_user_id}/{current_page_num}/large/"
    download_core_spinner(large_dir, url, filename)

    # IMPROVEMENT: non blocking command input.
    # open medium res image
    # run download_core_spinner on a separate thread
    # in the meantime, continue:
    #   run get_pages_url_in_post()
    #   run image_prompt()        <------ INPUT IS BLOCKING, BELOW NEVER RUNS
    # when download_core_spinner finishes, display the large image (run below command)

    # Can't put input into separate thread, as it will not correctly receive
    # the input
    # Can't display large image on a separate thread, as icat doesn't detect
    # kitty and fails
    # Only solution is to get image_prompt() to interrupt when it receives a
    # signal that download_core_spinner() has finished

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
                show_gallery(artist_user_id, current_page_num, current_page)
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
            url, filename, filepath = get_full_image_details(image_id=image_id)
            # IMPROVEMENT: spinner missing for all get_full_image_details()
            # because it accepts **kwargs and that confuses the spinner decorator
            download_core(
                f"{os.path.expanduser('~')}/Downloads/",
                url,
                filename,
                try_make_dir=False,
            )

            png = imghdr.what(filepath)
            if not png:
                os.remove(filepath)

                url, filename, filepath = get_full_image_details(
                    png=True, image_id=image_id
                )
                download_core(
                    f"{os.path.expanduser('~')}/Downloads/",
                    url,
                    filename,
                    try_make_dir=False,
                )

            print(f"Image downloaded at {filepath}\n")

        elif image_prompt_command == "n":
            if not page_urls:
                print("This is the only page in the post!")
                continue
            if current_page_num_post + 1 == number_of_pages:
                print("This is the last image in the post!")
            else:
                download_path = f"/tmp/koneko/{artist_user_id}/individual/{image_id}/"
                current_page_num_post += 1  # Be careful of 0 index
                # IDEAL: image prompt should not be blocked while downloading
                # But I think delaying the prompt is better than waiting for an image
                # to download when you load it
                if not list_of_names:  # From gallery; download next image
                    selection1 = page_urls[: current_page_num_post + 1]
                    list_of_names = [split_backslash_last(url) for url in selection1]

                    async_download_spinner(download_path, selection1)

                # fmt: off
                open_image_vp(
                    artist_user_id,
                    f"{image_id}/{list_of_names[current_page_num_post]}"
                )
                # fmt: on

                # Downloads the next image
                selection2 = page_urls[: current_page_num_post + 2]
                list_of_names = [split_backslash_last(url) for url in selection2]

                async_download_spinner(download_path, selection2)
                print(f"Page {current_page_num_post+1}/{number_of_pages}")

                # IMPROVEMENT: enter {number} to jump to image number (for
                # multi-image posts)

        elif image_prompt_command == "p":
            if not page_urls:
                print("This is the only page in the post!")
                continue
            if current_page_num_post == 0:
                print("This is the first image in the post!")
            else:
                current_page_num_post -= 1
                # fmt: off
                open_image_vp(
                    artist_user_id,
                    f"{image_id}/{list_of_names[current_page_num_post]}"
                )
                # fmt: on
                print(f"Page {current_page_num_post+1}/{number_of_pages}")

        elif image_prompt_command == "h":
            print(image_prompt.__doc__)
        else:
            print("Invalid command")
            print(image_prompt.__doc__)


def gallery_prompt(
    current_page_illusts,
    current_page,
    current_page_num,
    artist_user_id,
    all_pages_cache,
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
        # Prefetch the next page on first gallery load
        try:
            all_pages_cache = prefetch_next_page(
                current_page, current_page_num, artist_user_id, all_pages_cache
            )
        except LastPageException:
            pass
    else:  # Gallery -> next -> image prompt -> back
        all_pages_cache[str(current_page_num)] = current_page

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

            url, filename, filepath = get_full_image_details(post_json=post_json)
            download_core(
                f"{os.path.expanduser('~')}/Downloads/",
                url,
                filename,
                try_make_dir=False,
            )
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

            if not str(current_page_num) in all_pages_cache.keys():
                try:
                    # After showing gallery, pre-fetch the next page
                    all_pages_cache = prefetch_next_page(
                        current_page, current_page_num, artist_user_id, all_pages_cache
                    )
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

        # TODO: accept coordinates
        # TODO: o and d should also accept accept coordinates:
        # o {x,y} o {x y} d {x,y} d {x y}
        elif re.match(r"^\d,\d$", gallery_command):
            print("Coordinate, comma")

        elif re.match(r"^\d \d$", gallery_command):
            print("Coordinate, space")

        else:  # main_command is an int
            try:
                current_page = all_pages_cache[str(current_page_num)]
                current_page_illusts = current_page["illusts"]
                post_json = current_page_illusts[int(gallery_command)]
                image_id = post_json.id

                open_image(
                    post_json, artist_user_id, int(gallery_command), current_page_num
                )

                # IMPROVEMENT: it's async now but still blocking, as the result
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
def show_gallery(artist_user_id, current_page_num, current_page, show=True):
    download_path = f"/tmp/koneko/{artist_user_id}/{current_page_num}/"
    current_page_illusts = current_page["illusts"]

    if current_page_num == 1:
        if not os.path.isdir(download_path) and len(os.listdir(download_path)) != 0:
            download_illusts(current_page_illusts, current_page_num, artist_user_id)

    if show:
        show_artist_illusts(download_path)

    all_pages_cache = {"1": current_page}
    gallery_prompt(
        current_page_illusts,
        current_page,
        current_page_num,
        artist_user_id,
        all_pages_cache,
    )


def artist_illusts_mode(artist_user_id, current_page_num=1, **kwargs):
    """
    Use this if get_user_illusts_spinner() is needed (don't have current_page
    yet)
    Use show_gallery() otherwise (such as, after returning from image mode
    to gallery)
    """
    if current_page_num == 1:
        download_path = f"/tmp/koneko/{artist_user_id}/{current_page_num}/"
        # If path exists, show immediately (without checking for contents!)
        if os.path.isdir(download_path) and len(os.listdir(download_path)) != 0:
            show_artist_illusts(download_path)

        current_page = get_user_illusts_spinner(artist_user_id)
        show_gallery(artist_user_id, current_page_num, current_page, show=False)

    else:
        current_page = kwargs["current_page"]
        show_gallery(artist_user_id, current_page_num, current_page)


def view_post_mode(image_id):
    # illust_detail might need a spinner
    post_json = api.illust_detail(image_id)["illust"]
    url = get_url(post_json, "large")
    filename = split_backslash_last(url)
    artist_user_id = post_json["user"]["id"]

    large_dir = f"/tmp/koneko/{artist_user_id}/individual/"
    download_core_spinner(large_dir, url, filename)
    open_image_vp(artist_user_id, filename)

    number_of_pages, page_urls = get_pages_url_in_post(post_json, "large")

    if number_of_pages == 1:
        list_of_names = None
    else:
        list_of_names = [split_backslash_last(url) for url in page_urls[:2]]

        download_path = f"/tmp/koneko/{artist_user_id}/individual/{image_id}/"
        async_download_spinner(download_path, page_urls[:2])

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
                artist_user_id = split_backslash_last(artist_user_id)
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
                image_id = split_backslash_last(url_or_id)
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
    # TODO: gallery mode - if tmp has artist id and '1' dir, immediately
    # show it without trying to log in or download
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
    # IMPROVEMENT: put a cute anime girl here with icat
    os.system("clear")

    # Direct command line arguments, skip begin_prompt()
    if len(sys.argv) == 2:
        prompted = False
        url = sys.argv[1]
        if "users" in url:
            artist_user_id = split_backslash_last(url).split("\\")[-1][1:]
            main_command = "1"
            kwargs = {"artist_user_id": artist_user_id, "main_command": main_command}

        elif "artworks" in url:
            image_id = split_backslash_last(url).split("\\")[0]
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
