#!/usr/bin/env python3
"""Browse pixiv in the terminal using kitty's icat to display images (in the
terminal!)

Usage:
  ./koneko.py       [<link> | <searchstr>]
  ./koneko.py [1|a] <link_or_id>
  ./koneko.py [2|i] <link_or_id>
  ./koneko.py (3|f) <link_or_id>
  ./koneko.py [4|s] <searchstr>
  ./koneko.py [5|n]
  ./koneko.py -h

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
import queue
import threading
from pathlib import Path
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor

import funcy
from tqdm import tqdm
from colorama import Fore
from docopt import docopt
from pixivpy3 import PixivError, AppPixivAPI

import pure
import lscat
import utils
import prompt
import colors


def main():
    """Read config file, start login, process any cli arguments, go to main loop"""
    os.system("clear")
    credentials, your_id = utils.config()

    # It'll never be changed after logging in
    global API, API_QUEUE, API_THREAD
    API_QUEUE = queue.Queue()
    API_THREAD = threading.Thread(target=setup, args=(API_QUEUE, credentials))
    API_THREAD.start()  # Start logging in

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
        main_loop(prompted, main_command, user_input, your_id)
    except KeyboardInterrupt:
        print("\n")
        answer = input("Are you sure you want to exit? [y/N]:\n")
        if answer == "y" or not answer:
            sys.exit(0)
        else:
            main()

def main_loop(prompted, main_command, user_input, your_id=None):
    """
    Ask for mode selection, if no command line arguments supplied
    call the right function depending on the mode
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
            ArtistModeLoop(prompted, user_input).start()

        elif main_command == "2":
            ViewPostModeLoop(prompted, user_input).start()

        elif main_command == "3":
            if your_id: # your_id stored in config file
                ans = input("Do you want to use the Pixiv ID saved in your config?\n")
                if ans in {"y", ""}:
                    FollowingUserModeLoop(prompted, your_id).start()

            # If your_id not stored, or if ans is no, ask for your_id
            FollowingUserModeLoop(prompted, user_input).start()

        elif main_command == "4":
            SearchUsersModeLoop(prompted, user_input).start()

        elif main_command == "5":
            IllustFollowModeLoop().start()

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


#- Loop classes ==========================================================
class Loop(ABC):
    """Ask for details relevant to mode then go to mode
    prompt user for details, if no command line arguments supplied
    process input (can be overridden)
    validate input (can be overridden)
    wait for api thread to finish logging in
    activates the selected mode (needs to be overridden)

    Note: this violates the Liskov substitution principle, because
    subclasses can 'remove' methods (by overriding them to `pass`)
    This isn't a big concern because I just want to reduce code duplication,
    thematically group functions into the Loop ABC, & those methods are private anyway
    """
    def __init__(self, prompted, user_input):
        self._prompted = prompted
        self._user_input = user_input
        # Defined by classes that inherit this in _prompt_url_id()
        self._url_or_id = None

    def start(self):
        while True:
            if self._prompted and not self._user_input:
                self._prompt_url_id()
                os.system("clear")

                self._process_url_or_input()
                self._validate_input()

            API_THREAD.join()  # Wait for API to finish
            global API
            API = API_QUEUE.get()  # Assign API to PixivAPI object

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
            print("Invalid image ID!")

    @abstractmethod
    def _go_to_mode(self):
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
            self._user_input = re.findall(
                 r"&illust_id.*",
                self._url_or_id
            )[0].split("=")[-1]

        elif "pixiv" in self._url_or_id:
            self._user_input = pure.split_backslash_last(self._url_or_id)
        else:
            self._user_input = self._url_or_id

    def _go_to_mode(self):
        view_post_mode(self._user_input)


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
        """Overriding base class: search string doesn't need to be int"""
        pass

    def _go_to_mode(self):
        self.searching = SearchUsers(self._user_input)
        self.searching.start()
        prompt.user_prompt(self.searching)


class FollowingUserModeLoop(Loop):
    """
    Ask for pixiv ID or url and process it, wait for API to finish logging in
    before proceeding
    If user agrees to use the your_id saved in configu, prompt_url_id() will be
    skipped
    """
    def _prompt_url_id(self):
        self._url_or_id = input("Enter your pixiv ID or url: ")

    def _go_to_mode(self):
        self.following = FollowingUsers(self._user_input)
        self.following.start()
        prompt.user_prompt(self.following)

