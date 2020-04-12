#!/usr/bin/env python3
"""
Browse pixiv in the terminal using kitty's icat to display images (in the
terminal!)

Requires [kitty](https://github.com/kovidgoyal/kitty) on Linux. It uses the
magical `kitty +kitten icat` 'kitten' to display images.

Capitalized tag definitions:
    TODO: to-do, high priority
    SPEED: speed things up, high priority
    FEATURE: extra feature, low priority
    BLOCKING: this is blocking the prompt but I'm stuck on how to proceed
"""

import os
import re
import sys
import time
import queue
import threading
from abc import ABC, abstractmethod
from configparser import ConfigParser
from concurrent.futures import ThreadPoolExecutor

import funcy
from tqdm import tqdm
from blessed import Terminal
from pixivpy3 import AppPixivAPI, PixivError

import pure
import utils
import lscat


# - API FUNCTIONS ======================================================
def setup(out_queue, credentials):
    """
    Logins to pixiv in the background, using credentials from config file.

    Parameters
    ----------
    out_queue : queue.Queue()
        queue for storing logged-in API object. Needed for threading
    """
    global API
    API = AppPixivAPI()
    API.login(credentials["Username"], credentials["Password"])
    out_queue.put(API)


# - Uses web requests, impure
@pure.spinner("Fetching user illustrations... ")
def user_illusts_spinner(artist_user_id):
    # There's a delay here
    # Threading won't do anything meaningful here...
    # SPEED: Caching it (in non volatile storage) might work
    return API.user_illusts(artist_user_id)


@funcy.retry(tries=3, errors=(ConnectionError, PixivError))
def protected_illust_detail(image_id):
    return API.illust_detail(image_id)


@pure.spinner("Getting full image details... ")
def full_img_details(png=False, post_json=None, image_id=None):
    """
    All in one function that gets the full-resolution url, filename, and
    filepath of given image id. Or it can get the id given the post json
    """
    if image_id and not post_json:
        current_image = protected_illust_detail(image_id)

        post_json = current_image.illust

    url = pure.change_url_to_full(post_json=post_json, png=png)
    filename = pure.split_backslash_last(url)
    filepath = pure.generate_filepath(filename)
    return url, filename, filepath

# - API FUNCTIONS ======================================================



# - DOWNLOAD FUNCTIONS ==================================================
# - Core download functions (for async)
@pure.spinner("")
def async_download_spinner(
    download_path, urls, rename_images=False, file_names=None, pbar=None
):
    async_download_core(
        download_path,
        urls,
        rename_images=rename_images,
        file_names=file_names,
        pbar=pbar,
    )


def async_download_core(
    download_path, urls, rename_images=False, file_names=None, pbar=None
):
    """
    Core logic for async downloading. Rename files with given new name
    if needed. Submit each url to the ThreadPoolExecutor.
    """
    oldnames = list(map(pure.split_backslash_last, urls))
    if rename_images:
        newnames = map(pure.prefix_filename, oldnames, file_names, range(len(urls)))
        newnames = list(newnames)
    else:
        newnames = oldnames

    os.makedirs(download_path, exist_ok=True)
    with pure.cd(download_path):
        with ThreadPoolExecutor(max_workers=len(urls)) as executor:
            for (i, name) in enumerate(newnames):
                if not os.path.isfile(name):
                    executor.submit(
                        downloadr, urls[i], oldnames[i], newnames[i], pbar=pbar
                    )


@funcy.retry(tries=3, errors=(ConnectionError, PixivError))
def protected_download(url):
    API.download(url)


def downloadr(url, img_name, new_file_name=None, pbar=None):
    """Actually downloads one pic given the single url, rename if needed."""
    protected_download(url)

    if pbar:
        pbar.update(1)
    # print(f"{img_name} done!")
    if new_file_name:
        os.rename(img_name, new_file_name)  # FIXME Sometimes it misses a file?!


# - Wrappers around the core functions for async download
def download_page(current_page_illusts, current_page_num, artist_user_id, pbar=None):
    """
    Download the illustrations on one page of given artist id (using threads),
    rename them based on the post title

    Parameters
    ----------
    current_page_illusts : JsonDict
        JsonDict holding lots of info on all the posts in the current page
    current_page_num : int
        Page as in artist illustration profile pages. Starts from 1
    artist_user_id : int
    """
    urls = pure.medium_urls(current_page_illusts)
    titles = pure.post_titles_in_page(current_page_illusts)
    download_path = f"{KONEKODIR}/{artist_user_id}/{current_page_num}/"

    async_download_core(
        download_path, urls, rename_images=True, file_names=titles, pbar=pbar
    )


# - Wrappers around the core functions for downloading one image
@pure.spinner("")
def download_core(large_dir, url, filename, try_make_dir=True):
    """Downloads one url, intended for single images only"""
    if try_make_dir:
        os.makedirs(large_dir, exist_ok=True)
    if not os.path.isfile(filename):
        print("   Downloading illustration...", flush=True, end="\r")
        with pure.cd(large_dir):
            downloadr(url, filename, None)


