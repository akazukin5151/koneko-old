#!/usr/bin/env python3
"""Browse pixiv in the terminal using kitty's icat to display images (in the
terminal!)

Usage:
  koneko       [<link> | <searchstr>]
  koneko [1|a] <link_or_id>
  koneko [2|i] <link_or_id>
  koneko (3|f) <link_or_id>
  koneko [4|s] <searchstr>
  koneko [5|n]
  koneko -h

Notes:
*  If you supply a link and want to go to mode 3, you must give the (3|f) argument,
   otherwise your link would default to mode 1.
*  It is assumed you won't need to search for an artist named '5' or 'n' from the
   command line, because it would go to mode 5.

Optional arguments (for specifying a mode):
  1 a  Mode 1 (Artist gallery)
  2 i  Mode 2 (Image view)
  3 f  Mode 3 (Following artists)
  4 s  Mode 4 (Search for artists)
  5 n  Mode 5 (Newest works from following artists ("illust follow"))

Required arguments if a mode is specified:
  <link>        Pixiv url, auto detect mode. Only works for modes 1, 2, and 4
  <link_or_id>  Either pixiv url or artist ID or image ID
  <searchstr>   String to search for artists

Options:
  -h  Show this help
"""
# Capitalized tag definitions:
#     TODO: to-do, high priority
#     SPEED: speed things up, high priority
#     FEATURE: extra feature, low priority
#     BLOCKING: this is blocking the prompt but I'm stuck on how to proceed

import os
import re
import sys
import time
import queue
import itertools
import threading
from pathlib import Path
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor

import funcy
import cytoolz
from tqdm import tqdm
from docopt import docopt
from pixivpy3 import PixivError, AppPixivAPI

from koneko import pure
from koneko import lscat
from koneko import utils
from koneko import prompt
from koneko import colors
from koneko import ui

KONEKODIR = Path("~/.local/share/koneko/cache").expanduser()

def main():
    """Read config file, start login, process any cli arguments, go to main loop"""
    os.system("clear")
    credentials, your_id = utils.config()
    if not Path("~/.local/share/koneko").expanduser().exists():
        print("Please wait, downloading welcome image (this will only occur once)...")
        Path("~/.local/share/koneko/pics").expanduser().mkdir(parents=True)
        os.system("curl -s https://raw.githubusercontent.com/twenty5151/koneko/master/pics/71471144_p0.png -o ~/.local/share/koneko/pics/71471144_p0.png")
        os.system("curl -s https://raw.githubusercontent.com/twenty5151/koneko/master/pics/79494300_p0.png -o ~/.local/share/koneko/pics/79494300_p0.png")
        os.system("clear")

    # It'll never be changed after logging in
    _API = APIHandler(credentials)
    _API.start()

    # During this part, the API can still be logging in but we can proceed
    args = docopt(__doc__)
    if len(sys.argv) > 1:
        print("Logging in...")
        prompted = False
    else:  # No cli arguments
        prompted = True
        main_command = None
        user_input = None

    # Direct command line arguments
    if url_or_str := args['<link>']:
        # Link given, no mode specified
        if "users" in url_or_str:
            user_input, main_command = pure.process_user_url(url_or_str)

        elif "artworks" in url_or_str or "illust_id" in url_or_str:
            user_input, main_command = pure.process_artwork_url(url_or_str)

        # Assume you won't search for '5' or 'n'
        elif url_or_str == "5" or url_or_str == "n":
            main_command = "5"
            user_input = None

        else:  # Mode 4, string to search for artists
            user_input = url_or_str
            main_command = "4"

    elif url_or_id := args['<link_or_id>']:
        # Mode specified, argument can be link or id
        if args['1'] or args['a']:
            user_input, main_command = pure.process_user_url(url_or_id)

        elif args['2'] or args['i']:
            user_input, main_command = pure.process_artwork_url(url_or_id)

        elif args['3'] or args['f']:
            user_input, main_command = pure.process_user_url(url_or_id)
            main_command = "3"

    elif user_input := args['<searchstr>']:
        main_command = "4"

    try:
        main_loop(_API, prompted, main_command, user_input, your_id)
    except KeyboardInterrupt:
        main()