class IllustFollowModeLoop(Loop):
    """
    Immediately goes to IllustFollow()
    Doesn't actually need to inherit from Loop ABC because it's so different
    But make UML diagrams look better
    """
    def __init__(self): pass

    def start(self):
        while True:
            API_THREAD.join()  # Wait for API to finish
            global API
            API = API_QUEUE.get()  # Assign API to PixivAPI object

            self._go_to_mode()

    def _prompt_url_id(self): pass

    def _go_to_mode(self):
        self.mode = IllustFollowMode()

# - Loop classes ==========================================================

# - Mode classes
class GalleryLikeMode(ABC):
    def __init__(self, current_page_num=1, all_pages_cache=None):
        self._current_page_num = current_page_num
        # Defined in self.start()
        self._current_page = None
        # Defined in self._show_gallery()
        self._current_page_illusts = None
        self._all_pages_cache = all_pages_cache

        self.start()

    def start(self):
        """
        If artist_user_id dir exists, show immediately (without checking
        for contents!)
        Else, fetch current_page json and proceed download -> show -> prompt
        """
        # If path exists, show immediately (without checking for contents!)
        if Path(self._download_path).is_dir(): # Defined in child classes
            try:
                utils.show_artist_illusts(self._download_path)
            except IndexError: # Folder exists but no files
                show = True
            else:
                show = False
        else:
            show = True

        self._current_page = self._pixivrequest()
        self._show_gallery(show=show)
        self._instantiate()

    @abstractmethod
    @funcy.retry(tries=3, errors=(ConnectionError, PixivError))
    def _pixivrequest(self):
        raise NotImplementedError

    def _show_gallery(self, show=True):
        """
        Downloads images, show if requested, instantiate all_pages_cache, prompt.
        """
        self._current_page_illusts = self._current_page["illusts"]

        if not Path(self._download_path).is_dir():
            pbar = tqdm(total=len(self._current_page_illusts), smoothing=0)
            download_page(self._current_page_illusts, self._download_path, pbar=pbar)
            pbar.close()

        if show:
            utils.show_artist_illusts(self._download_path)

        if not self._all_pages_cache:
            self._all_pages_cache = {"1": self._current_page}

    @abstractmethod
    def _instantiate(self):
        raise NotImplementedError

class ArtistGalleryMode(GalleryLikeMode):
    def __init__(self, artist_user_id, current_page_num=1, **kwargs):
        self._artist_user_id = artist_user_id
        self._download_path = f"{KONEKODIR}/{artist_user_id}/{current_page_num}/"
        self._illust_follow_info = None

        if kwargs:
            self._current_page_num = current_page_num
            self._current_page = kwargs['current_page']
            self._all_pages_cache = kwargs['all_pages_cache']

            self.start()
        super().__init__(current_page_num, None)


    @funcy.retry(tries=3, errors=(ConnectionError, PixivError))
    @pure.spinner("")
    def _pixivrequest(self):
        return API.user_illusts(self._artist_user_id)

    def _instantiate(self):
        self.gallery = ArtistGallery(
            self._current_page_illusts,
            self._current_page,
            self._current_page_num,
            self._artist_user_id,
            self._all_pages_cache,
            illust_follow_info=self._illust_follow_info,
        )
        prompt.gallery_like_prompt(self.gallery)
        # After backing
        main()


class IllustFollowMode(GalleryLikeMode):
    """
    artist_user_id is useless. Only determines where the pics will be saved
    It's set to a string for now, will remove later
    """
    def __init__(self, current_page_num=1, all_pages_cache=None):
        self._download_path = f"{KONEKODIR}/illustfollow/{current_page_num}/"
        super().__init__(current_page_num, all_pages_cache)

    @funcy.retry(tries=3, errors=(ConnectionError, PixivError))
    @pure.spinner("")
    def _pixivrequest(self):
        return API.illust_follow(restrict='private')

    def _instantiate(self):
        self.gallery = IllustFollowGallery(
            self._current_page_illusts,
            self._current_page,
            self._current_page_num,
            self._all_pages_cache,
        )
        prompt.gallery_like_prompt(self.gallery)
        # After backing
        main()

# - Mode and loop functions (some interactive and some not)
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

    multi_image_info = {
        'page_urls': page_urls,
        'img_post_page_num': 0,
        'number_of_pages': number_of_pages,
        'downloaded_images': downloaded_images,
        'download_path': large_dir,
    }

    image = Image(image_id, artist_user_id, 1, True, multi_image_info)
    prompt.image_prompt(image)
    # Will only be used for multi-image posts, so it's safe to use large_dir
    # Without checking for number_of_pages