def download_image_verified(image_id=None, post_json=None, png=False, **kwargs):
    """
    This downloads an image, checks if it's valid. If not, retry with png.
    """
    if not kwargs:
        url, filename, filepath = full_img_details(
            image_id=image_id, post_json=post_json, png=png
        )
    else:
        url = kwargs["url"]
        filename = kwargs["filename"]
        filepath = kwargs["filepath"]

    homepath = os.path.expanduser("~")
    download_path = f"{homepath}/Downloads/"
    download_core(download_path, url, filename, try_make_dir=False)

    verified = utils.verify_full_download(filepath)
    if not verified:
        download_image_verified(image_id=image_id, png=True)
    print(f"Image downloaded at {filepath}\n")


# - Functions that are wrappers around download functions, making them impure
class LastPageException(ValueError):
    pass


# @pure.spinner("")  # No message because it conflicts with download_page()
def prefetch_next_page(current_page_num, artist_user_id, all_pages_cache):
    """
    current_page_num : int
        It is the CURRENT page number, before incrementing
    """
    # print("   Prefetching next page...", flush=True, end="\r")
    next_url = all_pages_cache[str(current_page_num)]["next_url"]
    if not next_url:  # this is the last page
        raise LastPageException

    parse_page = API.user_illusts(**API.parse_qs(next_url))
    all_pages_cache[str(current_page_num + 1)] = parse_page
    current_page_illusts = parse_page["illusts"]

    download_path = f"{KONEKODIR}/{artist_user_id}/{current_page_num+1}/"
    if not os.path.isdir(download_path):
        pbar = tqdm(total=len(current_page_illusts), smoothing=0)
        download_page(
            current_page_illusts, current_page_num + 1, artist_user_id, pbar=pbar
        )
        pbar.close
    return all_pages_cache


def go_next_image(
    page_urls, img_post_page_num, number_of_pages, downloaded_images, download_path,
):
    """
    Intended to be from image_prompt, for posts with multiple images.
    Downloads next image it not downloaded, open it, download the next image
    in the background

    Parameters
    img_post_page_num : int
        **Starts from 0**. Page number of the multi-image post.
    """
    # IDEAL: image prompt should not be blocked while downloading
    # But I think delaying the prompt is better than waiting for an image
    # to download when you load it

    # First time from gallery; download next image
    if img_post_page_num == 1:
        url = page_urls[img_post_page_num]
        downloaded_images = list(map(pure.split_backslash_last, page_urls[:2]))
        async_download_spinner(download_path, [url])

    utils.display_image_vp(f"{download_path}{downloaded_images[img_post_page_num]}")

    # Downloads the next image
    try:
        next_img_url = page_urls[img_post_page_num + 1]
    except IndexError:
        pass  # Last page
    else:  # No error
        downloaded_images.append(pure.split_backslash_last(next_img_url))
        async_download_spinner(download_path, [next_img_url])
    print(f"Page {img_post_page_num+1}/{number_of_pages}")

    return downloaded_images


def display_image(post_json, artist_user_id, number_prefix, current_page_num):
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
        f"kitty +kitten icat --silent {KONEKODIR}/{artist_user_id}/{current_page_num}/{search_string}*"
    )

    url = pure.url_given_size(post_json, "large")
    filename = pure.split_backslash_last(url)
    large_dir = f"{KONEKODIR}/{artist_user_id}/{current_page_num}/large/"
    download_core(large_dir, url, filename)

    # BLOCKING: imput is blocking, will not display large image until input
    # received

    os.system("clear")
    os.system(
        f"kitty +kitten icat --silent {KONEKODIR}/{artist_user_id}/{current_page_num}/large/{filename}"
    )

# - DOWNLOAD FUNCTIONS ==================================================



# - Interactive functions (frontend)
def quit():
    with term.cbreak():
        while True:
            ans = term.inkey()
            if ans == "y" or ans == "q" or ans.code == 343:  # Enter
                sys.exit(0)
            elif ans:
                break