def main_loop(_API, prompted, main_command, user_input, your_id=None):
    """
    Ask for mode selection, if no command line arguments supplied
    call the right function depending on the mode
    user_input : str or int
        For artist_illusts_mode, it is artist_user_id : int
        For view_post_mode, it is image_id : int
        For following users mode, it is your_id : int
        For search users mode, it is search_string : str
        For illust following mode, it's not required
    """
    # SPEED: gallery mode - if tmp has artist id and '1' dir,
    # immediately show it without trying to log in or download
    printmessage = True
    while True:
        if prompted and not user_input:
            main_command = utils.begin_prompt(printmessage)

        if main_command == "1":
            ArtistModeLoop(prompted, user_input).start(_API)

        elif main_command == "2":
            ViewPostModeLoop(prompted, user_input).start(_API)

        elif main_command == "3":
            if your_id: # your_id stored in config file
                ans = input("Do you want to use the Pixiv ID saved in your config?\n")
                if ans in {"y", ""}:
                    FollowingUserModeLoop(prompted, your_id).start(_API)

            # If your_id not stored, or if ans is no, ask for your_id
            FollowingUserModeLoop(prompted, user_input).start(_API)

        elif main_command == "4":
            SearchUsersModeLoop(prompted, user_input).start(_API)

        elif main_command == "5":
            IllustFollowModeLoop().start(_API)

        elif main_command == "?":
            utils.info_screen_loop()

        elif main_command == "m":
            utils.show_man_loop()

        elif main_command == "c":
            utils.clear_cache_loop()

        elif main_command == "q":
            answer = input("Are you sure you want to exit? [y/N]:\n")
            if answer == "y" or not answer:
                sys.exit(0)
            else:
                printmessage = False
                continue

        else:
            print("\nInvalid command!")
            printmessage = False
            continue


#- Loop classes
class Loop(ABC):
    """Ask for details relevant to mode then go to mode
    prompt user for details, if no command line arguments supplied
    process input (can be overridden)
    validate input (can be overridden)
    wait for api thread to finish logging in
    activates the selected mode (needs to be overridden)
    """
    def __init__(self, prompted, user_input):
        self._prompted = prompted
        self._user_input = user_input
        # Defined by classes that inherit this in _prompt_url_id()
        self._url_or_id: str
        self.mode: Any

    def start(self, _API):
        """Ask for further info if not provided; wait for log in then proceed"""
        while True:
            if self._prompted and not self._user_input:
                self._prompt_url_id()
                os.system("clear")

                self._process_url_or_input()
                self._validate_input()

            _API.await_login()
            self._go_to_mode()

    @abstractmethod
    def _prompt_url_id(self):
        """define self._url_or_id here"""
        raise NotImplementedError

    def _process_url_or_input(self):
        if "pixiv" in self._url_or_id:
            self._user_input = pure.split_backslash_last(self._url_or_id)
        else:
            self._user_input = self._url_or_id

    def _validate_input(self):
        try:
            int(self._user_input)
        except ValueError:
            print("Invalid image ID! Returning to main...")
            time.sleep(2)
            main()

    @abstractmethod
    def _go_to_mode(self):
        """Define self.mode here"""
        raise NotImplementedError


class ArtistModeLoop(Loop):
    """
    Ask for artist ID and process it, wait for API to finish logging in
    before proceeding
    """
    def _prompt_url_id(self):
        self._url_or_id = utils.artist_user_id_prompt()

    def _go_to_mode(self):
        self.mode = ArtistGalleryMode(self._user_input)
        # This is the entry mode, user goes back but there is nothing to catch it
        main()


class ViewPostModeLoop(Loop):
    """
    Ask for post ID and process it, wait for API to finish logging in
    before proceeding
    """
    def _prompt_url_id(self):
        self._url_or_id = input("Enter pixiv post url or ID:\n")

    def _process_url_or_input(self):
        """Overriding base class to account for 'illust_id' cases"""
        if "illust_id" in self._url_or_id:
            reg = re.findall(r"&illust_id.*", self._url_or_id)
            self._user_input = reg[0].split("=")[-1]

        elif "pixiv" in self._url_or_id:
            self._user_input = pure.split_backslash_last(self._url_or_id)
        else:
            self._user_input = self._url_or_id

    def _go_to_mode(self):
        self.mode = view_post_mode(self._user_input)