# - Mode and loop functions (some interactive and some not)


# - Interactive functions (frontend)
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
    def __init__(self, image_id, artist_user_id, current_page_num=1,
                 firstmode=False, multi_image_info=None):
        self._image_id = image_id
        self._artist_user_id = artist_user_id
        self._current_page_num = current_page_num
        self._firstmode = firstmode

        if multi_image_info:  # Posts with multiple pages
            self._page_urls = multi_image_info["page_urls"]
            self._img_post_page_num = multi_image_info["img_post_page_num"]
            self._number_of_pages = multi_image_info["number_of_pages"]
            self._downloaded_images = multi_image_info["downloaded_images"]
            self._download_path = multi_image_info['download_path']

    def open_image(self):
        link = f"https://www.pixiv.net/artworks/{self._image_id}"
        os.system(f"xdg-open {link}")
        print(f"Opened {link} in browser")

    def download_image(self):
        current_url = self._page_urls[self._img_post_page_num]
        # Need to work on multi-image posts
        # Doing the same job as full_img_details
        large_url = pure.change_url_to_full(url=current_url)
        filename = pure.split_backslash_last(large_url)
        filepath = pure.generate_filepath(filename)
        download_image_verified(url=large_url, filename=filename, filepath=filepath)

    def next_image(self):
        if not self._page_urls:
            print("This is the only page in the post!")
        elif self._img_post_page_num + 1 == self._number_of_pages:
            print("This is the last image in the post!")

        else:
            self._img_post_page_num += 1  # Be careful of 0 index
            self._downloaded_images = go_next_image(
                self._page_urls,
                self._img_post_page_num,
                self._number_of_pages,
                self._downloaded_images,
                self._download_path,
            )

    def previous_image(self):
        if not self._page_urls:
            print("This is the only page in the post!")
        elif self._img_post_page_num == 0:
            print("This is the first image in the post!")
        else:
            self._img_post_page_num -= 1
            image_filename = self._downloaded_images[self._img_post_page_num]
            utils.display_image_vp(f"{self._download_path}{image_filename}")
            print(f"Page {self._img_post_page_num+1}/{self._number_of_pages}")

    def leave(self, force=False):
        if self._firstmode or force:
            # Came from view post mode, don't know current page num
            # Defaults to page 1
            ArtistGalleryMode(self._artist_user_id, self._current_page_num)
        # Else: image prompt and class ends, goes back to gallery


