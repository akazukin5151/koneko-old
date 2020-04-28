"""Browse pixiv in the terminal using kitty's icat to display images (in the
terminal!)

Entry point of package, start all the while loops here and launch the
required mode.

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
from pathlib import Path
from abc import ABC, abstractmethod

from tqdm import tqdm

from koneko import pure
from koneko import utils
from koneko import prompt
from koneko import ui
from koneko import api
from koneko import download
from koneko import cli


# Pseudo-global as all functions rely on this value's closure
# Note: _single underscore doesn't mean it's private here ... just 'special'
_API = api.APIHandler()
KONEKODIR = Path("~/.local/share/koneko/cache").expanduser()

def main(start=True):
    """Read config file, start login, process any cli arguments, go to main loop"""
    os.system("clear")
    credentials, your_id = utils.config()
    if not Path("~/.local/share/koneko").expanduser().exists():
        print("Please wait, downloading welcome image (this will only occur once)...")
        baseurl = "https://raw.githubusercontent.com/twenty5151/koneko/master/pics/"
        basedir = Path("~/.local/share/koneko/pics").expanduser()

        basedir.mkdir(parents=True)
        for pic in ("71471144_p0.png", "79494300_p0.png"):
            os.system(f"curl -s {baseurl}{pic} -o {basedir}{pic}")

        os.system("clear")

    _API.add_credentials(credentials)
    if start:
        _API.start()

    # After this part, the API is logging in in the background and we can proceed
    prompted, main_command, user_input = cli.process_cli_args()

    try:
        main_loop(prompted, main_command, user_input, your_id, start)
    except KeyboardInterrupt:
        # If ctrl+c pressed before a mode is selected, thread will never join
        # Get it to join first so that modes still work
        _API.await_login()
        main(start=False)

def main_loop(prompted, main_command, user_input, your_id=None, start=True):
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
            ArtistModeLoop(prompted, user_input).start(start)

        elif main_command == "2":
            ViewPostModeLoop(prompted, user_input).start(start)

        elif main_command == "3":
            if your_id and not user_input: # your_id stored in config file
                ans = input("Do you want to use the Pixiv ID saved in your config?\n")
                if ans in {"y", ""}:
                    FollowingUserModeLoop(prompted, your_id).start(start)

            # If your_id not stored, or if ans is no, or if id provided, via cli
            FollowingUserModeLoop(prompted, user_input).start(start)

        elif main_command == "4":
            SearchUsersModeLoop(prompted, user_input).start(start)

        elif main_command == "5":
            IllustFollowModeLoop().start(start)

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

    def start(self, start):
        """Ask for further info if not provided; wait for log in then proceed"""
        while True:
            if self._prompted and not self._user_input:
                self._prompt_url_id()
                self._process_url_or_input()
                self._validate_input()
                os.system("clear")

            if start:
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
            # If ctrl+c pressed before a mode is selected, thread will never join
            # Get it to join first so that modes still work
            _API.await_login()
            time.sleep(2)
            main(start=False)

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
        main(start=False)


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
    def start(self, start):
        while True:
            if start:
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
                Path(self._download_path).rmdir()
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
    def _pixivrequest(self):
        raise NotImplementedError

    def _download_pbar(self):
        pbar = tqdm(total=len(self._current_page_illusts), smoothing=0)
        download.download_page(self._current_page_illusts, self._download_path,
                               pbar=pbar)
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
        return _API.artist_gallery_request(self._artist_user_id)

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
        return _API.illust_follow_request(restrict='private') # Publicity

    def _instantiate(self):
        self.gallery = ui.IllustFollowGallery(
            self._current_page_illusts,
            self._current_page,
            self._current_page_num,
            self._all_pages_cache,
        )
        prompt.gallery_like_prompt(self.gallery)
        # After backing
        main(start=False)

def view_post_mode(image_id):
    """
    Fetch all the illust info, download it in the correct directory, then display it.
    If it is a multi-image post, download the next image
    Else or otherwise, open image prompt
    """
    print("Fetching illust details...")
    try:
        post_json = _API.protected_illust_detail(image_id)["illust"]
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

    download.download_core(large_dir, url, filename)
    utils.display_image_vp(f"{large_dir}{filename}")

    # Download the next page for multi-image posts
    if number_of_pages != 1:
        download.async_download_spinner(large_dir, page_urls[:2])
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

if __name__ == "__main__":
    main()