class SearchUsersModeLoop(Loop):
    """
    Ask for search string and process it, wait for API to finish logging in
    before proceeding
    """
    def _prompt_url_id(self):
        self._url_or_id = input("Enter search string:\n")

    def _process_url_or_input(self):
        """the 'url or id' name doesn't really apply; accepts all strings"""
        self._user_input = self._url_or_id

    def _validate_input(self):
        """Overriding base class: search string doesn't need to be int
        Technically it doesn't violate LSP because all inputs are valid
        """
        return True

    def _go_to_mode(self):
        self.mode = ui.SearchUsers(self._user_input)
        self.mode.start()
        prompt.user_prompt(self.mode)


class FollowingUserModeLoop(Loop):
    """
    Ask for pixiv ID or url and process it, wait for API to finish logging in
    before proceeding
    If user agrees to use the your_id saved in config, prompt_url_id() will be
    skipped
    """
    def _prompt_url_id(self):
        self._url_or_id = input("Enter your pixiv ID or url: ")

    def _go_to_mode(self):
        self.mode = ui.FollowingUsers(self._user_input)
        self.mode.start()
        prompt.user_prompt(self.mode)

class IllustFollowModeLoop:
    """Immediately goes to IllustFollow()"""
    def start(self, _API):
        while True:
            _API.await_login()
            self._go_to_mode()

    def _go_to_mode(self):
        self.mode = IllustFollowMode()

# - Mode classes
class GalleryLikeMode(ABC):
    def __init__(self, current_page_num=1, all_pages_cache=None):
        self._current_page_num = current_page_num
        self._show = True
        # Defined in self.start()
        self._current_page: 'JsonDict'
        # Defined in self._init_download()
        self._current_page_illusts: 'JsonDictPage'
        self._all_pages_cache = all_pages_cache
        # Defined in child classes
        self._download_path: str
        self.gallery: GalleryLikeMode

        self.start()

    def start(self):
        """
        If artist_user_id dir exists, show immediately (without checking
        for contents!)
        Else, fetch current_page json and proceed download -> show -> prompt
        """
        if Path(self._download_path).is_dir():
            try:
                utils.show_artist_illusts(self._download_path)
            except IndexError: # Folder exists but no files
                self._show = True
            else:
                self._show = False
        else:
            self._show = True

        self._current_page = self._pixivrequest()
        self._init_download()
        if self._show:
            utils.show_artist_illusts(self._download_path)
        self._instantiate()

    @abstractmethod
    @funcy.retry(tries=3, errors=(ConnectionError, PixivError))
    def _pixivrequest(self):
        raise NotImplementedError

    def _download_pbar(self):
        pbar = tqdm(total=len(self._current_page_illusts), smoothing=0)
        download_page(self._current_page_illusts, self._download_path, pbar=pbar)
        pbar.close()

    def _init_download(self):
        self._current_page_illusts = self._current_page["illusts"]
        titles = pure.post_titles_in_page(self._current_page_illusts)

        if not Path(self._download_path).is_dir():
            self._download_pbar()

        elif not titles[0] in sorted(os.listdir(self._download_path))[0]:
            print("Cache is outdated, reloading...")
            # Remove old images
            os.system(f"rm -r {self._download_path}") # shutil.rmtree is better
            self._download_pbar()
            self._show = True

        if not self._all_pages_cache:
            self._all_pages_cache = {"1": self._current_page}

    @abstractmethod
    def _instantiate(self):
        """Instantiate the correct Gallery class"""
        raise NotImplementedError