class AbstractGallery(ABC):
    def __init__(self, current_page_illusts, current_page, current_page_num,
                 all_pages_cache):
        self._current_page_illusts = current_page_illusts
        self._current_page = current_page
        self._current_page_num = current_page_num
        self._all_pages_cache = all_pages_cache
        self._post_json = None # Defined in self.view_image

        pure.print_multiple_imgs(self._current_page_illusts)
        print(f"Page {self._current_page_num}")

        # Fixes: Gallery -> next page -> image prompt -> back -> prev page
        # Gallery -> Image -> back still retains all_pages_cache, no need to
        # prefetch again
        if len(self._all_pages_cache) == 1:
            # Prefetch the next page on first gallery load
            with funcy.suppress(LastPageException):
                self._prefetch_next_page()

        else:
            # Gallery -> next -> image prompt -> back
            self._all_pages_cache[str(self._current_page_num)] = self._current_page

    def open_link_coords(self, first_num, second_num):
        selected_image_num = pure.find_number_map(int(first_num), int(second_num))
        if not selected_image_num:
            print("Invalid number!")
        else:
            self.open_link_num(selected_image_num)

    def open_link_num(self, number):
        # Update current_page_illusts, in case if you're in another page
        self._current_page = self._all_pages_cache[str(self._current_page_num)]
        self._current_page_illusts = self._current_page["illusts"]
        image_id = self._current_page_illusts[number]["id"]
        link = f"https://www.pixiv.net/artworks/{image_id}"
        os.system(f"xdg-open {link}")
        print(f"Opened {link}!\n")

    def download_image_coords(self, first_num, second_num):
        selected_image_num = pure.find_number_map(int(first_num), int(second_num))
        if not selected_image_num:
            print("Invalid number!")
        else:
            self.download_image_num(selected_image_num)

    def download_image_num(self, number):
        # Update current_page_illusts, in case if you're in another page
        self._current_page = self._all_pages_cache[str(self._current_page_num)]
        self._current_page_illusts = self._current_page["illusts"]
        post_json = self._current_page_illusts[number]
        download_image_verified(post_json=post_json)

    def view_image(self, selected_image_num):
        self._selected_image_num = selected_image_num
        self._current_page = self._all_pages_cache[str(self._current_page_num)]
        self._current_page_illusts = self._current_page["illusts"]
        self._post_json = self._current_page_illusts[selected_image_num]

        # IllustFollow doesn't have artist_user_id
        artist_user_id = self._post_json['user']['id']
        image_id = self._post_json.id

        display_image(
            self._post_json,
            artist_user_id,
            self._selected_image_num,
            self._current_page_num
        )

        # blocking: no way to unblock prompt
        number_of_pages, page_urls = pure.page_urls_in_post(self._post_json, "large")

        # self._main_path defined in child classes
        multi_image_info = {
            'page_urls': page_urls,
            'img_post_page_num': 0,
            'number_of_pages': number_of_pages,
            'downloaded_images': None,
            'download_path': f"{self._main_path}/{self._current_page_num}/large/",
        }

        image = Image(image_id, artist_user_id,
                      self._current_page_num, False, multi_image_info)
        prompt.image_prompt(image)

        # Image prompt ends, user presses back
        self._back()

    @abstractmethod
    def _back(self):
        raise NotImplementedError

    def next_page(self):
        download_path = f"{self._main_path}/{self._current_page_num+1}/"
        try:
            utils.show_artist_illusts(download_path)
        except FileNotFoundError:
            print("This is the last page!")
        else:
            self._current_page_num += 1
            print(f"Page {self._current_page_num}")
            print("Enter a gallery command:\n")

        # Skip prefetching again for cases like next -> prev -> next
        if str(self._current_page_num + 1) not in self._all_pages_cache.keys():
            try:
                # After showing gallery, pre-fetch the next page
                self._prefetch_next_page()
            except LastPageException:
                print("This is the last page!")

    def previous_page(self):
        if self._current_page_num > 1:
            self._current_page = self._all_pages_cache[str(self._current_page_num - 1)]
            self._current_page_illusts = self._current_page["illusts"]
            self._current_page_num -= 1

            download_path = (
                f"{self._main_path}/{self._current_page_num}/"
            )
            utils.show_artist_illusts(download_path)
            print(f"Page {self._current_page_num}")
            print("Enter a gallery command:\n")

        else:
            print("This is the first page!")

    @abstractmethod
    @funcy.retry(tries=3, errors=(ConnectionError, PixivError))
    def _pixivrequest(self, **kwargs):
        raise NotImplementedError

    def _prefetch_next_page(self):
        # print("   Prefetching next page...", flush=True, end="\r")
        next_url = self._all_pages_cache[str(self._current_page_num)]["next_url"]
        if not next_url:  # this is the last page
            raise LastPageException

        parse_page = API.parse_qs(next_url)
        next_page = self._pixivrequest(**parse_page)
        self._all_pages_cache[str(self._current_page_num + 1)] = next_page
        current_page_illusts = next_page["illusts"]

        download_path = f"{self._main_path}/{self._current_page_num+1}/"
        if not Path(download_path).is_dir():
            pbar = tqdm(total=len(current_page_illusts), smoothing=0)
            download_page(
                current_page_illusts, download_path, pbar=pbar
            )
            pbar.close

    def reload(self):
        ans = input("This will delete cached images and redownload them. Proceed?\n")
        if ans == "y" or not ans:
            os.system(f"rm -r {self._main_path}") # shutil.rmtree is better
            self._back()
        else:
            prompt.gallery_like_prompt(self)

    @abstractmethod
    def handle_prompt(self, keyseqs, gallery_command, selected_image_num,
                      first_num, second_num):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def help():
        raise NotImplementedError


