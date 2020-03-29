"""
TODO: accept pixiv link via command line argument
    eg https://www.pixiv.net/en/artworks/72642560 --> image view
    https://www.pixiv.net/en/users/34931 --> artist view
TODO: handle posts with multiple images:
    Need an indicator in gallery view (need to rewrite lscat first)

Browse pixiv in the terminal using kitty's icat to display images (in the terminal!)

Requires [kitty](https://github.com/kovidgoyal/kitty) on Linux. It uses the magical `kitty +kitten icat` 'kitten' to display images.

Uses [pixivpy](https://github.com/upbit/pixivpy/), install with `pip install pixivpy`
"""

import os
import sys
import threading
import queue
import re
from configparser import ConfigParser
from contextlib import contextmanager
from pixivpy3 import *

import time
import functools


def timer(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        t0 = time.time()
        value = func(*args, **kwargs)
        t1 = time.time()
        total = t1 - t0
        with open("/home/twenty/Workspace/pixiv/time.txt", "a") as the_file:
            the_file.write(f"{func.__name__!r}() time: {total}\n")
        return value

    return wrapper

#https://stackoverflow.com/questions/431684/how-do-i-change-the-working-directory-in-python/24176022#24176022
@contextmanager
def cd(newdir):
    prevdir = os.getcwd()
    os.chdir(os.path.expanduser(newdir))
    try:
        yield
    finally:
        os.chdir(prevdir)

# @timer
def setup(out_queue):
    api = AppPixivAPI()
    #Read config.ini file
    config_object = ConfigParser()
    config_object.read(f"{os.path.expanduser('~/.config/koneko/')}config.ini")
    config = config_object["Credentials"]

    # print("Logging in...")
    api.login(config['Username'], config['Password'])
    out_queue.put(api)
    # return api


def begin_prompt():
    print("\n        Select action:\n\
        1. View artist illustrations\n\
        2. Open pixiv post\n\n\
        q. Quit\n"
    )
    command = input("Enter a number: ")
    return command


def artist_user_id_prompt():
    artist_user_id = input("Enter artist ID or url:\n")
    return artist_user_id


# TODO: reduce code duplication by pre-evaluating ['image_urls']['medium'] or ['large']
# @timer
def download_illusts(api, current_page_illusts, current_page_num, artist_user_id):
    # TODO: download asynchronously
    urls = []
    file_names = []
    for i in range(len(current_page_illusts)):
        urls.append(current_page_illusts[i]["image_urls"]["medium"])  # or square_medium
        file_names.append(current_page_illusts[i]["title"])

    download_path = f"/tmp/koneko/{artist_user_id}/{current_page_num}/"
    os.makedirs(download_path, exist_ok=True)
    with cd(download_path):
        for i in range(len(urls)):
            url = urls[i]
            img_name = url.split("/")[-1]
            img_ext = img_name.split(".")[-1]

            if len(urls) >= 10 and i < 10:
                # This assumes len(url) < 100
                number_prefix = str(i).rjust(2, "0")
            else:
                number_prefix = str(i)

            # Rename files to be prefixed with a number
            new_file_name = f"{number_prefix}_{file_names[i]}.{img_ext}"

            # TODO: asynchronously display images (call lsix) after every
            # downloaded pic. No need to wait for all of them to be downloaded
            # Requires a rewrite of lsix, because I only want it to display the
            # latest image and not create a new montage of all images so far.
            # A custom implementation of the gallery in icat seems to be better

            # Only download pictures if not already downloaded
            if not os.path.isfile(new_file_name):
                print(f"Downloading {new_file_name}...")
                # t0 = time.time()
                api.download(url)
                # t1 = time.time()
                # total = t1-t0
                # print(total)
                # with open('/home/twenty/Workspace/pixiv/downloadtime.txt', 'a') as the_file:
                #     the_file.write(f"{total}\n")
                os.rename(f"{img_name}", f"{new_file_name}")
    return urls, download_path


# @timer
def show_artist_illusts(path):
    lscat_path = os.getcwd()
    with cd(path):
        os.system(f"{lscat_path}/lscat")

def open_image(api, current_page_illusts, artist_user_id, number, current_page_num):
    # TODO: current_page_illusts is only used to pass to another function
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

    image_id, image_filename, _ = download_large(
        api, current_page_illusts, current_page_num, artist_user_id, number
    )

    # TODO: non blocking command input. solution 1: run input() in another
    # thread. doesn't work because it doesn't wait for input + enter and
    # immediately quits.
    # solution 2: run download_large in another thread. doesn't work because
    # icat doesn't detect kitty and fails
    # Warning: code below has capitalization fucked up
    #   largequeue = queue.queue()
    #   largethread = threading.thread(target=download_large, args=(api, current_page_illusts, current_page_num, artist_user_id, number, largequeue))
    #   largethread.start()
    # asynchronous command prompt here
    #    largethread.join()
    #    image_id, image_filename = largequeue.get()

    os.system(
        f"kitty +kitten icat --silent /tmp/koneko/{artist_user_id}/{current_page_num}/large/{image_filename}"
    )

    return image_id

def open_image_vp(artist_user_id, filename):
    os.system(
        f"kitty +kitten icat --silent /tmp/koneko/{artist_user_id}/individual/{filename}"
    )


# @timer
def download_large(
    api, current_page_illusts, current_page_num, artist_user_id, number
):  # out_queue
    # TODO: add spinner
    currentImage = current_page_illusts[number]
    image_id = currentImage["id"]
    url = currentImage["image_urls"]["large"]
    filename = url.split("/")[-1]

    large_dir = f"/tmp/koneko/{artist_user_id}/{current_page_num}/large/"
    filepath = f"{large_dir}{filename}"
    make_path_and_download(api, large_dir, url, filename)
    #   if out_queue:
    #       out_queue.put((image_id, filename))
    return image_id, filename, filepath


def make_path_and_download(api, large_dir, url, filename, try_make_dir=True):
    if try_make_dir:
        os.makedirs(large_dir, exist_ok=True)
    if not os.path.isfile(filename):
        with cd(large_dir):
       # old_dir = os.getcwd()
       # os.chdir(large_dir)
            api.download(url)
       # os.chdir(old_dir)


def download_large_vp(api, image_id):
    post_json = api.illust_detail(image_id)['illust']
    url = post_json['image_urls']['large']
    filename = url.split("/")[-1]
    artist_user_id = post_json['user']['id']

    large_dir = f"/tmp/koneko/{artist_user_id}/individual/"
    make_path_and_download(api, large_dir, url, filename)
    return artist_user_id, filename


def get_url_and_filename(url):
    url = re.sub("_p0_master\d+", "_p0", url)
    url = re.sub("c\/\d+x\d+_\d+_\w+\/img-master", "img-original", url)
    filename = url.split("/")[-1]
    return url, filename


def download_full_core(api, url):
    url, filename = get_url_and_filename(url)
    make_path_and_download(
        api,
        f"{os.path.expanduser('~')}/Downloads/",
        url,
        filename,
        try_make_dir=False
    )
    return filename


def download_full(api, **kwargs):
    if ("current_page_illusts" and "number") in kwargs.keys():
        currentImage = kwargs['current_page_illusts'][kwargs['number']]
        url = currentImage["image_urls"]["large"]
    elif "image_id" in kwargs.keys():
        current_image = api.illust_detail(kwargs['image_id'])
        url = current_image['illust']['image_urls']['large']

    filename = download_full_core(api, url)
    return f"/home/twenty/Downloads/{filename}" # Filepath


# TODO: consider refactoring (extracting core away) with download_illusts()
def download_multi(api, artist_user_id, image_id, page_urls):
    list_of_names = []
    download_path = f"/tmp/koneko/{artist_user_id}/individual/{image_id}/"
    os.makedirs(download_path, exist_ok=True)
    with cd(download_path):
        for i in range(len(page_urls)):
            url = page_urls[i]
            img_name = url.split("/")[-1]
            list_of_names.append(img_name)
            #img_ext = img_name.split(".")[-1]

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
    page_urls = kwargs['page_urls']
    current_page_num = kwargs['current_page_num']
    number_of_pages = kwargs['number_of_pages']

    while True:
        image_prompt_command = input("Enter an image view command: ")
        if image_prompt_command == "b":
            artist_illusts_mode(api, artist_user_id)
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
            if current_page_num+1 == number_of_pages:
                print("This is the last image in the post!")
            else:
                current_page_num += 1 # Be careful of 0 index
                # TODO: download first pic, display, then
                # download the rest in the background
                list_of_names = download_multi(api, artist_user_id, image_id, page_urls)
                open_image_vp(artist_user_id,
                        f"{image_id}/{list_of_names[current_page_num]}")
                print(f"Page {current_page_num+1}/{number_of_pages}")

        elif image_prompt_command == "p":
            if not page_urls:
                print("This is the only page in the post!")
                continue
            if current_page_num == 0:
                print("This is the first image in the post!")
            else:
                current_page_num -= 1
                open_image_vp(artist_user_id,
                        f"{image_id}/{list_of_names[current_page_num]}")
                print(f"Page {current_page_num+1}/{number_of_pages}")

        elif image_prompt_command == "h":
            print(image_prompt.__doc__)
        else:
            print("Invalid command")
            print(image_prompt.__doc__)


def gallery_prompt(
    api, current_page_illusts, current_page, current_page_num, artist_user_id, urls
):
    # TODO: artist_user_id is only used to pass to other functions
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
            filepath = download_full(
                            api,
                            current_page_illusts=current_page_illusts,
                            number=int(gallery_command[1:])
                        )
            print(f"Image downloaded at {filepath}\n")

        elif gallery_command == "n":
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
                matched = re.findall("\&offset=\d+", next_url)[0]
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
                image_id = open_image(
                    api,
                    current_page_illusts,
                    artist_user_id,
                    int(gallery_command),
                    current_page_num,
                )

                image_prompt(api, image_id, artist_user_id)
            except ValueError:
                print("Invalid command")
                print(gallery_prompt.__doc__)


def artist_illusts_mode(api, artist_user_id):
    # TODO: both params are only used to pass to other functions
    current_page = api.user_illusts(artist_user_id)
    current_page_illusts = current_page["illusts"]
    current_page_num = 1

    urls, download_path = download_illusts(
        api, current_page_illusts, current_page_num, artist_user_id
    )
    show_artist_illusts(download_path)
    gallery_prompt(
        api,
        current_page_illusts,
        current_page,
        current_page_num,
        artist_user_id,
        urls,
    )


def view_post_mode(api, image_id):
    # TODO: both params are only used to pass to other functions
    artist_user_id, filename = download_large_vp(api, image_id)
    open_image_vp(artist_user_id, filename)

    illust_details = api.illust_detail(image_id)
    number_of_pages = illust_details.illust.page_count
    if number_of_pages > 1:
        print(f"Page 1/{number_of_pages}")
        list_of_pages = illust_details.illust.meta_pages
        page_urls = [list_of_pages[i].image_urls.medium for i in range(number_of_pages)]
    else:
        page_urls = None

    image_prompt(api, image_id, artist_user_id,
            page_urls=page_urls, current_page_num=0,
            number_of_pages=number_of_pages)
    artist_illusts_mode(api, artist_user_id)


def main():
    apiQueue = queue.Queue()
    apiThread = threading.Thread(target=setup, args=(apiQueue,))
    apiThread.start()  # Start logging in

    # During this part, the API can still be logging in but we can proceed
    # TODO: put a cute anime girl here with icat
    os.system("clear")
    main_command = begin_prompt()

    if main_command == "1":
        artist_user_id = artist_user_id_prompt()
        if "pixiv" in artist_user_id:
            artist_user_id = artist_user_id.split("/")[-1]

        # TODO: add spinner
        apiThread.join()  # Wait for api to finish
        api = apiQueue.get()  # Assign api to PixivAPI object

        artist_illusts_mode(api, artist_user_id)

    elif main_command == "2":
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