class ArtistGalleryMode(GalleryLikeMode):
    def __init__(self, artist_user_id, current_page_num=1, **kwargs):
        self._artist_user_id = artist_user_id
        self._download_path = f"{KONEKODIR}/{artist_user_id}/{current_page_num}/"

        if kwargs:
            self._current_page_num = current_page_num
            self._current_page = kwargs['current_page']
            self._all_pages_cache = kwargs['all_pages_cache']

            self.start()
        super().__init__(current_page_num, None)


    def _pixivrequest(self):
        return artist_gallery_request(self._artist_user_id)

    def _instantiate(self):
        self.gallery = ui.ArtistGallery(
            self._current_page_illusts,
            self._current_page,
            self._current_page_num,
            self._artist_user_id,
            self._all_pages_cache
        )
        prompt.gallery_like_prompt(self.gallery)
        # After backing, exit mode. The class that instantiated this mode
        # should catch the back.


class IllustFollowMode(GalleryLikeMode):
    def __init__(self, current_page_num=1, all_pages_cache=None):
        self._download_path = f"{KONEKODIR}/illustfollow/{current_page_num}/"
        super().__init__(current_page_num, all_pages_cache)

    def _pixivrequest(self):
        return illust_follow_request(restrict='private') # Publicity

    def _instantiate(self):
        self.gallery = ui.IllustFollowGallery(
            self._current_page_illusts,
            self._current_page,
            self._current_page_num,
            self._all_pages_cache,
        )
        prompt.gallery_like_prompt(self.gallery)
        # After backing
        main()

def view_post_mode(image_id):
    """
    Fetch all the illust info, download it in the correct directory, then display it.
    If it is a multi-image post, download the next image
    Else or otherwise, open image prompt
    """
    print("Fetching illust details...")
    try:
        post_json = protected_illust_detail(image_id)["illust"]
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

    # Will only be used for multi-image posts, so it's safe to use large_dir
    # Without checking for number_of_pages
    multi_image_info = {
        'page_urls': page_urls,
        'img_post_page_num': 0,
        'number_of_pages': number_of_pages,
        'downloaded_images': downloaded_images,
        'download_path': large_dir,
    }

    image = ui.Image(image_id, artist_user_id, 1, True, multi_image_info)
    prompt.image_prompt(image)


# ================================   API  ====================================
class APIHandler:
    def __init__(self, credentials):
        self._credentials = credentials
        self.API_QUEUE = queue.Queue()
        self.API_THREAD = threading.Thread(target=self.login)

    def start(self):
        """Start logging in"""
        self.API_THREAD.start()

    def await_login(self):
        """Wait for login to finish, then assign PixivAPI session to API"""
        self.API_THREAD.join()
        global API
        API = self.API_QUEUE.get()

    def login(self):
        """
        Logins to pixiv in the background, using credentials from config file.
        """
        api = AppPixivAPI()
        api.login(self._credentials["Username"], self._credentials["Password"])
        self.API_QUEUE.put(api)


# API request functions for each mode
@funcy.retry(tries=3, errors=(ConnectionError, PixivError))
def parse_next(next_url):
    """All modes; parse next_url for next page's json"""
    return API.parse_qs(next_url)

@funcy.retry(tries=3, errors=(ConnectionError, PixivError))
@pure.spinner("")
def artist_gallery_parse_next(**kwargs):
    """Mode 1, feed in next page"""
    return API.user_illusts(**kwargs)

@funcy.retry(tries=3, errors=(ConnectionError, PixivError))
@pure.spinner("")
def artist_gallery_request(artist_user_id):
    """Mode 1, normal usage"""
    return API.user_illusts(artist_user_id)

@funcy.retry(tries=3, errors=(ConnectionError, PixivError))
def search_user_request(searchstr, offset):
    """Mode 3"""
    return API.search_user(searchstr, offset=offset)

@funcy.retry(tries=3, errors=(ConnectionError, PixivError))
def following_user_request(user_id, publicity, offset):
    """Mode 4"""
    return API.user_following(user_id, restrict=publicity, offset=offset)

@funcy.retry(tries=3, errors=(ConnectionError, PixivError))
@pure.spinner("")
def illust_follow_request(**kwargs):
    """Mode 5
    **kwargs can be **parse_page (for _prefetch_next_page), but also contain
    publicity='private' (for normal)
    """
    return API.illust_follow(**kwargs)