class ArtistGallery(AbstractGallery):
    """
    Artist Gallery commands: (No need to press enter)
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
        r                  -- delete all cached images, re-download and reload view
        b                  -- go back to previous mode (either 3, 4, 5, or main screen)
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
    def __init__(self, current_page_illusts, current_page,
                 current_page_num, artist_user_id, all_pages_cache, **kwargs):
        self._main_path = f"{KONEKODIR}/{artist_user_id}/"
        self._artist_user_id = artist_user_id
        self._kwargs = kwargs
        super().__init__(current_page_illusts, current_page, current_page_num,
                         all_pages_cache)

    @funcy.retry(tries=3, errors=(ConnectionError, PixivError))
    @pure.spinner("")
    def _pixivrequest(self, **kwargs):
        return API.user_illusts(**kwargs)

    def _back(self):
        # After user 'back's from image prompt, start mode again
        ArtistGalleryMode(self._artist_user_id, self._current_page_num,
                          all_pages_cache=self._all_pages_cache,
                          current_page=self._current_page)

    def handle_prompt(self, keyseqs, gallery_command, selected_image_num,
                      first_num, second_num):
        # Display image (using either coords or image number), the show this prompt
        if gallery_command == "b":
            pass # Stop gallery instance, return to previous state
        elif gallery_command == "r":
            self.reload()
        elif keyseqs[0] == "i":
            self.view_image(selected_image_num)
        elif keyseqs[0].lower() == "a":
            print("Invalid command! Press h to show help")
            prompt.gallery_like_prompt(self) # Go back to while loop
        elif len(keyseqs) == 2:
            selected_image_num = pure.find_number_map(first_num, second_num)
            self.view_image(selected_image_num)

    @staticmethod
    def help():
        print(f"{colors.coords} view image at (x,y); {colors.i} view nth image; {colors.d} download image;\n{colors.o} open image in browser; {colors.n}ext image; {colors.p}revious image;\n{colors.r}eload and re-download all; {colors.q}uit (with confirmation); view {colors.m}anual; {colors.b}ack\n")


class IllustFollowGallery(AbstractGallery):
    """
    Illust Follow Gallery commands: (No need to press enter)
        Using coordinates, where {digit1} is the row and {digit2} is the column
        {digit1}{digit2}   -- display the image on row digit1 and column digit2
        o{digit1}{digit2}  -- open pixiv image/post in browser
        d{digit1}{digit2}  -- download image in large resolution
        a{digit1}{digit2}  -- view illusts by the artist of the selected image

    Using image number, where {number} is the nth image in order (see examples)
        i{number}          -- display the image
        O{number}          -- open pixiv image/post in browser.
        D{number}          -- download image in large resolution.
        A{number}          -- view illusts by the artist of the selected image

        n                  -- view the next page
        p                  -- view the previous page
        r                  -- delete all cached images, re-download and reload view
        b                  -- go back to main screen
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
    def __init__(self, current_page_illusts, current_page,
                 current_page_num, all_pages_cache):
        self._main_path = f"{KONEKODIR}/illustfollow/"
        super().__init__(current_page_illusts, current_page, current_page_num,
                         all_pages_cache)

    @funcy.retry(tries=3, errors=(ConnectionError, PixivError))
    @pure.spinner("")
    def _pixivrequest(self, **kwargs):
        """
        **kwargs can be **parse_page (for _prefetch_next_page), or
        publicity='private' (for normal)
        """
        if 'restrict' in kwargs:
            return API.illust_follow(**kwargs)
        else:
            return API.illust_follow()

    def go_artist_gallery_coords(self, first_num, second_num):
        selected_image_num = pure.find_number_map(int(first_num), int(second_num))
        self.go_artist_gallery_num(selected_image_num)

    def go_artist_gallery_num(self, selected_image_num):
        """Like self.view_image(), but goes to artist mode instead of image"""
        self._selected_image_num = selected_image_num
        self._current_page = self._all_pages_cache[str(self._current_page_num)]
        self._current_page_illusts = self._current_page["illusts"]
        self._post_json = self._current_page_illusts[selected_image_num]

        artist_user_id = self._post_json['user']['id']
        ArtistGalleryMode(artist_user_id)
        # Gallery prompt ends, user presses back
        self._back()

    def _back(self):
        # User 'back's out of artist gallery, start current mode again
        IllustFollowMode(self._current_page_num, self._all_pages_cache)

    def handle_prompt(self, keyseqs, gallery_command, selected_image_num,
                      first_num, second_num):
        # "b" must be handled first, because keyseqs might be empty
        if gallery_command == "b":
            print("Invalid command! Press h to show help")
            prompt.gallery_like_prompt(self) # Go back to while loop
        elif gallery_command == "r":
            self.reload()
        elif keyseqs[0] == "i":
            self.view_image(selected_image_num)
        elif keyseqs[0] == "a":
            self.go_artist_gallery_coords(first_num, second_num)
        elif keyseqs[0] == "A":
            self.go_artist_gallery_num(selected_image_num)
        elif len(keyseqs) == 2:
            selected_image_num = pure.find_number_map(first_num, second_num)
            self.view_image(selected_image_num)

    @staticmethod
    def help():
        print(f"{colors.coords} view image at (x,y); {colors.i} view nth image; {colors.d} download image;\n{colors.o} open image in browser; view {colors.a}rtist gallery; {colors.n}ext image; {colors.p}revious image;\n{colors.r}eload and re-download all; {colors.q}uit (with confirmation); view {colors.m}anual\n")


