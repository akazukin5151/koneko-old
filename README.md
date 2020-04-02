# koneko [![GPLv3 license](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.txt) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
Browse pixiv in the terminal using kitty's icat to display images (in the terminal!)

![Gallery view](gallery_view.png)

![Image_view](image_view.png)

Requires [kitty](https://github.com/kovidgoyal/kitty) on Linux. It uses the magical `kitty +kitten icat` 'kitten' to display images. For more info see the [kitty documentation](https://sw.kovidgoyal.net/kitty/kittens/icat.html). Actually, `lscat.py` uses [pixcat](https://github.com/mirukana/pixcat), which is a Python API for icat.

**Why the name Koneko?** Koneko (こねこ) means kitten, which is icat is, a kitty +kitten

**This is still in alpha stages**. Once I finally ~~get async working~~ and ~~rewrite lscat~~ and refactor+stabilize it will be in beta (see [milestones](https://github.com/twenty5151/koneko/milestone/1)). All PRs are welcome. The current master branch is (relatively more) stable. The `testing` branch is for the latest features, fixes, and super instability. The `dev` branch is a more stable branch where commits from `testing` gets merged nightly (or less frequently).

## lscat rewrite

It's not possible to print the post title with the new lscat (without using the slow ImageMagick). So I just put column numbers in the bottom. You can count! Gallery prompt will now recognise coordinates `2,3` instead of `6` (both accesses the sixth picture) to assist in counting.


# Usage
0. Install [kitty](https://github.com/kovidgoyal/kitty), and all other requirements (just see list of imports)
    * [pixivpy](https://github.com/upbit/pixivpy): `pip install pixivpy`
    * [pixcat](https://github.com/mirukana/pixcat): `pip install pixcat`
1. `mkdir ~/.config/koneko/ && touch ~/.config/koneko/config.ini`
2. `vim ~/.config/koneko/config.ini` and fill it out with your pixiv username and password like this:

```ini
[Credentials]
Username = XXX
Password = XXX
```

3. 
```sh
git clone https://github.com/twenty5151/koneko.git && cd koneko
python koneko.py
```

Alternatively, you can supply a pixiv url as a command line argument to `koneko.py`, bypassing the first interactive prompt. The pixiv url must be either the url of the artist's page, or a pixiv post. (Contains "artworks" and "member" respectively). Example:

```sh
python koneko.py https://www.pixiv.net/en/users/2232374
```

```sh
python koneko.py https://www.pixiv.net/en/artworks/78823485
```

## `Dev` branch

Use the `dev` branch for latest features/fixes that will be merged to `master` soon:

```sh
git clone -b dev https://github.com/twenty5151/koneko.git
```


# Features
* Artist illustration gallery (equivalent to the illustrations tab on the artist's profile)
    * Enter a number to open a post, or its coordinates in the form `x,y` (no brackets needed) or `x y` (separate with a space)
* Image view: view an image in large resolution
* Image view can also browse through different images in a multi-image post.
* Both gallery and image views can:
    * Download a post ([PixivUtil](https://github.com/Nandaka/PixivUtil2/) would be more suitable for batch download)
    * Open post in browser


# Rationale
* Terminal user interfaces are minimalist, fast, and doesn't load Javascript that slows down your entire browser or track you
    * Image loading is *so* much faster

I get 32 trackers on Pixiv. Plus, you have to disable ublock if you ever get logged out

![pixiv_ublock](pixiv_ublock.png)

* TUIs make you cool
* TUIs *with embedded pictures* make you even cooler
* TUIs embedded with pictures of cute anime girls make you the coolest
* Keyboard driven
* I use arch btw


# Developer manual
As of now there are two modes of operation:

1. Show artist illustrations: equivalent to going to the artist page in pixie
2. View post: equivalent to going directly to a post (think getting a 'sauce' link)

Those two modes are represented by:

1. `artist_illusts_mode()`
2. `view_post_mode()`

* Frontend, interactive functions (with an input()); has word 'prompt'
    * `begin_prompt()`
    * `artist_user_id_prompt()`
    * `gallery_prompt()`
    * `image_prompt()`

* Non interactive functions:
    * Not visible to user (backend):
        * `setup()`
        * `download_illusts()`   (only if 'downloading img' messages are disabled)
        * `download_large()`, `download_large_vp()`
            * `make_path_and_download()`
        * `download_full()`
            * `download_full_core()`
            * `get_url_and_filename()`

    * Visible to user. Leads to (--->) an interactive prompt:
        * `show_artist_illusts()` ---> `gallery_prompt()`
        * `open_image()` ---> `image_prompt()`
        * `open_image_vp()` ---^

Misc functions:
* `main()` starts `setup()` asynchronously, so it log ins in the background while the user pick between modes and enters the IDs
* `timer()` is just a custom decorator to roughly profile the code
* `cd()` is a context manager for changing current dir then restoring the old one

Here's a random shell command to get (but not download) and display any pixiv image url
`curl -e 'https://www.pixiv.net' "https://i.pximg.net/img-original/img/2019/12/21/20/13/12/78403815_p0.jpg" | convert - -geometry 800x480 jpg:- | kitty +kitten icat --align left --place 800x480@0x5`

## Unit tests
The few lines of unit tests can be ran with `pytest testing.py`