class Image:
    """
    Image view commands (No need to press enter):
        b -- go back to the gallery
        n -- view next image in post (only for posts with multiple pages)
        p -- view previous image in post (same as above)
        d -- download this image
        o -- open pixiv post in browser
        h -- show this help

        q -- quit (with confirmation)

    """
    # fmt: off
    def __init__(
        self,
        image_id,
        artist_user_id,
        current_page=None,
        current_page_num=1,
        **kwargs
    ):
    # fmt: on
        self.image_id = image_id
        self.artist_user_id = artist_user_id
        self.current_page = current_page
        self.current_page_num = current_page_num

        if kwargs:  # Posts with multiple pages
            self.page_urls = kwargs["page_urls"]
            self.img_post_page_num = kwargs["img_post_page_num"]
            self.number_of_pages = kwargs["number_of_pages"]
            self.downloaded_images = kwargs["downloaded_images"]
        self.kwargs = kwargs  # Make it accessible to the methods

    def open_image(self):
        link = f"https://www.pixiv.net/artworks/{self.image_id}"
        os.system(f"xdg-open {link}")
        print(f"Opened {link} in browser")

    def download_image(self, png=False):
        current_url = self.page_urls[self.img_post_page_num]
        # Need to work on multi-image posts
        # Doing the same job as full_img_details
        large_url = pure.change_url_to_full(url=current_url)
        filename = pure.split_backslash_last(large_url)
        filepath = pure.generate_filepath(filename)
        download_image_verified(url=large_url, filename=filename, filepath=filepath)

    def next_image(self):
        if not self.page_urls:
            print("This is the only page in the post!")
        elif self.img_post_page_num + 1 == self.number_of_pages:
            print("This is the last image in the post!")

        else:
            self.img_post_page_num += 1  # Be careful of 0 index
            self.downloaded_images = go_next_image(
                self.page_urls,
                self.img_post_page_num,
                self.number_of_pages,
                self.downloaded_images,
                download_path=self.kwargs["download_path"],
            )

    def previous_image(self):
        if not self.page_urls:
            print("This is the only page in the post!")
        elif self.img_post_page_num == 0:
            print("This is the first image in the post!")
        else:
            download_path = self.kwargs["download_path"]
            self.img_post_page_num -= 1
            image_filename = self.downloaded_images[self.img_post_page_num]
            utils.display_image_vp(f"{download_path}{image_filename}")
            print(f"Page {self.img_post_page_num+1}/{self.number_of_pages}")

    def leave(self):
        if self.current_page_num > 1 or self.current_page:
            self.all_pages_cache = self.kwargs["all_pages_cache"]
            show_gallery(
                self.artist_user_id,
                self.current_page_num,
                self.current_page,
                all_pages_cache=self.all_pages_cache,
            )
        else:
            # Came from view post mode, don't know current page num
            # Defaults to page 1
            artist_illusts_mode(self.artist_user_id)


# - Prompt functions with logic
def image_prompt(image):
    """
    if-else statements to intercept key presses and do the correct action
    current_page and current_page_num is for gallery view -> next page(s) ->
    image prompt -> back
    kwargs are to store info for posts with multiple pages/images
    """
    case = {
        "o": image.open_image,
        "d": image.download_image,
        "n": image.next_image,
        "p": image.previous_image,
    }

    with term.cbreak():
        while True:
            print("Enter an image view command:")
            image_prompt_command = term.inkey()

            # Simplify if-else chain with case-switch
            func = case.get(image_prompt_command, None)
            if func:
                func()

            elif image_prompt_command == "h":
                print(image.__doc__)

            elif image_prompt_command == "q":
                print("Are you sure you want to exit?")
                quit()

            elif image_prompt_command == "b":
                break  # Leave cbreak()

            elif image_prompt_command == "":
                pass

            elif image_prompt_command:
                print("Invalid command! Press h to show help")

            # End if
        # End while
    # End cbreak()

    # image_prompt_command == "b"
    image.leave()