class Users(ABC):
    """
    User view commands (No need to press enter):
        n -- view next page
        p -- view previous page
        r -- delete all cached images, re-download and reload view
        h -- show this help
        q -- quit (with confirmation)

    """

    @abstractmethod
    def __init__(self, user_or_id):
        self._input = user_or_id
        self._offset = 0
        self._page_num = 1
        # self._main_path defined in child classes
        self._download_path = f"{self._main_path}/{self._input}/{self._page_num}"
        self._names_cache = {}
        self._ids_cache = {}
        # Defined in _parse_user_infos():
        self._next_url = None
        self._ids = None
        self._names = None
        self._profile_pic_urls = None

    def start(self):
        # TODO: if dir exists, show page first then parse
        self._parse_and_download()
        self._show_page()
        self._prefetch_next_page()

    def _parse_and_download(self):
        """
        Parse info, combine profile pics and previews, download all concurrently,
        move the profile pics to the correct dir (less files to move)
        """
        self._parse_user_infos()

        preview_path = f"{self._main_path}/{self._input}/{self._page_num}/previews/"
        all_urls = self._profile_pic_urls + self._image_urls
        preview_names_ext = map(pure.split_backslash_last, self._image_urls)
        preview_names = [x.split('.')[0] for x in preview_names_ext]
        all_names = self._names + preview_names
        splitpoint = len(self._profile_pic_urls)

        if (Path(self._download_path).is_dir() and
                len(os.listdir(self._download_path)) == splitpoint + 1):
            return True

        pbar = tqdm(total=len(all_urls), smoothing=0)
        async_download_core(
            preview_path,
            all_urls,
            rename_images=True,
            file_names=all_names,
            pbar=pbar
        )
        pbar.close()

        # Move artist profile pics to their correct dir
        to_move = sorted(os.listdir(preview_path))[:splitpoint]
        with pure.cd(self._download_path):
            for pic in to_move:
                os.rename(f"{self._download_path}/previews/{pic}",
                          f"{self._download_path}/{pic}")


    @abstractmethod
    @funcy.retry(tries=3, errors=(ConnectionError, PixivError))
    def _pixivrequest(self):
        """Blank method, classes that inherit this ABC must override this"""
        raise NotImplementedError

    @pure.spinner('Parsing info...')
    def _parse_user_infos(self):
        """Parse json and get list of artist names, profile pic urls, and id"""
        result = self._pixivrequest()
        page = result["user_previews"]
        self._next_url = result["next_url"]

        self._ids = list(map(self._user_id, page))
        self._ids_cache.update({self._page_num: self._ids})

        self._names = list(map(self._user_name, page))
        self._names_cache.update({self._page_num: self._names})

        self._profile_pic_urls = list(map(self._user_profile_pic, page))

        # max(i) == number of artists on this page
        # max(j) == 3 == 3 previews for every artist
        self._image_urls = [page[i]['illusts'][j]['image_urls']['square_medium']
                            for i in range(len(page))
                            for j in range(len(page[i]['illusts']))]


    def _show_page(self):
        try:
            names = self._names_cache[self._page_num]
        except KeyError:
            print("This is the last page!")
            self._page_num -= 1
            self._download_path = f"{self._main_path}/{self._input}/{self._page_num}"

        else:
            names_prefixed = map(pure.prefix_artist_name, names, range(len(names)))
            names_prefixed = list(names_prefixed)

            lscat.Card(
                self._download_path,
                f"{self._main_path}/{self._input}/{self._page_num}/previews/",
                messages=names_prefixed,
            ).render()

    def _prefetch_next_page(self):
        oldnum = self._page_num

        if self._next_url:
            self._offset = API.parse_qs(self._next_url)["offset"]
            # For when next -> prev -> next
            self._page_num = int(self._offset) // 30 + 1
            self._download_path = f"{self._main_path}/{self._input}/{self._page_num}"

            self._parse_and_download()

        self._page_num = oldnum
        self._download_path = f"{self._main_path}/{self._input}/{self._page_num}"

    def next_page(self):
        self._page_num += 1
        self._download_path = f"{self._main_path}/{self._input}/{self._page_num}"
        self._show_page()

        self._prefetch_next_page()

    def previous_page(self):
        if self._page_num > 1:
            self._page_num -= 1
            self._download_path = f"{self._main_path}/{self._input}/{self._page_num}"
            self._show_page()
        else:
            print("This is the first page!")

    def go_artist_mode(self, selected_user_num):
        current_page_ids = self._ids_cache[self._page_num]
        try:
            artist_user_id = current_page_ids[selected_user_num]
        except IndexError:
            print("Invalid number!")
        ArtistGalleryMode(artist_user_id)
        # After backing from gallery
        self._show_page()
        prompt.user_prompt(self)

    def reload(self):
        ans = input("This will delete cached images and redownload them. Proceed?\n")
        if ans == "y" or not ans:
            os.system(f"rm -r {self._main_path}") # shutil.rmtree is better
            self.__init__(self._input)
            self.start()
        prompt.user_prompt(self)

    @staticmethod
    def _user_id(json):
        return json["user"]["id"]

    @staticmethod
    def _user_name(json):
        return json["user"]["name"]

    @staticmethod
    def _user_profile_pic(json):
        return json["user"]["profile_image_urls"]["medium"]

    @staticmethod
    def _image_urls(illusts_json):
        """page[i]['illusts'][j]['image_urls']['medium']"""
        return illusts_json['image_urls']['medium']