@funcy.retry(tries=3, errors=(ConnectionError, PixivError))
def protected_illust_detail(image_id):
    """Mode 2"""
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


# - DOWNLOAD FUNCTIONS
# - For batch downloading multiple images (all 5 functions related)
@pure.spinner("")
def async_download_spinner(download_path, urls, rename_images=False,
                           file_names=None, pbar=None):
    """Batch download and rename, with spinner. For mode 2; multi-image posts"""
    async_download_core(
        download_path,
        urls,
        rename_images=rename_images,
        file_names=file_names,
        pbar=pbar,
    )


def async_download_core(download_path, urls, rename_images=False,
                        file_names=None, pbar=None):
    """
    Rename files with given new name if needed.
    Submit each url to the ThreadPoolExecutor, so download and rename are concurrent
    """
    oldnames = list(map(pure.split_backslash_last, urls))
    if rename_images:
        newnames = map(pure.prefix_filename, oldnames, file_names, range(len(urls)))
        newnames = list(newnames)
    else:
        newnames = oldnames

    filtered = itertools.filterfalse(os.path.isfile, newnames)
    oldnames = itertools.filterfalse(os.path.isfile, oldnames)
    helper = downloadr(pbar=pbar)
    os.makedirs(download_path, exist_ok=True)
    with pure.cd(download_path):
        with ThreadPoolExecutor(max_workers=len(urls)) as executor:
            executor.map(helper, urls, oldnames, filtered)

@funcy.retry(tries=3, errors=(ConnectionError, PixivError))
def protected_download(url):
    """Protect api download function with funcy.retry so it doesn't crash"""
    API.download(url)

@cytoolz.curry
def downloadr(url, img_name, new_file_name=None, pbar=None):
    """Actually downloads one pic given one url, rename if needed."""
    protected_download(url)

    if pbar:
        pbar.update(1)
    # print(f"{img_name} done!")
    if new_file_name:
        # This character break renames
        if "/" in new_file_name:
            new_file_name = new_file_name.replace("/", "")
        os.rename(img_name, new_file_name)


def download_page(current_page_illusts, download_path, pbar=None):
    """
    Download the illustrations on one page of given artist id (using threads),
    rename them based on the *post title*. Used for gallery modes (1 and 5)
    """
    urls = pure.medium_urls(current_page_illusts)
    titles = pure.post_titles_in_page(current_page_illusts)

    async_download_core(
        download_path, urls, rename_images=True, file_names=titles, pbar=pbar
    )


# - Wrappers around the core functions for downloading one image
@pure.spinner("")
def download_core(large_dir, url, filename, try_make_dir=True):
    """Downloads one url, intended for single images only"""
    if try_make_dir:
        os.makedirs(large_dir, exist_ok=True)
    if not Path(filename).is_file():
        print("   Downloading illustration...", flush=True, end="\r")
        with pure.cd(large_dir):
            downloadr(url, filename, None)


def download_image_verified(image_id=None, post_json=None, png=False, **kwargs):
    """
    This downloads an image, checks if it's valid. If not, retry with png.
    Used for downloading full-res, single only; on-user-demand
    """
    if png and 'url' in kwargs: # Called from recursion
        # IMPROVEMENT This is copied from full_img_details()...
        url = pure.change_url_to_full(url=kwargs['url'], png=True)
        filename = pure.split_backslash_last(url)
        filepath = pure.generate_filepath(filename)

    elif not kwargs:
        url, filename, filepath = full_img_details(
            image_id=image_id, post_json=post_json, png=png
        )
    else:
        url = kwargs["url"]
        filename = kwargs["filename"]
        filepath = kwargs["filepath"]

    download_path = Path("~/Downloads").expanduser()
    download_core(download_path, url, filename, try_make_dir=False)

    verified = utils.verify_full_download(filepath)
    if not verified:
        download_image_verified(url=url, png=True)
    else:
        print(f"Image downloaded at {filepath}\n")

if __name__ == "__main__":
    main()