class Gallery:
    """
    Gallery commands: (No need to press enter)
        Using coordinates, where {digit1} is the row and {digit2} is the column
        {digit1}{digit2}   -- display the image on row digit1 and column digit2
        o{digit1}{digit2}  -- open pixiv image/post in browser
        d{digit1}{digit2}  -- download image in large resolution

    Using image number, where {number} is the nth image in order (see examples)
        i{number}          -- display the image
        O{number}          -- open pixiv image/post in browser.
        D{number}          -- download image in large resolution.

        n                  -- view the next page
        p                  -- view the previous page
        h                  -- show this help
        q                  -- quit (with confirmation)

    Examples:
        i09   --->  Display the ninth image in image view (must have leading 0)
        i10   --->  Display the tenth image in image view
        O9    --->  Open the ninth image's post in browser
        D9    --->  Download the ninth image, in large resolution

        25    --->  Display the image on column 2, row 5 (index starts at 1)
        d25   --->  Open the image on column 2, row 5 (index starts at 1) in browser
        o25   --->  Download the image on column 2, row 5 (index starts at 1)

    """

    def __init__(
        self,
        current_page_illusts,
        current_page,
        current_page_num,
        artist_user_id,
        all_pages_cache,
    ):
        self.current_page_illusts = current_page_illusts
        self.current_page = current_page
        self.current_page_num = current_page_num
        self.artist_user_id = artist_user_id
        self.all_pages_cache = all_pages_cache

        pure.print_multiple_imgs(self.current_page_illusts)
        print(f"Page {self.current_page_num}")
        # Fixes: Gallery -> next page -> image prompt -> back -> prev page
        # Gallery -> Image -> back still retains all_pages_cache, no need to
        # prefetch again
        if len(self.all_pages_cache) == 1:
            # Prefetch the next page on first gallery load
            with funcy.suppress(LastPageException):
                self.all_pages_cache = prefetch_next_page(
                    self.current_page_num, self.artist_user_id, self.all_pages_cache
                )

        else:
            # Gallery -> next -> image prompt -> back
            self.all_pages_cache[str(self.current_page_num)] = self.current_page


    def download_image_coords(self, first_num, second_num):
        selected_image_num = pure.find_number_map(int(first_num), int(second_num))
        if not selected_user_num:
            print("Invalid number!")
        else:
            self.download_image_num(selected_image_num)

    def open_link_coords(self, first_num, second_num):
        selected_image_num = pure.find_number_map(int(first_num), int(second_num))
        if not selected_user_num:
            print("Invalid number!")
        else:
            self.open_link_num(selected_image_num)

    def open_link_num(self, number):
        # Update current_page_illusts, in case if you're in another page
        self.current_page = self.all_pages_cache[str(self.current_page_num)]
        self.current_page_illusts = self.current_page["illusts"]
        image_id = self.current_page_illusts[number]["id"]
        link = f"https://www.pixiv.net/artworks/{image_id}"
        os.system(f"xdg-open {link}")
        print(f"Opened {link}!\n")

    def download_image_num(self, number, png=False):
        # Update current_page_illusts, in case if you're in another page
        self.current_page = self.all_pages_cache[str(self.current_page_num)]
        self.current_page_illusts = self.current_page["illusts"]
        post_json = self.current_page_illusts[number]
        download_image_verified(post_json=post_json)

    def view_image(self, selected_image_num):
        self.current_page = self.all_pages_cache[str(self.current_page_num)]
        self.current_page_illusts = self.current_page["illusts"]
        post_json = self.current_page_illusts[selected_image_num]
        image_id = post_json.id

        display_image(
            post_json, self.artist_user_id, selected_image_num, self.current_page_num
        )

        # blocking: no way to unblock prompt
        number_of_pages, page_urls = pure.page_urls_in_post(post_json, "large")

        image = Image(
            image_id,
            self.artist_user_id,
            current_page_num=self.current_page_num,
            current_page=self.current_page,
            page_urls=page_urls,
            img_post_page_num=0,
            number_of_pages=number_of_pages,
            downloaded_images=None,
            all_pages_cache=self.all_pages_cache,
            download_path=f"{KONEKODIR}/{self.artist_user_id}/{self.current_page_num}/large/",
        )
        image_prompt(image)

    def next_page(self):
        download_path = f"{KONEKODIR}/{self.artist_user_id}/{self.current_page_num+1}/"
        try:
            utils.show_artist_illusts(download_path)
        except FileNotFoundError:
            print("This is the last page!")
        else:
            self.current_page_num += 1
            print(f"Page {self.current_page_num}")
            print("Enter a gallery command:\n")

        # Skip prefetching again for cases like next -> prev -> next
        if str(self.current_page_num + 1) not in self.all_pages_cache.keys():
            try:
                # After showing gallery, pre-fetch the next page
                self.all_pages_cache = prefetch_next_page(
                    self.current_page_num, self.artist_user_id, self.all_pages_cache
                )
            except LastPageException:
                print("This is the last page!")

    def previous_page(self):
        if self.current_page_num > 1:
            self.current_page = self.all_pages_cache[str(self.current_page_num - 1)]
            self.current_page_illusts = self.current_page["illusts"]
            self.current_page_num -= 1

            download_path = (
                f"{KONEKODIR}/{self.artist_user_id}/{self.current_page_num}/"
            )
            utils.show_artist_illusts(download_path)
            print(f"Page {self.current_page_num}")
            print("Enter a gallery command:\n")

        else:
            print("This is the first page!")


