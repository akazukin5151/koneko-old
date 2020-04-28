"""Handles user interaction inside all the modes. No knowledge of API needed"""

import os
from pathlib import Path
from abc import ABC, abstractmethod

import funcy
from tqdm import tqdm

from koneko import main
from koneko import pure
from koneko import lscat
from koneko import colors
from koneko import utils
from koneko import prompt
from koneko import download

KONEKODIR = Path("~/.local/share/koneko/cache").expanduser()

class LastPageException(ValueError):
    pass

class AbstractGallery(ABC):
    def __init__(self, current_page_illusts, current_page, current_page_num,
                 all_pages_cache):
        self._current_page_illusts = current_page_illusts
        self._current_page = current_page
        self._current_page_num = current_page_num
        self._all_pages_cache = all_pages_cache
        # Defined in self.view_image
        self._post_json: 'PostJson'
        self._selected_image_num: int
        # Defined in child classes
        self._main_path: str

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
        download.download_image_verified(post_json=post_json)

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

        image = Image(image_id, artist_user_id, self._current_page_num,
                      False, multi_image_info)
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
    def _pixivrequest(self, **kwargs):
        raise NotImplementedError

    def _prefetch_next_page(self):
        # print("   Prefetching next page...", flush=True, end="\r")
        next_url = self._all_pages_cache[str(self._current_page_num)]["next_url"]
        if not next_url:  # this is the last page
            raise LastPageException

        parse_page = main._API.parse_next(next_url)
        next_page = self._pixivrequest(**parse_page)
        self._all_pages_cache[str(self._current_page_num + 1)] = next_page
        current_page_illusts = next_page["illusts"]

        download_path = f"{self._main_path}/{self._current_page_num+1}/"
        if not Path(download_path).is_dir():
            pbar = tqdm(total=len(current_page_illusts), smoothing=0)
            download.download_page(
                current_page_illusts, download_path, pbar=pbar
            )
            pbar.close()

    def reload(self):
        ans = input("This will delete cached images and redownload them. Proceed?\n")
        if ans == "y" or not ans:
            os.system(f"rm -r {self._main_path}") # shutil.rmtree is better
            self._all_pages_cache = {} # Ensures prefetch after reloading
            self._back()
        else:
            # After reloading, back will return to the same mode again
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
        h                  -- show keybindings
        m                  -- show this manual
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

    def _pixivrequest(self, **kwargs):
        return main._API.artist_gallery_parse_next(**kwargs)

    def _back(self):
        # After user 'back's from image prompt, start mode again
        main.ArtistGalleryMode(self._artist_user_id, self._current_page_num,
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
            if not selected_image_num:
                print("Invalid number!")
                prompt.gallery_like_prompt(self) # Go back to while loop
            else:
                self.view_image(selected_image_num)

    @staticmethod
    def help():
        print("".join(
            colors.base1 + "view " + colors.base2
            + ["view ", colors.m, "anual; ",
               colors.b, "ack\n"]))


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
        h                  -- show keybindings
        m                  -- show this manual
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

    def _pixivrequest(self, **kwargs):
        return main._API.illust_follow_request(**kwargs)

    def go_artist_gallery_coords(self, first_num, second_num):
        selected_image_num = pure.find_number_map(int(first_num), int(second_num))
        if selected_image_num is False: # 0 is valid!
            print("Invalid number!")
        else:
            self.go_artist_gallery_num(selected_image_num)

    def go_artist_gallery_num(self, selected_image_num):
        """Like self.view_image(), but goes to artist mode instead of image"""
        self._selected_image_num = selected_image_num
        self._current_page = self._all_pages_cache[str(self._current_page_num)]
        self._current_page_illusts = self._current_page["illusts"]
        self._post_json = self._current_page_illusts[selected_image_num]

        artist_user_id = self._post_json['user']['id']
        main.ArtistGalleryMode(artist_user_id)
        # Gallery prompt ends, user presses back
        self._back()

    def _back(self):
        # User 'back's out of artist gallery, start current mode again
        main.IllustFollowMode(self._current_page_num, self._all_pages_cache)

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
            if not selected_image_num:
                print("Invalid number!")
                prompt.gallery_like_prompt(self) # Go back to while loop
            else:
                self.view_image(selected_image_num)

    @staticmethod
    def help():
        print("".join(colors.base1 + [
            colors.a, "view artist's illusts; ",
            colors.n, "ext page;\n",
            colors.p, "revious page; ",
            colors.r, "eload and re-download all; ",
            colors.q, "uit (with confirmation); ",
            "view ", colors.m, "anual\n"]))

def display_image(post_json, artist_user_id, number_prefix, current_page_num):
    """
    Opens image given by the number (medium-res), downloads large-res and
    then display that.

    Parameters
    ----------
    number_prefix : int
        The number prefixed in each image
    post_json : JsonDict
    artist_user_id : int
    current_page_num : int
    """
    search_string = f"{str(number_prefix).rjust(3, '0')}_"

    # LSCAT
    os.system("clear")
    arg = f"{KONEKODIR}/{artist_user_id}/{current_page_num}/{search_string}*"
    os.system(f"kitty +kitten icat --silent {arg}")

    url = pure.url_given_size(post_json, "large")
    filename = pure.split_backslash_last(url)
    large_dir = f"{KONEKODIR}/{artist_user_id}/{current_page_num}/large/"
    download.download_core(large_dir, url, filename)

    # BLOCKING: imput is blocking, will not display large image until input
    # received

    # LSCAT
    os.system("clear")
    arg = f"{KONEKODIR}/{artist_user_id}/{current_page_num}/large/{filename}"
    os.system(f"kitty +kitten icat --silent {arg}")


class Image:
    """
    Image view commands (No need to press enter):
        b -- go back to the gallery
        n -- view next image in post (only for posts with multiple pages)
        p -- view previous image in post (same as above)
        d -- download this image
        o -- open pixiv post in browser
        h -- show keybindings
        m -- show this manual

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
            # Starts from 0
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
        download.download_image_verified(url=large_url, filename=filename,
                                         filepath=filepath)

    def next_image(self):
        if not self._page_urls:
            print("This is the only page in the post!")
        elif self._img_post_page_num + 1 == self._number_of_pages:
            print("This is the last image in the post!")

        else:
            self._img_post_page_num += 1  # Be careful of 0 index
            self._go_next_image()

    def _go_next_image(self):
        """
        Downloads next image if not downloaded, open it, download the next image
        in the background
        """
        # IDEAL: image prompt should not be blocked while downloading
        # But I think delaying the prompt is better than waiting for an image
        # to download when you load it

        # First time from gallery; download next image
        if self._img_post_page_num == 1:
            url = self._page_urls[self._img_post_page_num]
            self._downloaded_images = map(pure.split_backslash_last,
                                          self._page_urls[:2])
            self._downloaded_images = list(self._downloaded_images)
            download.async_download_spinner(self._download_path, [url])

        utils.display_image_vp("".join([
            self._download_path,
            self._downloaded_images[self._img_post_page_num]
        ]))

        # Downloads the next image
        try:
            next_img_url = self._page_urls[self._img_post_page_num + 1]
        except IndexError:
            pass  # Last page
        else:  # No error
            self._downloaded_images.append(
                pure.split_backslash_last(next_img_url)
            )
            download.async_download_spinner(self._download_path, [next_img_url])

        print(f"Page {self._img_post_page_num+1}/{self._number_of_pages}")

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
            main.ArtistGalleryMode(self._artist_user_id, self._current_page_num)
            # After backing
            main.main(start=False)
        # Else: image prompt and class ends, goes back to previous mode


class Users(ABC):
    """
    User view commands (No need to press enter):
        n -- view next page
        p -- view previous page
        r -- delete all cached images, re-download and reload view
        h -- show keybindings
        m -- show this manual
        q -- quit (with confirmation)

    """

    @abstractmethod
    def __init__(self, user_or_id):
        # Defined in child classes
        self._main_path: str

        self._input = user_or_id
        self._offset = 0
        self._page_num = 1
        self._download_path = f"{self._main_path}/{self._input}/{self._page_num}"
        self._names_cache = {}
        self._ids_cache = {}
        self._show = True
        # Defined in _parse_user_infos():
        self._next_url: 'Dict[str, str]'
        self._ids: 'List[str]'
        self._names: 'List[str]'
        self._profile_pic_urls: 'List[str]'
        self._image_urls = 'List[str]'

    def start(self):
        # It can't show first (including if cache is outdated),
        # because it needs to print the right message
        # Which means parsing is needed first
        self._parse_and_download()
        if self._show:
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

        # Similar to logic in GalleryLikeMode (_init_download())...
        if not Path(self._download_path).is_dir():
            self._download_pbar(all_urls, preview_path, all_names, splitpoint)

        elif not all_names[0] in sorted(os.listdir(self._download_path))[0]:
            print("Cache is outdated, reloading...")
            # Remove old images
            os.system(f"rm -r {self._download_path}") # shutil.rmtree is better
            self._download_pbar(all_urls, preview_path, all_names, splitpoint)
            self._show = True

    def _download_pbar(self, all_urls, preview_path, all_names, splitpoint):
        pbar = tqdm(total=len(all_urls), smoothing=0)
        download.async_download_core(
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
            [os.rename(f"{self._download_path}/previews/{pic}",
                       f"{self._download_path}/{pic}")
             for pic in to_move]


    @abstractmethod
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

            # LSCAT
            lscat.Card(
                self._download_path,
                f"{self._main_path}/{self._input}/{self._page_num}/previews/",
                messages=names_prefixed,
            ).render()

    def _prefetch_next_page(self):
        oldnum = self._page_num

        if self._next_url:
            self._offset = main._API.parse_next(self._next_url)["offset"]
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
        main.ArtistGalleryMode(artist_user_id)
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


class SearchUsers(Users):
    """
    Inherits from Users class, define self._input as the search string (user)
    Parent directory for downloads should go to search/
    """
    def __init__(self, user):
        self._main_path = f"{KONEKODIR}/search"
        super().__init__(user)

    def _pixivrequest(self):
        return main._API.search_user_request(self._input, self._offset)

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

    def _pixivrequest(self):
        return main._API.following_user_request(self._input, self._publicity, self._offset)
