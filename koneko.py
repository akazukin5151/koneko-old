"""
Browse pixiv in the terminal using kitty's icat to display images (in the
terminal!)

Requires [kitty](https://github.com/kovidgoyal/kitty) on Linux. It uses the
magical `kitty +kitten icat` 'kitten' to display images.

IMPROVEMENT: if post has multiple images, there should be a preview in image view
TODO: unit tests
IMPROVEMENT: get rid of for loops
"""

import os
import re
import sys
import queue
import imghdr
import itertools
import threading
from configparser import ConfigParser
from concurrent.futures import ThreadPoolExecutor

import cytoolz
from tqdm import tqdm
from pixivpy3 import AppPixivAPI

from pure import (
    cd,
    spinner,
    process_coords,
    prefix_filename,
    generate_filepath,
    print_multiple_imgs,
    process_coords_slice,
    split_backslash_last,
)
from lscat import main as lscat


# - Logging in function
# @timer
def setup(out_queue):
    """
    Logins to pixiv in the background, using credentials from config file.

    Parameters
    ----------
    out_queue : queue.Queue()
        queue for storing logged-in api object
    """
    api = AppPixivAPI()
    # Read config.ini file
    config_object = ConfigParser()
    config_path = os.path.expanduser('~/.config/koneko/')
    config_object.read(f"{config_path}config.ini")
    config = config_object["Credentials"]

    api.login(config["Username"], config["Password"])
    out_queue.put(api)


# - Other backend functions; all pure functions
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
    get_medium_url = url_given_size(size="medium")
    urls = list(map(get_medium_url, current_page_illusts))
    return urls


def post_titles_in_page(current_page_illusts):
    post_titles = post_title(current_page_illusts)
    titles = list(map(post_titles, enumerate(current_page_illusts)))
    return titles


@spinner("")
def page_urls_in_post(post_json, size="medium"):
    """Get the number of pages and each of their urls in a multi-image post."""
    number_of_pages = post_json.page_count
    if number_of_pages > 1:
        print(f"Page 1/{number_of_pages}")
        list_of_pages = post_json.meta_pages
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


class LastPageException(Exception):
    pass


# - Uses web requests, impure
@spinner("Fetching user illustrations... ")
def user_illusts_spinner(artist_user_id):
    # There's a delay here
    # Threading won't do anything meaningful here...
    # IMPROVEMENT: Caching it (in non volatile storage) might work
    return api.user_illusts(artist_user_id)


def full_img_details(png=False, post_json=None, image_id=None):
    """
    All in one function that gets the full-res url, filename, and filepath.
    """
    if (not post_json) and image_id:
        current_image = api.illust_detail(image_id)
        post_json = current_image.illust

    url = change_url_to_full(post_json, png)
    filename = split_backslash_last(url)
    filepath = generate_filepath(filename)
    return url, filename, filepath


@spinner("")  # No message because it conflicts with download_illusts()
def prefetch_next_page(current_page_num, artist_user_id, all_pages_cache):
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

    download_path = f"{DIR}/{artist_user_id}/{current_page_num+1}/"
    if not os.path.isdir(download_path):
        download_illusts(current_page_illusts, current_page_num + 1, artist_user_id)
    print("  " * 26) # Magic
    return all_pages_cache


# - Download functions
# - Core download functions (for async)
def async_download_core(
    download_path, urls, rename_images=False, file_names=None, pbar=None
):
    """Core logic for async downloading."""
    oldnames = list(map(split_backslash_last, urls))
    if rename_images:
        newnames = list(map(prefix_filename, oldnames, file_names, enumerate(urls)))
    else:
        newnames = oldnames

    os.makedirs(download_path, exist_ok=True)
    with cd(download_path):
        with ThreadPoolExecutor(max_workers=30) as executor:
            urls_to_download = list(itertools.filterfalse(os.path.isfile, urls))
            # Curried submit function doesn't work...
            for (i, url) in enumerate(urls_to_download):
                executor.submit(downloadr, url, oldnames[i], newnames[i], pbar=pbar)


def downloadr(url, img_name, new_file_name=None, pbar=None):
    """Actually downloads given url, rename if needed."""
    try:
        # print(f"Downloading {img_name}")
        api.download(url)
    except RemoteDisconnected as e: # TODO: retry
        print(f"Network error! Caught {e}")
    if pbar:
        pbar.update(1)
    # print(f"{img_name} done!")
    if new_file_name:
        os.rename(img_name, new_file_name)