def gallery_prompt(gallery):
    """
    Only contains logic for interpreting key presses, and do the correct action
    Sequence means a combination of more than one key.
    When a sequenceable key is pressed, wait for the next keys in the sequence
        If the sequence is valid, execute their corresponding actions
    Otherwise for keys that do not need a sequence, execute their actions normally
    """
    sequenceable_keys = ("o", "d", "i", "O", "D")
    with term.cbreak():
        keyseqs = []
        seq_num = 0
        print("Enter a gallery command:")
        while True:
            gallery_command = term.inkey()

            # Wait for the rest of the sequence
            if gallery_command in sequenceable_keys:
                keyseqs.append(gallery_command)
                print(keyseqs)
                print(term.move_up(1) + term.move_right(1))
                seq_num += 1

            elif gallery_command.code == 361:  # Escape
                keyseqs = []
                seq_num = 0
                print(keyseqs)

            # Digits continue the sequence
            elif gallery_command.isdigit():
                keyseqs.append(gallery_command)
                print(keyseqs)

                # End of the sequence...
                # Two digit sequence -- view image given coords
                if seq_num == 1 and keyseqs[0].isdigit() and keyseqs[1].isdigit():

                    first_num = int(keyseqs[0])
                    second_num = int(keyseqs[1])
                    selected_image_num = pure.find_number_map(first_num, second_num)

                    break  # leave cbreak(), go to image prompt

                # One letter two digit sequence
                elif seq_num == 2 and keyseqs[1].isdigit() and keyseqs[2].isdigit():

                    first_num = keyseqs[1]
                    second_num = keyseqs[2]

                    # Open or download given coords
                    if keyseqs[0] == "o":
                        gallery.open_link_coords(first_num, second_num)

                    elif keyseqs[0] == "d":
                        gallery.download_image_coords(first_num, second_num)

                    # Open, download, or view image, given image number
                    selected_image_num = int(f"{first_num}{second_num}")

                    if keyseqs[0] == "O":
                        gallery.open_link_num(selected_image_num)
                    elif keyseqs[0] == "D":
                        gallery.download_image_num(selected_image_num)
                    elif keyseqs[0] == "i":
                        break  # leave cbreak(), go to image prompt

                    # Reset sequence info after running everything
                    keyseqs = []
                    seq_num = 0

                # Not the end of the sequence yet, continue while block
                else:
                    seq_num += 1

            # No sequence, execute their functions immediately
            elif gallery_command == "n":
                gallery.next_page()

            elif gallery_command == "p":
                gallery.previous_page()

            elif gallery_command == "q":
                print("Are you sure you want to exit?")
                quit()
                # If exit cancelled
                print("Enter a gallery command:")

            elif gallery_command.code == 343:  # Enter
                pass
            elif gallery_command == "h":
                print(gallery.__doc__)
            elif gallery_command:
                print("Invalid command! Press h to show help")
                keyseqs = []
                seq_num = 0
            # End if
        # End while
    # End cbreak()

    # Display image (using either coords or image number), the show this prompt
    gallery.view_image(selected_image_num)


class Users(ABC):
    """
    User view commands (No need to press enter):
        n -- view next page
        p -- view previous page
        h -- show this help
        q -- quit (with confirmation)

    """

    @abstractmethod
    def __init__(self, user_or_id):
        self.input = user_or_id
        self.offset = 0
        self.page_num = 1
        self.download_path = f"{self.main_path}/{self.input}/{self.page_num}"
        self.names_cache = {}
        self.ids_cache = {}

        # TODO: if dir exists, show page first then parse
        self.parse_and_download()
        self.show_page()
        self.prefetch_next_page()

    def parse_and_download(self):
        """
        Parse info, combine profile pics and previews, download all concurrently,
        move the profile pics to the correct dir (less files to move)
        """
        self.parse_user_infos()
        preview_path = f"{self.main_path}/{self.input}/{self.page_num}/previews/"
        all_urls = self.profile_pic_urls + self.image_urls
        all_names = self.names + list(map(pure.split_backslash_last, self.image_urls))
        splitpoint = len(self.profile_pic_urls)

        pbar = tqdm(total=len(all_urls), smoothing=0)
        # fmt: off
        async_download_core(
            preview_path,
            all_urls,
            rename_images=True,
            file_names=all_names,
            pbar=pbar
        )
        pbar.close()
        # fmt: on

        # Move artist profile pics to their correct dir
        to_move = sorted(os.listdir(preview_path))[:splitpoint]
        with pure.cd(self.download_path):
            for pic in to_move:
                os.rename(f"{self.download_path}/previews/{pic}",
                            f"{self.download_path}/{pic}")


    @abstractmethod
    @funcy.retry(tries=3, errors=(ConnectionError, PixivError))
    def pixivrequest(self):
        """Blank method, classes that inherit this ABC must override this"""
        raise NotImplementedError

    @pure.spinner('Parsing info...')
    def parse_user_infos(self):
        """Parse json and get list of artist names, profile pic urls, and id"""
        result = self.pixivrequest()
        page = result["user_previews"]
        self.next_url = result["next_url"]

        self.ids = list(map(self.user_id, page))
        self.ids_cache.update({self.page_num: self.ids})

        self.names = list(map(self.user_name, page))
        self.names_cache.update({self.page_num: self.names})

        self.profile_pic_urls = list(map(self.user_profile_pic, page))

        # max(i) == number of artists on this page
        # max(j) == 3 == 3 previews for every artist
        self.image_urls = [page[i]['illusts'][j]['image_urls']['square_medium']
                            for i in range(len(page))
                            for j in range(len(page[i]['illusts']))]


    def show_page(self):
        names = self.names_cache[self.page_num]
        names_prefixed = list(map(
            pure.prefix_artist_name,
            names,
            range(len(names))
        ))

        try:
            lscat.Card(
                self.download_path,
                f"{self.main_path}/{self.input}/{self.page_num}/previews/",
                messages=names_prefixed,
            )
        except FileNotFoundError:
            print("This is the last page!")
            self.page_num -= 1
            self.download_path = f"{self.main_path}/{self.input}/{self.page_num}"

    def prefetch_next_page(self):
        self.page_num += 1
        self.download_path = f"{self.main_path}/{self.input}/{self.page_num}"

        if self.next_url:
            self.offset = API.parse_qs(self.next_url)["offset"]
            self.parse_and_download()
        self.page_num -= 1
        self.download_path = f"{self.main_path}/{self.input}/{self.page_num}"

    def next_page(self):
        self.page_num += 1
        self.download_path = f"{self.main_path}/{self.input}/{self.page_num}"
        self.show_page()

        self.prefetch_next_page()

    def previous_page(self):
        if self.page_num > 1:
            self.page_num -= 1
            self.download_path = f"{self.main_path}/{self.input}/{self.page_num}"
            self.show_page()
        else:
            print("This is the first page!")

    def go_artist_mode(self, selected_user_num):
        current_page_ids = self.ids_cache[self.page_num]
        try:
            artist_user_id = current_page_ids[selected_user_num]
        except IndexError:
            print("Invalid number!")
        artist_illusts_mode(artist_user_id)

    @staticmethod
    def user_id(json):
        return json["user"]["id"]

    @staticmethod
    def user_name(json):
        return json["user"]["name"]

    @staticmethod
    def user_profile_pic(json):
        return json["user"]["profile_image_urls"]["medium"]

    @staticmethod
    def image_urls(illusts_json):
        """page[i]['illusts'][j]['image_urls']['medium']"""
        return illusts_json['image_urls']['medium']