class SearchUsers(Users):
    """
    Inherits from Users class, define self._input as the search string (user)
    Parent directory for downloads should go to search/
    Note that pixivpy3 does not have search_user() yet (not released yet);
    you need to install the master branch (which should be done if you used
    the requirements.txt)
    """
    def __init__(self, user):
        self._main_path = f"{KONEKODIR}/search"
        super().__init__(user)

    @funcy.retry(tries=3, errors=(ConnectionError, PixivError))
    def _pixivrequest(self):
        return API.search_user(self._input, offset=self._offset)


class FollowingUsers(Users):
    """
    Inherits from Users class, define self._input as the user's pixiv ID
    (Or any other pixiv ID that the user wants to look at their following users)
    Parent directory for downloads should go to following/
    """
    def __init__(self, your_id, publicity='private'):
        self._publicity = publicity
        self._main_path = f"{KONEKODIR}/following"
        super().__init__(your_id)

    @funcy.retry(tries=3, errors=(ConnectionError, PixivError))
    def _pixivrequest(self):
        return API.user_following(
            self._input, restrict=self._publicity, offset=self._offset
        )

# - End interactive (frontend) functions



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
    """Protect api download function with funcy.retry so it doesn't crash"""
    API.download(url)


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


# - Functions that are wrappers around download functions, making them impure
# - Both classes used only by the Image class, but detached to reduce its size
def go_next_image(page_urls, img_post_page_num, number_of_pages,
                  downloaded_images, download_path):
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
    search_string = f"{str(number_prefix).rjust(3, '0')}_"

    # display the already-downloaded medium-res image first,
    # then download and display the large-res
    os.system("clear")
    arg = f"{KONEKODIR}/{artist_user_id}/{current_page_num}/{search_string}*"
    os.system(f"kitty +kitten icat --silent {arg}")

    url = pure.url_given_size(post_json, "large")
    filename = pure.split_backslash_last(url)
    large_dir = f"{KONEKODIR}/{artist_user_id}/{current_page_num}/large/"
    download_core(large_dir, url, filename)

    # BLOCKING: imput is blocking, will not display large image until input
    # received

    os.system("clear")
    arg = f"{KONEKODIR}/{artist_user_id}/{current_page_num}/large/{filename}"
    os.system(f"kitty +kitten icat --silent {arg}")

# - DOWNLOAD FUNCTIONS ==================================================

class LastPageException(ValueError):
    pass


if __name__ == "__main__":
    KONEKODIR = "/tmp/koneko"
    main()