# - Wrappers around the core functions for async download
# @timer
# @spinner(" Downloading illustrations...  ")
def download_illusts(current_page_illusts, current_page_num, artist_user_id, pbar=None):
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
    urls = medium_urls(current_page_illusts)
    titles = post_titles_in_page(current_page_illusts)
    download_path = f"{DIR}/{artist_user_id}/{current_page_num}/"

    async_download_core(
        download_path, urls, rename_images=True, file_names=titles, pbar=pbar
    )


@spinner("")
def async_download_spinner(download_path, page_urls):
    async_download_core(download_path, page_urls)


# @timer
@spinner("")
def download_core_spinner(large_dir, url, filename):
    download_core(large_dir, url, filename)


# - Functions that are wrappers around download functions, making them impure
def download_core(large_dir, url, filename, try_make_dir=True):
    """
    Downloads one url, intended for single images only
    """
    if try_make_dir:
        os.makedirs(large_dir, exist_ok=True)
    if not os.path.isfile(filename):
        print("   Downloading illustration...", flush=True, end="\r")
        with cd(large_dir):
            downloadr(url, filename, None)


def download_from_image_view(image_id, png=False):
    """
    This downloads an image, checks if it's valid. If not, retry with png.
    """
    url, filename, filepath = full_img_details(image_id=image_id, png=png)
    # IMPROVEMENT: spinner missing for all full_img_details()
    # because it accepts **kwargs and that confuses the spinner decorator
    homepath = os.path.expanduser('~')
    download_core(
        f"{homepath}/Downloads/", url, filename, try_make_dir=False,
    )

    png = imghdr.what(filepath)
    if not png:
        os.remove(filepath)
        download_from_image_view(image_id, png=True)

    print(f"Image downloaded at {filepath}\n")


def go_next_image(
    page_urls,
    img_post_page_num,
    number_of_pages,
    downloaded_images,
    artist_user_id,
    image_id,
):
    """
    Intended to be from image_prompt, for posts with multiple images.
    Downloads next image it not downloaded, open it, download the next image
    in the background

    Parameters
    img_post_page_num : int
        **Starts from 0**. Page number of the multi-image post.
    """
    download_path = f"{DIR}/{artist_user_id}/individual/{image_id}/"
    # IDEAL: image prompt should not be blocked while downloading
    # But I think delaying the prompt is better than waiting for an image
    # to download when you load it

    # First time from gallery; download next image
    if not downloaded_images:
        url = page_urls[img_post_page_num]
        downloaded_images = [split_backslash_last(url) for url in page_urls[:2]]
        async_download_spinner(download_path, url)

    # fmt: off
    open_image_vp(
        artist_user_id,
        f"{image_id}/{downloaded_images[img_post_page_num]}"
    )
    # fmt: on

    # Downloads the next image
    next_img_url = page_urls[img_post_page_num + 1]
    downloaded_images.append(split_backslash_last(next_img_url))
    async_download_spinner(download_path, next_img_url)
    print(f"Page {img_post_page_num+1}/{number_of_pages}")

    return downloaded_images


# - End non interactive, invisible to user (backend) functions


# - Non interactive, visible to user functions
# @timer
def show_artist_illusts(path):
    with cd(path):
        # This assumes you're in the directory where both koneko.py and lscat is in
        # lscat_path = os.getcwd()
        # os.system(f"{lscat_path}/lscat")
        lscat(path)