class SearchUsers(Users):
    """
    Inherits from Users class, define self.input as the search string (user)
    Parent directory for downloads should go to search/
    Note that pixivpy3 does not have search_user() yet (not released yet);
    you need to install the master branch (which should be done if you used
    the requirements.txt)
    """
    def __init__(self, user):
        self.main_path = f"{KONEKODIR}/search"
        super().__init__(user)

    def pixivrequest(self):
        return API.search_user(self.input, offset=self.offset)


class FollowingUsers(Users):
    """
    Inherits from Users class, define self.input as the user's pixiv ID
    (Or any other pixiv ID that the user wants to look at their following users)
    Parent directory for downloads should go to following/
    """
    def __init__(self, your_id, publicity='private'):
        self.publicity = publicity
        self.main_path = f"{KONEKODIR}/following"
        super().__init__(your_id)

    def pixivrequest(self):
        return API.user_following(
            self.input, restrict=self.publicity, offset=self.offset
        )


def user_prompt(user_class):
    """
    Handles key presses for user views (following users and user search)
    """
    keyseqs = []
    seq_num = 0
    sequenceable_keys = "i"
    with term.cbreak():
        while True:
            print("Enter a user view command:")
            user_prompt_command = term.inkey()

            if user_prompt_command == "n":
                user_class.next_page()
                # Prevents catching "n" and messing up the cache
                time.sleep(0.5)

            elif user_prompt_command == "p":
                user_class.previous_page()

            # Wait for the rest of the sequence
            elif user_prompt_command in sequenceable_keys:
                keyseqs.append(user_prompt_command)
                print(keyseqs)
                seq_num += 1

            elif user_prompt_command.isdigit():
                keyseqs.append(user_prompt_command)
                print(keyseqs)

                # End of the sequence...
                # Two digit sequence -- view artist given number
                if seq_num == 1 and keyseqs[0].isdigit() and keyseqs[1].isdigit():

                    first_num = keyseqs[0]
                    second_num = keyseqs[1]
                    selected_user_num = int(f"{first_num}{second_num}")
                    break  # leave cbreak(), go to gallery

                # Not the end of the sequence yet, continue while block
                else:
                    seq_num += 1

            elif user_prompt_command == "q":
                print("Are you sure you want to exit?")
                quit()

            elif user_prompt_command == "":
                pass
            elif user_prompt_command == "h":
                print(Users.__doc__)
            elif user_prompt_command:
                print("Invalid command! Press h to show help")
                keyseqs = []
                seq_num = 0
            # End if
        # End while
    # End cbreak()

    user_class.go_artist_mode(selected_user_num)
# - End interactive (frontend) functions


# - Mode and loop functions (some interactive and some not)
def show_gallery(
    artist_user_id, current_page_num, current_page, show=True, all_pages_cache=None
):
    """
    Downloads images, show if requested, instantiate all_pages_cache, prompt.
    """
    download_path = f"{KONEKODIR}/{artist_user_id}/{current_page_num}/"
    current_page_illusts = current_page["illusts"]

    if not os.path.isdir(download_path):
        pbar = tqdm(total=len(current_page_illusts), smoothing=0)
        download_page(current_page_illusts, current_page_num, artist_user_id, pbar=pbar)
        pbar.close()

    if show:
        utils.show_artist_illusts(download_path)

    if not all_pages_cache:
        all_pages_cache = {"1": current_page}

    # Instantiate a gallery class
    gallery = Gallery(
        current_page_illusts,
        current_page,
        current_page_num,
        artist_user_id,
        all_pages_cache,
    )
    gallery_prompt(gallery)


