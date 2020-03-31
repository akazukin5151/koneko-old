# koneko [![GPLv3 license](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.txt) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
Browse pixiv in the terminal using kitty's icat to display images (in the terminal!)

![Gallery view](gallery_view.png)

![Image_view](image_view.png)

Requires [kitty](https://github.com/kovidgoyal/kitty) on Linux. It uses the magical `kitty +kitten icat` 'kitten' to display images. For more info see the [kitty documentation](https://sw.kovidgoyal.net/kitty/kittens/icat.html)

**Why the name Koneko?** Koneko (こねこ) means kitten, which is icat is, a kitty +kitten

Uses [pixivpy](https://github.com/upbit/pixivpy/), install with `pip install pixivpy`

Right now it's slow because it adapts [lsix](https://github.com/hackerb9/lsix/), which relies on ImageMagick. I started with lsix, using libsixel. But it used too much memory and switching around was slow. Plus I didn't want to switch away from kitty. Eventually there will be a rewrite of lsix (now [lscat](https://github.com/twenty5151/koneko/blob/master/lscat)) to remove dependency on ImageMagick and speed it up a lot.

As of now it's in alpha stages. Once I finally get asyncio working it will be in beta. All PRs are welcome. The current master branch is stable, but slow.


# Usage
0. Install [kitty](https://github.com/kovidgoyal/kitty), ImageMagick, and all requirements (just see list of imports)
1. `mkdir ~/.config/koneko/ && touch ~/.config/koneko/config.ini`
2. `vim ~/.config/koneko/config.ini` and fill it out with your pixiv username and password like this:

```
[Credentials]
Username = XXX
Password = XXX
```

3. `git clone https://github.com/twenty5151/koneko.git && cd koneko`
4. `python koneko.py`

Alternatively, you can supply a pixiv url as a command line argument to `koneko.py`, bypassing the first interactive prompt. The pixiv url must be either the url of the artist's page, or a pixiv post. (Contains "artworks" and "member" respectively). Example:

```python koneko.py https://www.pixiv.net/en/users/2232374```

```python koneko.py https://www.pixiv.net/en/artworks/78823485```

# Developer manual
As of now there are two modes of operation:

1. Show artist illustrations: equivalent to going to the artist page in pixie
2. View post: equivalent to going directly to a post (think getting a 'sauce' link)

Those two modes are represented by:

1. `artist_illusts_mode()`
2. `view_post_mode()`

Frontend, interactive functions (with an input()); has word 'prompt'

* `begin_prompt()`
* `artist_user_id_prompt()`
* `gallery_prompt()`
* `image_prompt()`

Non interactive functions:

* Not visible to user (backend):
    * `setup()`
    * `download_illusts()`   (only if 'downloading img' messages are disabled)
    * `download_large()`, `download_large_vp()`
        * `make_path_and_download()`
    * `download_full()`
        * `download_full_core()`
        * `get_url_and_filename()`

* Visible to user. Non-interactive function leads to (--->) an interactive prompt:
    * `show_artist_illusts()` ---> `gallery_prompt()`
    * `open_image()` ---> `image_prompt()`
    * `open_image_vp()` ---^

Misc functions:
* `main()` starts `setup()` asynchronously, so it log ins in the background while the user pick between modes and enters the IDs
* `timer()` is just a custom decorator to roughly profile the code
* `cd()` is a context manager for changing current dir then restoring the old one

Here's a random shell command to get (but not download) and display any pixiv image url
`curl -e 'https://www.pixiv.net' "https://i.pximg.net/img-original/img/2019/12/21/20/13/12/78403815_p0.jpg" | convert - -geometry 800x480 jpg:- | kitty +kitten icat --align left --place 800x480@0x5`