def open_image(post_json, artist_user_id, number_prefix, current_page_num):
    """
    Opens image given by the number (medium-res), downloads large-res and
    then display that.

    Parameters
    ----------
    post_json : JsonDict
        description
    number_prefix : int
        The number prefixed in each image
    artist_user_id : int
    current_page_num : int
    """
    if number_prefix < 10:
        search_string = f"0{number_prefix}_"
    else:
        search_string = f"{number_prefix}_"

    # display the already-downloaded medium-res image first, then download and
    # display the large-res
    os.system("clear")
    os.system(
        f"kitty +kitten icat --silent {DIR}/{artist_user_id}/{current_page_num}/{search_string}*"
    )

    url = url_given_size(post_json, "large")
    filename = split_backslash_last(url)

    large_dir = f"{DIR}/{artist_user_id}/{current_page_num}/large/"
    download_core_spinner(large_dir, url, filename)

    # IMPROVEMENT: non blocking command input.
    # open medium res image
    # run download_core_spinner on a separate thread
    # in the meantime, continue:
    #   run page_urls_in_post()
    #   run image_prompt()        <------ INPUT IS BLOCKING, BELOW NEVER RUNS
    # when download_core_spinner finishes, display the large image (run below command)

    # Can't put input into separate thread, as it will not correctly receive
    # the input
    # Can't display large image on a separate thread, as icat doesn't detect
    # kitty and fails
    # Only solution is to get image_prompt() to interrupt when it receives a
    # signal that download_core_spinner() has finished

    os.system("clear")
    os.system(
        f"kitty +kitten icat --silent {DIR}/{artist_user_id}/{current_page_num}/large/{filename}"
    )