def artist_illusts_mode(artist_user_id, current_page_num=1):
    """
    If artist_user_id dir exists, show immediately (without checking
    for contents!)
    Else, fetch current_page json and proceed download -> show -> prompt
    """
    download_path = f"{KONEKODIR}/{artist_user_id}/{current_page_num}/"
    # If path exists, show immediately (without checking for contents!)
    if os.path.isdir(download_path):
        utils.show_artist_illusts(download_path)
        show = False
    else:
        show = True

    current_page = user_illusts_spinner(artist_user_id)
    show_gallery(artist_user_id, current_page_num, current_page, show=show)


def view_post_mode(image_id):
    """
    Fetch all the illust info, download it in the correct directory, then display it.
    If it is a multi-image post, download the next image
    Else or otherwise, open image prompt
    """
    print("Fetching illust details...")
    try:
        post_json = API.illust_detail(image_id)["illust"]
    except KeyError:
        print("Work has been deleted or the ID does not exist!")
        sys.exit(1)

    url = pure.url_given_size(post_json, "large")
    filename = pure.split_backslash_last(url)
    artist_user_id = post_json["user"]["id"]

    # If it's a multi-image post, download the first pic in individual/{image_id}
    # So it won't be duplicated later
    number_of_pages, page_urls = pure.page_urls_in_post(post_json, "large")
    if number_of_pages == 1:
        large_dir = f"{KONEKODIR}/{artist_user_id}/individual/"
        downloaded_images = None
    else:
        large_dir = f"{KONEKODIR}/{artist_user_id}/individual/{image_id}/"

    download_core(large_dir, url, filename)
    utils.display_image_vp(f"{large_dir}{filename}")

    # Download the next page for multi-image posts
    if number_of_pages != 1:
        async_download_spinner(large_dir, page_urls[:2])
        downloaded_images = list(map(pure.split_backslash_last, page_urls[:2]))

    image = Image(
        image_id,
        artist_user_id,
        page_urls=page_urls,
        img_post_page_num=0,
        number_of_pages=number_of_pages,
        downloaded_images=downloaded_images,
        download_path=large_dir,
    )
    image_prompt(image)
    # Will only be used for multi-image posts, so it's safe to use large_dir
    # Without checking for number_of_pages
    # artist_illusts_mode(artist_user_id)

#- Loop classes ==========================================================
class Loop(ABC):
    def __init__(self, prompted, user_input):
        self.prompted = prompted
        self.user_input = user_input

        while True:
            if self.prompted and not self.user_input:
                self.prompt_url_id()
                os.system("clear")

                self.process_url_or_input()
                self.validate_input()

            API_THREAD.join()  # Wait for API to finish
            global API
            API = API_QUEUE.get()  # Assign API to PixivAPI object

            self.go_to_mode()

    @abstractmethod
    def prompt_url_id(self):
        raise NotImplementedError

    def process_url_or_input(self):
        if "pixiv" in self.url_or_id:
            self.user_input = pure.split_backslash_last(self.url_or_id)
        else:
            self.user_input = self.url_or_id

    def validate_input(self):
        try:
            int(self.user_input)
        except ValueError:
            print("Invalid image ID!")

    @abstractmethod
    def go_to_mode(self):
        raise NotImplementedError


class ArtistModeLoop(Loop):
    """
    Ask for artist ID and process it, wait for API to finish logging in
    before proceeding
    """
    def prompt_url_id(self):
        self.url_or_id = utils.artist_user_id_prompt()

    def go_to_mode(self):
        artist_illusts_mode(self.user_input)


class ViewPostModeLoop(Loop):
    """
    Ask for post ID and process it, wait for API to finish logging in
    before proceeding
    """
    def prompt_url_id(self):
        self.url_or_id = input("Enter pixiv post url or ID:\n")

    def process_url_or_input(self):
        """Overriding base class to account for 'illust_id' cases"""
        if "illust_id" in self.url_or_id:
            self.user_input = re.findall(r"&illust_id.*", self.url_or_id)[0].split("=")[-1]
        elif "pixiv" in self.url_or_id:
            self.user_input = pure.split_backslash_last(self.url_or_id)
        else:
            self.user_input = self.url_or_id

    def go_to_mode(self):
        view_post_mode(self.user_input)


