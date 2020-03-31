"""
TODO: handle posts with multiple images:
    Need an indicator in gallery view (need to rewrite lscat first)
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
from configparser import ConfigParser
from contextlib import contextmanager
from pixivpy3 import *

import time
import functools


def timer(func):
    @functools.wraps(func) # Preserve original func.__name__
    def wrapper(*args, **kwargs):
        t0 = time.time()
        value = func(*args, **kwargs)
        t1 = time.time()
        total = t1 - t0
        with open("/home/twenty/Workspace/pixiv/time.txt", "a") as the_file:
            the_file.write(f"{func.__name__!r}() time: {total}\n")
        return value

    return wrapper


# https://stackoverflow.com/questions/431684/how-do-i-change-the-working-directory-in-python/24176022#24176022
@contextmanager
def cd(newdir):
    prevdir = os.getcwd()
    os.chdir(os.path.expanduser(newdir))
    try:
        yield
    finally:
        os.chdir(prevdir)


def spin(done):
    for char in itertools.cycle('|/-\\'): # Infinite loop
        print(char, flush=True, end='\r')
        if done.wait(.1):
            break
    print(' ' * len(char), end='\r') # clears the spinner


def spinner(func):
    """
    https://github.com/fluentpython/example-code/blob/master/18-asyncio-py3.7/spinner_asyncio.py
    """

    def wrapper(*args, **kwargs):
        done = threading.Event()
        spinner = threading.Thread(target=spin, args=(done,)) # Doesn't start it yet...
        spinner.start() # start spinning

        result = func(*args, **kwargs) # run slow function, blocking

        done.set() # once slow function finishes, set it to be done, ending the spinner
        spinner.join() # wait for spinner to end
        return result
    return wrapper


# @timer
def setup(out_queue):
    api = AppPixivAPI()
    # Read config.ini file
    config_object = ConfigParser()
    config_object.read(f"{os.path.expanduser('~/.config/koneko/')}config.ini")
    config = config_object["Credentials"]

    # print("Logging in...")
    api.login(config["Username"], config["Password"])
    out_queue.put(api)
    # return api


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


def async_download(api, url, img_name, new_file_name):
    api.download(url)
    os.rename(f"{img_name}", f"{new_file_name}")

# @timer
@spinner
def download_illusts(api, current_page_illusts, current_page_num, artist_user_id):
    urls = []
    file_names = []
    for i in range(len(current_page_illusts)):
        # Or square medium
        urls.append(get_url_and_filename(current_page_illusts[i], "medium"))
        file_names.append(current_page_illusts[i]["title"])

    download_path = f"/tmp/koneko/{artist_user_id}/{current_page_num}/"
    os.makedirs(download_path, exist_ok=True)
    with cd(download_path):
        with ThreadPoolExecutor(max_workers=3) as executor:
            for (index, url) in enumerate(urls):
                img_name = url.split("/")[-1]
                img_ext = img_name.split(".")[-1]

                if index < 10:
                   # Assumes 10 < number of files < 100
                   number_prefix = str(index).rjust(2, "0")
                else:
                   number_prefix = str(index)

                new_file_name = f"{number_prefix}_{file_names[index]}.{img_ext}"

                if not os.path.isfile(new_file_name):
                    print(f"Downloading {new_file_name}...")
                    future = executor.submit(async_download, api, url, img_name, new_file_name)

                # TODO: asynchronously display images (call lsix) after every
                # downloaded pic. No need to wait for all of them to be downloaded
                # Requires a rewrite of lsix, because I only want it to display the
                # latest image and not create a new montage of all images so far.
                # A custom implementation of the gallery in icat seems to be better
        # All files downloaded
    return urls, download_path


# @timer
def show_artist_illusts(path):
    lscat_path = os.getcwd()
    with cd(path):
        os.system(f"{lscat_path}/lscat")


def open_image(api, post_json, artist_user_id, number, current_page_num):
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
    download_large(api, artist_user_id, current_page_num, url, filename)

    # TODO: non blocking command input. solution 1: run input() in another
    # thread. doesn't work because it doesn't wait for input + enter and
    # immediately quits.
    # solution 2: run download_large in another thread. doesn't work because
    # icat doesn't detect kitty and fails
    # Just use solution 2, but don't call icat yet?

    os.system(
        f"kitty +kitten icat --silent /tmp/koneko/{artist_user_id}/{current_page_num}/large/{filename}"
    )



def open_image_vp(artist_user_id, filename):
    os.system(
        f"kitty +kitten icat --silent /tmp/koneko/{artist_user_id}/individual/{filename}"
    )


# @timer
@spinner
def download_large(api, artist_user_id, current_page_num, url, filename):
    large_dir = f"/tmp/koneko/{artist_user_id}/{current_page_num}/large/"
    filepath = f"{large_dir}{filename}"
    make_path_and_download(api, large_dir, url, filename)


def make_path_and_download(api, large_dir, url, filename, try_make_dir=True):
    if try_make_dir:
        os.makedirs(large_dir, exist_ok=True)
    if not os.path.isfile(filename):
        with cd(large_dir):
            api.download(url)

def get_url_and_filename(post_json, size, get_filename=False):
    url = post_json["image_urls"][size]
    if not get_filename:
        return url
    filename = url.split("/")[-1]
    return url, filename

@spinner
def download_large_vp(api, image_id):
    post_json = api.illust_detail(image_id)["illust"]
    url, filename = get_url_and_filename(post_json, "large", True)
    artist_user_id = post_json["user"]["id"]

    large_dir = f"/tmp/koneko/{artist_user_id}/individual/"
    make_path_and_download(api, large_dir, url, filename)
    return artist_user_id, filename, post_json


def get_url_and_filename_full(url):
    url = re.sub(r"_p0_master\d+", "_p0", url)
    url = re.sub(r"c\/\d+x\d+_\d+_\w+\/img-master", "img-original", url)
    filename = url.split("/")[-1]
    return url, filename


def download_full_core(api, url):
    url, filename = get_url_and_filename_full(url)
    make_path_and_download(
        api, f"{os.path.expanduser('~')}/Downloads/", url, filename, try_make_dir=False
    )
    return filename

@spinner
def download_full(api, **kwargs):
    if "post_json" in kwargs.keys():
        post_json = kwargs['post_json']
    elif "image_id" in kwargs.keys():
        current_image = api.illust_detail(kwargs["image_id"])
        post_json = current_image.illust
    url = get_url_and_filename(post_json, "large")

    filename = download_full_core(api, url)
    return f"/home/twenty/Downloads/{filename}"  # Filepath


# TODO: consider refactoring with download_illusts(). They are similar because
# this one is for downloading from image view, on a post with multiple images
# Might need to do async first (see THERE)
@spinner
def download_multi(api, artist_user_id, image_id, page_urls):
    list_of_names = []
    download_path = f"/tmp/koneko/{artist_user_id}/individual/{image_id}/"
    os.makedirs(download_path, exist_ok=True)
    with cd(download_path):
        for i in range(len(page_urls)):
            url = page_urls[i]
            img_name = url.split("/")[-1]
            list_of_names.append(img_name)

            if not os.path.isfile(img_name):
                print(f"Downloading {img_name}...")
                api.download(url)
    return list_of_names


def image_prompt(api, image_id, artist_user_id, **kwargs):
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
    try: # Posts with multiple pages
        page_urls = kwargs["page_urls"]
        current_page_num_post = kwargs["current_page_num_post"]
        number_of_pages = kwargs["number_of_pages"]
    except KeyError:
        pass

    try: # Gallery view -> next page(s) -> image prompt -> back
        current_page_num = kwargs["current_page_num"]
        current_page = kwargs["current_page"]
    except KeyError:
        current_page_num = 1

    while True:
        image_prompt_command = input("Enter an image view command: ")
        if image_prompt_command == "b":
            if current_page_num > 1:
                artist_illusts_mode(api, artist_user_id, current_page_num, current_page=current_page)
            else:
                artist_illusts_mode(api, artist_user_id, current_page_num)

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
            filepath = download_full(api, image_id=image_id)
            print(f"Image downloaded at {filepath}\n")

        elif image_prompt_command == "n":
            if not page_urls:
                print("This is the only page in the post!")
                continue
            if current_page_num_post + 1 == number_of_pages:
                print("This is the last image in the post!")
            else:
                current_page_num_post += 1  # Be careful of 0 index
                # TODO: download first pic, display, then
                # download the rest in the background asynchronously
                # Note: when used from gallery view, it first downloads the first pic
                # When 'n' is passed, it downloads the rest
                # TODO: in gallery view, if multi-images detected, download in background. THERE
                list_of_names = download_multi(api, artist_user_id, image_id, page_urls)
                open_image_vp(
                    artist_user_id, f"{image_id}/{list_of_names[current_page_num_post]}"
                )
                print(f"Page {current_page_num_post+1}/{number_of_pages}")
                # TODO: enter {digit} to jump to image number (for multi-image posts)

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
    api, current_page_illusts, current_page, current_page_num, artist_user_id
):
    """
    Gallery commands:
    {digit} -- display that image; corresponds to number
        prefixed on filenames
    o{digit} -- open pixiv post in browser
    d{digit} -- download image in large resolution
    n -- view the next page
    p -- view the previous page
    h -- show this help
    q -- exit

    Examples:
        9   --->    Display the ninth image (in image view)
        o9  --->    Open the ninth image's post in browser
        d9  --->    Download the ninth image, in large resolution
    """
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
            os.system(f"xdg-open https://www.pixiv.net/artworks/{image_id}")

        elif gallery_command[0] == "d":
            post_json = current_page_illusts[int(gallery_command[1:])]
            filepath = download_full(api, post_json=post_json)
            print(f"Image downloaded at {filepath}\n")

        elif gallery_command == "n":
            # TODO: reduce delay as it's requesting the api every time,
            # even if the files are already downloaded. Same for prev page.
            current_page_num += 1
            next_url = current_page["next_url"]
            # Mutating current_page to use the next page
            current_page = api.user_illusts(**api.parse_qs(next_url))
            current_page_illusts = current_page["illusts"]
            urls, download_path = download_illusts(
                api, current_page_illusts, current_page_num, artist_user_id
            )
            show_artist_illusts(download_path)

        elif gallery_command == "p":
            if current_page_num > 1:
                matched = re.findall(r"\&offset=\d+", next_url)[0]
                new_offset = int(matched.split("=")[1]) - 30
                assert new_offset >= 0
                prev_url = f"{next_url.split('&offset')[0]}&offset={new_offset}"

                current_page = api.user_illusts(**api.parse_qs(prev_url))
                current_page_illusts = current_page["illusts"]
                current_page_num -= 1
                urls, download_path = download_illusts(
                    api, current_page_illusts, current_page_num, artist_user_id
                )
                show_artist_illusts(download_path)

            else:
                print("This is the first page!")

        elif gallery_command == "h":
            print(gallery_prompt.__doc__)

        else:  # main_command is an int
            try:
                post_json = current_page_illusts[int(gallery_command)]
                image_id = post_json.id

                open_image(
                    api,
                    post_json,
                    artist_user_id,
                    int(gallery_command),
                    current_page_num,
                )

                # TODO: huge delay here, need to run asynchronously
                number_of_pages, page_urls = check_multiple_images_in_post(
                    api, post_json
                )

                image_prompt(
                    api,
                    image_id,
                    artist_user_id,
                    current_page_num=current_page_num,
                    current_page=current_page,
                    page_urls=page_urls,
                    current_page_num_post=0,
                    number_of_pages=number_of_pages,
                )

            except ValueError:
                print("Invalid command")
                print(gallery_prompt.__doc__)


@spinner
def check_multiple_images_in_post(api, post_json):
    number_of_pages = post_json.page_count
    if number_of_pages > 1:
        print(f"Page 1/{number_of_pages}")
        list_of_pages = post_json.meta_pages
        page_urls = []
        for i in range(number_of_pages):
            page_urls.append(get_url_and_filename(list_of_pages[i], "medium"))
    else:
        page_urls = None

    return number_of_pages, page_urls


def artist_illusts_mode(api, artist_user_id, current_page_num=1, **kwargs):
    # There's a delay here
    # TODO: async
    if current_page_num == 1:
        current_page = api.user_illusts(artist_user_id)
    else:
        current_page = kwargs["current_page"]
    current_page_illusts = current_page["illusts"]

    urls, download_path = download_illusts(
        api, current_page_illusts, current_page_num, artist_user_id
    )
    show_artist_illusts(download_path)
    gallery_prompt(
        api, current_page_illusts, current_page, current_page_num, artist_user_id,
    )


def view_post_mode(api, image_id):
    artist_user_id, filename, post_json = download_large_vp(api, image_id)
    open_image_vp(artist_user_id, filename)

    number_of_pages, page_urls = check_multiple_images_in_post(api, post_json)

    image_prompt(
        api,
        image_id,
        artist_user_id,
        page_urls=page_urls,
        current_page_num_post=0,
        number_of_pages=number_of_pages,
    )

    artist_illusts_mode(api, artist_user_id)


def main():
    apiQueue = queue.Queue()
    apiThread = threading.Thread(target=setup, args=(apiQueue,))
    apiThread.start()  # Start logging in

    # During this part, the API can still be logging in but we can proceed
    # TODO: put a cute anime girl here with icat
    os.system("clear")

    # Direct command line arguments, skip begin_prompt()
    if len(sys.argv) == 2:
        url = sys.argv[1]
        if "member" in url:
            artist_user_id = url.split("/")[-1].split("\\")[-1][1:]
            main_command = "1"
        elif "artworks" in url:
            image_id = url.split("/")[-1].split("\\")[0]
            main_command = "2"

        prompted = False
    elif len(sys.argv) > 3:
        print("Too many arguments!")
    else:
        main_command = begin_prompt()
        prompted = True

    if main_command == "1":
        if prompted:
            artist_user_id = artist_user_id_prompt()
            if "pixiv" in artist_user_id:
                artist_user_id = artist_user_id.split("/")[-1]

        # TODO: add spinner
        apiThread.join()  # Wait for api to finish
        api = apiQueue.get()  # Assign api to PixivAPI object

        artist_illusts_mode(api, artist_user_id)

    elif main_command == "2":
        if prompted:
            url_or_id = input("Enter pixiv post url or ID:\n")
            if "pixiv" in url_or_id:
                image_id = url_or_id.split("/")[-1]
            else:
                image_id = url_or_id

        apiThread.join()  # Wait for api to finish
        api = apiQueue.get()  # Assign api to PixivAPI object

        view_post_mode(api, image_id)

    elif main_command == "q":
        answer = input("Are you sure you want to exit? [y/N]:\n")
        if answer == "y" or not answer:
            sys.exit(0)


if __name__ == "__main__":
    main()