def open_image_vp(artist_user_id, filename):
    os.system(
        f"kitty +kitten icat --silent {DIR}/{artist_user_id}/individual/{filename}"
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
def image_prompt(image_id, artist_user_id, current_page=None, current_page_num=1, **kwargs):
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
    """
    current_page and current_page_num is for gallery view -> next page(s) ->
    image prompt -> back
    kwargs are to store info for posts with multiple pages/images
    """
    try:  # Posts with multiple pages
        page_urls = kwargs["page_urls"]
        img_post_page_num = kwargs["img_post_page_num"]
        number_of_pages = kwargs["number_of_pages"]
        downloaded_images = kwargs["downloaded_images"]
    except KeyError:
        pass

    while True:
        image_prompt_command = input("Enter an image view command: ")
        if image_prompt_command == "b":
            if current_page_num > 1 and current_page:
                all_pages_cache = kwargs["all_pages_cache"]
                show_gallery(
                    artist_user_id,
                    current_page_num,
                    current_page,
                    all_pages_cache=all_pages_cache,
                )
            else:
                # Came from view post mode, don't know current page num
                # Defaults to page 1
                artist_illusts_mode(artist_user_id)

        elif image_prompt_command == "o":
            link = f"https://www.pixiv.net/artworks/{image_id}"
            os.system(f"xdg-open {link}")
            print(f"Opened {link} in browser")

        elif image_prompt_command == "d":
            download_from_image_view(image_id)

        # IMPROVEMENT: enter {number} to jump to image number (for
        # multi-image posts)
        elif image_prompt_command == "n":
            if not page_urls:
                print("This is the only page in the post!")
            if img_post_page_num + 1 == number_of_pages:
                print("This is the last image in the post!")

            img_post_page_num += 1  # Be careful of 0 index
            downloaded_images = go_next_image(
                page_urls,
                img_post_page_num,
                number_of_pages,
                downloaded_images,
                artist_user_id,
                image_id,
            )

        elif image_prompt_command == "p":
            if not page_urls:
                print("This is the only page in the post!")
            if img_post_page_num == 0:
                print("This is the first image in the post!")
            else:
                img_post_page_num -= 1
                # fmt: off
                open_image_vp(
                    artist_user_id,
                    f"{image_id}/{downloaded_images[img_post_page_num]}"
                )
                # fmt: on
                print(f"Page {img_post_page_num+1}/{number_of_pages}")

        elif image_prompt_command == "q":
            answer = input("Are you sure you want to exit? [y/N]:\n")
            if answer == "y" or not answer:
                sys.exit(0)
            else:
                continue

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
    # Gallery -> Image -> back still retains all_pages_cache, no need to
    # prefetch again
    if len(all_pages_cache) == 1:
        # Prefetch the next page on first gallery load
        try:
            all_pages_cache = prefetch_next_page(
                current_page_num, artist_user_id, all_pages_cache
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

        elif gallery_command[0] == "o":
            number = process_coords_slice(gallery_command)
            if not number:
                number = int(gallery_command[1:])

            image_id = current_page_illusts[number]["id"]
            link = f"https://www.pixiv.net/artworks/{image_id}"
            os.system(f"xdg-open {link}")
            print(f"Opened {link}!\n")

        elif gallery_command[0] == "d":
            number = process_coords_slice(gallery_command)
            if not number:
                number = int(gallery_command[1:])

            post_json = current_page_illusts[number]

            url, filename, filepath = full_img_details(post_json=post_json)

            homepath = os.path.expanduser('~')
            download_core(
                f"{homepath}/Downloads/",
                url,
                filename,
                try_make_dir=False,
            )
            print(f"Image downloaded at {filepath}\n")

        elif gallery_command == "n":
            # First time pressing n: will always be 2
            download_path = f"{DIR}/{artist_user_id}/{current_page_num+1}/"
            try:
                show_artist_illusts(download_path)
            except FileNotFoundError:
                print("This is the last page!")
                continue
            current_page_num += 1  # Only increment if successful
            print(f"Page {current_page_num}")

            # Skip prefetching again for cases like next -> prev -> next
            if str(current_page_num + 1) not in all_pages_cache.keys():
                try:
                    # After showing gallery, pre-fetch the next page
                    all_pages_cache = prefetch_next_page(
                        current_page_num, artist_user_id, all_pages_cache
                    )
                except LastPageException:
                    print("This is the last page!")

        elif gallery_command == "p":
            if current_page_num > 1:
                # It's -2 because current_page_num starts at 1
                current_page = all_pages_cache[str(current_page_num - 1)]
                current_page_illusts = current_page["illusts"]
                current_page_num -= 1
                # download_path should already be set
                download_path = f"{DIR}/{artist_user_id}/{current_page_num}/"
                show_artist_illusts(download_path)
                print(f"Page {current_page_num}")

            else:
                print("This is the first page!")

        elif gallery_command == "h":
            print(gallery_prompt.__doc__)

        else:  # Open specified image
            # Process coordinates first
            if re.match(r"^\d,\d$", gallery_command):
                number = process_coords(gallery_command, ",")
                if not number:
                    continue
                else:
                    selected_image_num = number

            elif re.match(r"^\d \d$", gallery_command):
                number = process_coords(gallery_command, " ")
                if not number:
                    continue
                else:
                    selected_image_num = number

            else:  # gallery_command is the selected img, not coordinate
                try:
                    selected_image_num = int(gallery_command)
                except ValueError:
                    print("Invalid command")
                    print(gallery_prompt.__doc__)

            current_page = all_pages_cache[str(current_page_num)]
            current_page_illusts = current_page["illusts"]
            post_json = current_page_illusts[selected_image_num]
            image_id = post_json.id

            open_image(post_json, artist_user_id, selected_image_num, current_page_num)

            # IMPROVEMENT: it's async now but still blocking, as the result
            # is needed to pass to function
            # Threading won't even do anything meaningful here
            # with ThreadPoolExecutor(max_workers=3) as executor:
            #    future = executor.submit(
            #        page_urls_in_post,
            #        post_json
            #    )
            #
            # number_of_pages, page_urls = future.result()

            number_of_pages, page_urls = page_urls_in_post(post_json, "large")

            image_prompt(
                image_id,
                artist_user_id,
                current_page_num=current_page_num,
                current_page=current_page,
                page_urls=page_urls,
                img_post_page_num=0,
                number_of_pages=number_of_pages,
                downloaded_images=None,
                all_pages_cache=all_pages_cache,
            )


# - End interactive (frontend) functions


# - Mode and loop functions (some interactive and some not)
def show_gallery(
    artist_user_id, current_page_num, current_page, show=True, all_pages_cache=None
):
    """
    Downloads images, show if requested, instantiate all_pages_cache, prompt.
    """
    download_path = f"{DIR}/{artist_user_id}/{current_page_num}/"
    current_page_illusts = current_page["illusts"]

    if not os.path.isdir(download_path):
        pbar = tqdm(total=30) # Number of images in one gallery page
        download_illusts(
            current_page_illusts, current_page_num, artist_user_id, pbar=pbar
        )
        pbar.close()

    if show:
        show_artist_illusts(download_path)
    print_multiple_imgs(current_page_illusts)

    if not all_pages_cache:
        all_pages_cache = {"1": current_page}

    gallery_prompt(
        current_page_illusts,
        current_page,
        current_page_num,
        artist_user_id,
        all_pages_cache,
    )


def artist_illusts_mode(artist_user_id, current_page_num=1):
    """
    If artist_user_id dir exists, show immediately (without checking
    for contents!)
    Else, fetch current_page json and proceed download -> show -> prompt
    """
    download_path = f"{DIR}/{artist_user_id}/{current_page_num}/"
    # If path exists, show immediately (without checking for contents!)
    if os.path.isdir(download_path):
        show_artist_illusts(download_path)
        show = False
    else:
        show = True

    current_page = user_illusts_spinner(artist_user_id)
    show_gallery(artist_user_id, current_page_num, current_page, show=show)


def view_post_mode(image_id):
    # illust_detail might need a spinner
    post_json = api.illust_detail(image_id)["illust"]
    url = url_given_size(post_json, "large")
    filename = split_backslash_last(url)
    artist_user_id = post_json["user"]["id"]

    large_dir = f"{DIR}/{artist_user_id}/individual/"
    download_core_spinner(large_dir, url, filename)
    open_image_vp(artist_user_id, filename)

    number_of_pages, page_urls = page_urls_in_post(post_json, "large")

    if number_of_pages == 1:
        downloaded_images = None
    else:
        download_path = f"{DIR}/{artist_user_id}/individual/{image_id}/"
        async_download_spinner(download_path, page_urls[:2])
        downloaded_images = [split_backslash_last(url) for url in page_urls[:2]]

    image_prompt(
        image_id,
        artist_user_id,
        page_urls=page_urls,
        img_post_page_num=0,
        number_of_pages=number_of_pages,
        downloaded_images=downloaded_images,
    )

    artist_illusts_mode(artist_user_id)


def artist_illusts_mode_loop(if_prompted, artist_user_id=None):
    while True:
        if if_prompted and not artist_user_id:
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

        api_thread.join()  # Wait for api to finish
        global api
        api = api_queue.get()  # Assign api to PixivAPI object

        artist_illusts_mode(artist_user_id)


def view_post_mode_loop(if_prompted, image_id=None):
    while True:
        if if_prompted and not image_id:
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

        api_thread.join()  # Wait for api to finish
        global api
        api = api_queue.get()  # Assign api to PixivAPI object

        view_post_mode(image_id)


def main_loop(if_prompted, main_command=None, artist_user_id=None, image_id=None):
    # IMPROVEMENT: gallery mode - if tmp has artist id and '1' dir,
    # immediately show it without trying to log in or download
    while True:
        if if_prompted and not main_command:
            main_command = begin_prompt()

        if main_command == "1":
            try:
                artist_illusts_mode_loop(if_prompted, artist_user_id)
            except KeyboardInterrupt:
                os.system("clear")

        elif main_command == "2":
            try:
                view_post_mode_loop(if_prompted, image_id)
            except KeyboardInterrupt:
                os.system("clear")

        elif main_command == "q":
            answer = input("Are you sure you want to exit? [y/N]:\n")
            if answer == "y" or not answer:
                break

        else:
            print("Invalid command!")
            continue


def main():
    global DIR
    DIR = "/tmp/koneko"
    # It'll never be changed after logging in
    global api, api_queue, api_thread
    api_queue = queue.Queue()
    api_thread = threading.Thread(target=setup, args=(api_queue,))
    api_thread.start()  # Start logging in

    # During this part, the API can still be logging in but we can proceed
    # IMPROVEMENT: put a cute anime girl here with icat
    os.system("clear")

    artist_user_id, image_id = None, None
    # Direct command line arguments, skip begin_prompt()
    if len(sys.argv) == 2:
        if_prompted = False
        url = sys.argv[1]

        if "users" in url:
            artist_user_id = split_backslash_last(url).split("\\")[-1][1:]
            main_command = "1"

        elif "artworks" in url:
            image_id = split_backslash_last(url).split("\\")[0]
            main_command = "2"

        elif "illust_id" in url:
            image_id = re.findall(r"&illust_id.*", url)[0].split("=")[-1]
            main_command = "2"

    elif len(sys.argv) > 3:
        print("Too many arguments!")
        sys.exit(1)

    else:
        if_prompted = True
        main_command = None

    try:
        main_loop(if_prompted, main_command, artist_user_id, image_id)
    except KeyboardInterrupt:
        print("\n")
        answer = input("Are you sure you want to exit? [y/N]:\n")
        if answer == "y" or not answer:
            sys.exit(1)


if __name__ == "__main__":
    main()