class SearchUsersModeLoop(Loop):
    """
    Ask for search string and process it, wait for API to finish logging in
    before proceeding
    """
    def prompt_url_id(self):
        self.url_or_id = input("Enter search string:\n")

    def process_url_or_input(self):
        """the 'url or id' name doesn't really apply; accepts all strings"""
        self.user_input = self.url_or_id

    def validate_input(self):
        """Overriding base class: search string doesn't need to be int"""
        pass

    def go_to_mode(self):
        searching = SearchUsers(self.user_input)
        user_prompt(searching)


class FollowingUserModeLoop(Loop):
    """
    Ask for pixiv ID or url and process it, wait for API to finish logging in
    before proceeding
    If user agrees to use the your_id saved in configu, prompt_url_id() will be
    skipped
    """
    def prompt_url_id(self):
        self.url_or_id = input("Enter your pixiv ID or url: ")

    def go_to_mode(self):
        following = FollowingUsers(self.user_input)
        user_prompt(following)
#- Loop classes ==========================================================


def main_loop(prompted, main_command, user_input, your_id=None):
    """
    Ask for mode selection
    user_input : str or int
        For artist_illusts_mode, it is artist_user_id : int
        For view_post_mode, it is image_id : int
        For following users mode, it is your_id : int
        For search users mode, it is search_string : str
    """
    # SPEED: gallery mode - if tmp has artist id and '1' dir,
    # immediately show it without trying to log in or download
    printmessage = True
    while True:
        if prompted and not user_input:
            main_command = utils.begin_prompt(printmessage)

        if main_command == "1":
            ArtistModeLoop(prompted, user_input)

        elif main_command == "2":
            ViewPostModeLoop(prompted, user_input)

        # fmt: off
        elif main_command == "3":
            if your_id: # your_id stored in config file
                ans = input("Do you want to use the Pixiv ID saved in your config?\n")
                if ans in {"y", ""}:
                    FollowingUserModeLoop(prompted, your_id)

            # If your_id not stored, or if ans is no, ask for your_id
            FollowingUserModeLoop(prompted, user_input)

        elif main_command == "4":
            SearchUsersModeLoop(prompted, user_input)

        # fmt: on
        elif main_command == "?":
            utils.info_screen_loop()

        elif main_command == "m":
            utils.show_man_loop()

        elif main_command == "c":
            utils.clear_cache_loop()

        elif main_command == "q":
            answer = input("Are you sure you want to exit? [y/N]:\n")
            if answer == "y" or not answer:
                break
            else:
                printmessage = False
                continue

        else:
            print("\nInvalid command!")
            printmessage = False
            continue


def main():
    # Read config.ini file
    config_object = ConfigParser()
    config_path = os.path.expanduser("~/.config/koneko/")
    config_object.read(f"{config_path}config.ini")
    credentials = config_object["Credentials"]
    # If your_id is stored in the config
    your_id = credentials.get("ID", None)

    # It'll never be changed after logging in
    global API, API_QUEUE, API_THREAD
    API_QUEUE = queue.Queue()
    API_THREAD = threading.Thread(target=setup, args=(API_QUEUE, credentials))
    API_THREAD.start()  # Start logging in

    # During this part, the API can still be logging in but we can proceed
    os.system("clear")
    if len(sys.argv) == 2:
        print("Logging in...")

    # Direct command line arguments, skip utils.begin_prompt()
    if len(sys.argv) == 2:
        prompted = False
        cli_args = sys.argv[1]

        if "users" in cli_args:
            if "\\" in cli_args:
                user_input = pure.split_backslash_last(cli_args).split("\\")[-1][1:]
            else:
                user_input = pure.split_backslash_last(cli_args)
            main_command = "1"

        elif "artworks" in cli_args:
            user_input = pure.split_backslash_last(cli_args).split("\\")[0]
            main_command = "2"

        elif "illust_id" in cli_args:
            user_input = re.findall(r"&illust_id.*", cli_args)[0].split("=")[-1]
            user_input = int(image_id)
            main_command = "2"

        else:  # Mode 4, string to search for artists
            user_input = cli_args
            main_command = "4"

    elif len(sys.argv) == 3:
        if sys.argv[1] == "-f":
            cli_args = sys.argv[2]
            prompted = False

            if "\\" in cli_args:
                user_input = pure.split_backslash_last(cli_args).split("\\")[-1][1:]
            else:
                user_input = pure.split_backslash_last(cli_args)
            main_command = "3"

        else:
            print("Too many arguments!")
            sys.exit(1)

    elif len(sys.argv) > 3:
        print("Too many arguments!")
        sys.exit(1)

    else:  # No cli arguments
        prompted = True
        main_command = None
        user_input = None


    try:
        main_loop(prompted, main_command, user_input, your_id)
    except KeyboardInterrupt:
        print("\n")
        answer = input("Are you sure you want to exit? [y/N]:\n")
        if answer == "y" or not answer:
            sys.exit(0)
        else:
            main()


if __name__ == "__main__":
    global term
    term = Terminal()
    global KONEKODIR
    KONEKODIR = "/tmp/koneko"
    main()
