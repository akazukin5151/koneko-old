# koneko [![GPLv3 license](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.txt) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Browse pixiv in the terminal using kitty's icat to display images (in the terminal!)

![Gallery view](pics/gallery_view.png)

![Gallery view_square_medium](pics/gallery_view_square_medium.png)

![Image_view](pics/image_view.png)

Requires [kitty](https://github.com/kovidgoyal/kitty) on Linux. It uses the magical `kitty +kitten icat` 'kitten' to display images. For more info see the [kitty documentation](https://sw.kovidgoyal.net/kitty/kittens/icat.html). Actually, `lscat.py` uses [pixcat](https://github.com/mirukana/pixcat), which is a Python API for icat.

**Why the name Koneko?** Koneko (こねこ) means kitten, which is what `icat` is, a kitty `+kitten`


# Features
See the [manual](#manual) for more details

1. Artist illustrations gallery
    * Enter the post's coordinates to open it in image view. Coordinates are in the form `xy` where x is column and y is row.
    * Next and previous pages
2. Image view
    * View an image in large resolution
    * Browse through different images in a multi-image post.
3. Browse the artists you are following, and view their illustrations (goes to 1)
4. Search for an artist, and view their illustrations (goes to 1)
* Both gallery and image views can:
    * Download an image([PixivUtil](https://github.com/Nandaka/PixivUtil2/) would be more suitable for batch download) in full resolution
    * Open post in browser


# Rationale
* Terminal user interfaces are minimalist, fast, and doesn't load Javascript that slows down your entire browser or track you
    * Image loading is *so* much faster, especially if you don't delete the cache

I get 32 trackers on Pixiv. Plus, you have to disable ublock if you ever get logged out

<a href="url"><img src="pics/pixiv_ublock.png" height="350"></a>

* TUIs make you cool
* TUIs *with embedded pictures* make you even cooler
* TUIs embedded with pictures of cute anime girls make you the coolest
* Keyboard driven
* Familiar, vim-like key sequences
* I use arch btw


# Usage
0. Install [kitty](https://github.com/kovidgoyal/kitty)
1. `mkdir ~/.config/koneko/ && touch ~/.config/koneko/config.ini`
2. `vim ~/.config/koneko/config.ini` and fill it out with your pixiv username and password like this:

```ini
[Credentials]
Username = XXX
Password = XXX
# Your pixiv ID is optional. If you fill it in, you don't have to
# paste it every time you go to mode 3
ID = XXX
```

3. Run:
```sh
# Use latest master branch
git clone https://github.com/twenty5151/koneko.git

# Or use this for the latest 'stable' release
# Update the tag for the latest released version
git clone -b 'v0.1' --depth 1 https://github.com/twenty5151/koneko.git`

cd koneko
pip install -r requirements.txt --upgrade
python koneko.py
```

**NOTE:** requirements.txt will install a newer, unreleased version of pixivpy (from its master branch), because mode 4 relies on a new feature that hasn't been uploaded to Pypi yet. Artist search was not supported by pixivpy, but I made a [PR](https://github.com/upbit/pixivpy/pull/123) to add that feature and it has been merged. However, there has been no new release yet.

4. There are four modes of operation:
    1. Show artist illustrations: equivalent to going to the artist page
    2. View post: equivalent to going directly to a post (think getting a 'sauce' link)
    3. View artists you are following. (Or any other user ID)
    4. Search for artist/user.

Enter digits 1-4 to proceed. Then, paste in a valid pixiv ID or url. See below for url examples. Pressing ctrl+c in a prompt bring you back to the 'home' prompt.

Alternatively, you can supply a pixiv url as a command line argument to `koneko.py`, bypassing the first interactive prompt. The pixiv url must be either the url of the artist's page, or a pixiv post. Example:

```sh
python koneko.py https://www.pixiv.net/en/users/2232374 # Mode 1
python koneko.py https://www.pixiv.net/en/artworks/78823485 # Mode 2
python koneko.py -f https://www.pixiv.net/en/users/2232374 # Mode 3
python koneko.py "raika9" # Mode 4
```

# Roadmap

## Features

* Image view should preview the next few images in multi-image posts
* For multi-image posts in image view, enter a number to jump to the post's page
* Option to use pillow or wand to edit numbers on pics
* Support [ueberzug](https://github.com/seebye/ueberzug)

## Speed

* Cache API.user_illusts()
* If files already downloaded, show them immediately before logging in

# Manual

```
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
    q                  -- exit

Examples:
    i09   --->  Display the ninth image in image view (must have leading 0)
    i10   --->  Display the tenth image in image view
    O9    --->  Open the ninth image's post in browser
    D9    --->  Download the ninth image, in large resolution

    25    --->  Display the image on column 2, row 5 (index starts at 1)
    d25    --->  Open the image on column 2, row 5 (index starts at 1) in browser
    o25    --->  Download the image on column 2, row 5 (index starts at 1)
```

```
Image view commands (No need to press enter):
    b -- go back to the gallery
    n -- view next image in post (only for posts with multiple pages)
    p -- view previous image in post (same as above)
    d -- download this image
    o -- open pixiv post in browser
    h -- show this help

    q -- quit (with confirmation)
```

```
User view commands (No need to press enter):
    n -- view next page
    p -- view previous page
    h -- show this help
    q -- quit (with confirmation)
```

## lscat rewrite

**Note on terminology**: [lsix](https://github.com/hackerb9/lsix/) is the name of the original shell script I used, which uses sixel. I edited it to use icat and renamed it **lscat**. Then I rewrote it with python, which is named **lscat.py**. **lscat.py is the default renderer and the fastest.**

You might have problems with image positioning with lscat.py. I wrote it to fit my screen and my terminal size, so there is no functionality to adjust for different terminal size. There are also 'magic numbers' (numbers that just exist) around. If you encounter problems, there are four things you can do, in order of least to most effort:

* Revert to the old lscat shell script.

    1. In `show_artist_illusts()` (`utils.py`), change `renderer="lscat"` to `renderer="lscat old"`.

* Revert to the original lsix script. This would be more reliable than 1., because it has all the checks for terminal sizes. However, you cannot use kitty; xterm works.

    1. Make sure you're cd'ed into the koneko dir, then `curl "https://raw.githubusercontent.com/hackerb9/lsix/master/lsix" -o legacy/lsix && chmod +x legacy/lsix`

    2. In `show_artist_illusts()` (`utils.py`), change `renderer="lscat"` to `renderer="lsix"`.

* Adjust the 'magic numbers'. They are commented in `lscat.py`.
* You can contribute to `lscat.py` by checking terminal size and doing all the maths and send a PR

| Feature  | lscat.py | legacy/lscat | [hackerb9/lsix](https://github.com/hackerb9/lsix/) |
| --- | --- | --- | --- |
| Speed  | Fastest | Slow\* | Slow\*
| Reliability (eg, resizing the terminal) | Poor | Medium | Good
| Adaptability (eg, other terminals, tmux) | Poor | Poor | Medium

\* lsix will appear faster because the images are much smaller. Once you scale them up, lsix will be the slowest.


## `Dev` branch

Use the `dev` branch for latest features/fixes that will be merged to `master` soon:

```sh
git clone -b dev https://github.com/twenty5151/koneko.git
```

## Unit tests
Use `pytest testing.py`


Here's a random shell command to get (but not download) and display any pixiv image url:
```sh
curl -e 'https://www.pixiv.net' "https://i.pximg.net/img-original/img/2019/12/21/20/13/12/78403815_p0.jpg" | kitty +kitten icat --align left --place 800x480@0x5
```
