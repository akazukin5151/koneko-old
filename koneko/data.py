"""Stores json data from the api. Acts as a frontend to access data in a single line
TODO: The ui classes would never need to interact directly with the api
as they should focus on responding to user input and print/display.
"""
from koneko import pure

class GalleryJson:
    def __init__(self, raw):
        self.raw = raw
        self.all_pages_cache = {"1": self.raw}
        self.current_page_illusts = self.raw['illusts']

        self.titles = pure.post_titles_in_page(self.current_page_illusts)

    def current_page(self, current_page_num=1):
        return self.all_pages_cache[str(current_page_num)]

    def current_illusts(self, current_page_num=1):
        return self.all_pages_cache[str(current_page_num)]['illusts']

    def post_json(self, current_page_num, post_number):
        return self.current_illusts(current_page_num)[post_number]

    def image_id(self, current_page_num, number):
        return self.current_illusts(current_page_num)[number]["id"]

    def update_current_illusts(self, current_page_num):
        self.current_page_illusts = self.current_illusts(current_page_num)

    def cached_pages(self):
        return self.all_pages_cache.keys()

    def next_url(self, current_page_num):
        return self.all_pages_cache[str(current_page_num)]["next_url"]


class ImageJson:
    def __init__(self, raw, image_id):
        self.raw = raw
        self.url = pure.url_given_size(self.raw, "large")
        self.filename = pure.split_backslash_last(self.url)
        self.artist_user_id = self.raw["user"]["id"]
        self.img_post_page_num = 0

        self.number_of_pages, self.page_urls = pure.page_urls_in_post(post_json, "large")
        if self.number_of_pages == 1:
            self.downloaded_images = None
            self.large_dir = f"{KONEKODIR}/{self.artist_user_id}/individual/"
        else:
            self.download_images = list(map(pure.split_backslash_last,
                                            self.page_urls[:2]))
            # So it won't be duplicated later
            self.large_dir = f"{KONEKODIR}/{self.artist_user_id}/individual/{image_id}/"


        # Public attributes being used:
        self.current_url = self.page_urls[self.img_post_page_num]
        self.image_filename = self.download_images[self.img_post_page_num]
        self.filepath = "".join([self.download_path, self.image_filename])
        self.next_img_url = self.page_urls[self.img_post_page_num + 1]


class UserJson:
    def __init__(self, raw, page_num):
        self.raw = raw
        self.next_url = self.raw['next_url']
        page = udata.raw["user_previews"]

        ids = list(map(self._user_id, page))
        self.ids_cache.update({page_num: ids})

        self.names = list(map(self._user_name, page))
        self.names_cache.update({page_num: self._names})

        self.profile_pic_urls = list(map(self._user_profile_pic, page))

        # max(i) == number of artists on this page
        # max(j) == 3 == 3 previews for every artist
        self.image_urls = [page[i]['illusts'][j]['image_urls']['square_medium']
                            for i in range(len(page))
                            for j in range(len(page[i]['illusts']))]


    def artist_user_id(self, page_num, selected_user_num):
        return self.ids_cache[page_num][selected_user_num]

    def names(self, page_num):
        return self.names_cache[page_num]

    def all_urls(self):
        return self.profile_pic_urls + self.image_urls

    def all_names(self):
        preview_names_ext = map(pure.split_backslash_last, self.image_urls)
        preview_names = [x.split('.')[0] for x in preview_names_ext]
        return self.names + preview_names

    def splitpoint(self):
        return len(self.profile_pic_urls)

    @staticmethod
    def _user_id(json):
        return json["user"]["id"]

    @staticmethod
    def _user_name(json):
        return json["user"]["name"]

    @staticmethod
    def _user_profile_pic(json):
        return json["user"]["profile_image_urls"]["medium"]
