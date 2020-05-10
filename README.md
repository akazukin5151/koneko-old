# koneko [![GPLv3 license](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.txt)

Browse pixiv in the terminal using kitty's icat to display images (in the terminal!)

Gallery view, square medium
![Gallery view_square_medium1](pics/gallery_view_square_medium1.png)
![Gallery view_square_medium2](pics/gallery_view_square_medium2.png)
Gallery view, medium (non-square)
![Gallery view](pics/gallery_view.png)
Image view
![Image_view](pics/image_view.png)
Artist search (artist profile picture on the left, 3 previews on right)
![artist_search](pics/artist_search.png)
View artists you're following
![following_users_view](pics/following_users_view.png)

Requires [kitty](https://github.com/kovidgoyal/kitty) on Linux. It uses the magical `kitty +kitten icat` 'kitten' to display images. For more info see the [kitty documentation](https://sw.kovidgoyal.net/kitty/kittens/icat.html). Actually, `lscat.py` uses [pixcat](https://github.com/mirukana/pixcat), which is a Python API for icat.

**Why the name Koneko?** Koneko (こねこ) means kitten, which is what `icat` is, a kitty `+kitten`


# Features
See the [manual](#manual) for more details

1. Artist illustrations gallery ([ex](https://www.pixiv.net/bookmark.php?type=user))
    * Enter the post's coordinates to open it in image view. Coordinates are in the form `xy` where x is column and y is row.
    * Next and previous pages
2. Image view ([ex](https://www.pixiv.net/en/artworks/78823485))
    * View an image in large resolution
    * Browse through different images in a multi-image post.
3. View artists you are following ([ex](https://www.pixiv.net/bookmark.php?type=user))
4. Search for an artist ([ex](https://www.pixiv.net/search_user.php?nick=raika9&s_mode=s_usr))
5. View new illustrations from all the artists you are following ([ex](https://www.pixiv.net/bookmark_new_illust.php))
* Both gallery and image views can:
    * Download an image([PixivUtil](https://github.com/Nandaka/PixivUtil2/) would be more suitable for batch download) in full resolution
    * Open post in browser


# Rationale
* Terminal user interfaces are minimalist, fast, and doesn't load Javascript that slows down your entire browser or track you
    * Image loading is *so* much faster, especially if you don't delete the cache

I get 32 trackers on Pixiv. Plus, you have to disable ublock if you ever get logged out

<a href="url"><img src="pics/pixiv_ublock.png" height="350"></a>

The mobile app even directly tells you Google "and our 198 partners" "collect and use data"! See [prompt 1](https://raw.githubusercontent.com/twenty5151/koneko/master/pics/ads1.png), [prompt 2](https://raw.githubusercontent.com/twenty5151/koneko/master/pics/ads2.png) (Github can't render the images correctly for some reason) and this [list](#trackers)

* TUIs make you cool
* TUIs *with embedded pictures* make you even cooler
* TUIs embedded with pictures of cute anime girls make you the coolest
* Keyboard driven
* Familiar, vim-like key sequences
* I use arch btw


# Installation
See also: [manual installation](#manual-installation)

0. Install [kitty](https://github.com/kovidgoyal/kitty)
1. `pip install koneko` (or if you use [conda](#conda)...):
2. Run `koneko`

If it crashes (it shouldn't), it might be because pip didn't 'install' the welcome pictures, *and* the script failed to download them for some reason. Try:

```sh
mkdir -p ~/.local/share/koneko/pics
curl -s https://raw.githubusercontent.com/twenty5151/koneko/master/pics/71471144_p0.png -o ~/.local/share/koneko/pics/71471144_p0.png
curl -s https://raw.githubusercontent.com/twenty5151/koneko/master/pics/79494300_p0.png -o ~/.local/share/koneko/pics/79494300_p0.png
```

# Usage
There are five modes of operation:
1. View artist illustrations ([ex](https://www.pixiv.net/bookmark.php?type=user))
2. View a post ([ex](https://www.pixiv.net/en/artworks/78823485))
3. View the artists that you are following (or any other user ID) ([ex](https://www.pixiv.net/bookmark.php?type=user))
4. Search for artist/user ([ex](https://www.pixiv.net/search_user.php?nick=raika9&s_mode=s_usr))
5. View newest illustrations from artists you're following ([ex](https://www.pixiv.net/bookmark_new_illust.php))

Enter digits 1-5 to proceed. If prompted, paste in an appropriate pixiv ID or url. See below for url examples.

Alternatively, you can supply a pixiv url as a command line argument, bypassing the first interactive prompt. The pixiv url must be either the url of the artist's page, or a pixiv post. Example:

```sh
koneko https://www.pixiv.net/en/users/2232374 # Mode 1
koneko https://www.pixiv.net/en/artworks/78823485 # Mode 2
koneko f https://www.pixiv.net/en/users/2232374 # Mode 3
koneko "raika9" # Mode 4
koneko 5 # Mode 5
```
For more details refer to the [manual](#manual).

# Roadmap

## Features

* Show large version in image view - useful for 'landscape' pictures
* For multi-image posts in image view, enter a number to jump to the post's page
* Image view should preview the next few images in multi-image posts (but either it blocks the prompt or the prompt blocks)
* Image and User views should use lscat.py to render so alternate renderers can be used
* Option to use pillow or wand to edit numbers on pics
* Support [ueberzug](https://github.com/seebye/ueberzug)

## Speed

* Display each image as soon as they finish downloading (but due to lscat limitations, only one page at a time). Requires "integrating" (read: basically rewriting) lscat.py and threaded download functions

# FAQ
* Pixiv keeps emailing me saying I've logged in, every time I use this app!

That's because cookies aren't stored so you log in everytime with a new session. Looking at [PixivUtil's cookie implementation](https://github.com/Nandaka/PixivUtil2/blob/master/PixivBrowserFactory.py), it would be easier to base this app on PixivUtil for downloads, than to write it myself (currently, it's based on the [pixivpy](https://github.com/upbit/pixivpy/) api). The problems with this, other than being a huge time and effort investment, is that koneko uses info from the requests, such as number of pages.
I'd like to fix this but I'd rather not use mechanize but I don't know how to do it either way.

* What operating systems does it support?

It supports all OSes that kitty supports, which means Linux and macOS. It should work on macOS, but I don't have a test device. If you do, please contribute!


## Image rendering with lscat

**Note on terminology**: [lsix](https://github.com/hackerb9/lsix/) is the name of the original shell script I used, which uses sixel. I edited it to use icat and renamed it **lscat**. Then I rewrote it with python, which is named **lscat.py**. **lscat.py is the default renderer and the fastest.**

**Note on installation**: if you edit it, you'll need to install it manually (or send a PR), see [manual installation](#manual-installation)

You might have problems with image positioning with lscat.py. I wrote it to fit my screen and my terminal size, so there is no functionality to adjust for different terminal size. There are also 'magic numbers' (numbers that just exist) around. If you encounter problems, there are four things you can do, in order of least to most effort:

* Revert to the old lscat shell script.

    1. In `show_artist_illusts()` (`utils.py`), change `renderer="lscat"` to `renderer="lscat old"`.
    2. Note that Image and User views (mode 2, 3, 4) still use lscat. The responsible code are annotated with a `# LSCAT` comment.

* Revert to the original lsix script. This would be more reliable than 1., because it has all the checks for terminal sizes. However, you cannot use kitty; xterm works.

    1. Make sure you're cd'ed into the koneko dir, then `curl "https://raw.githubusercontent.com/hackerb9/lsix/master/lsix" -o legacy/lsix && chmod +x legacy/lsix`

    2. In `show_artist_illusts()` (`utils.py`), change `renderer="lscat"` to `renderer="lsix"`.

* Adjust the 'magic numbers'. They are commented in `lscat.py`.
* You can contribute to `lscat.py` by checking terminal size and doing all the maths and send a PR

| Feature  | lscat.py | legacy/lscat | [hackerb9/lsix](https://github.com/hackerb9/lsix/) |
| --- | --- | --- | --- |
| Speed  | :heavy_check_mark: | :x:\* | :x:\*
| Reliability (eg, resizing the terminal) | :x: | :interrobang: | :heavy_check_mark:
| Adaptability (eg, other terminals, tmux) | :x: | :x: | :interrobang:

\* lsix will appear faster because the images are much smaller. Once you scale them up, lsix will be the slowest.

# Contributing
* Fork it
* Make a new branch with `git checkout -b myfeature` (a git pre-commit hook might prevent your git client from commiting to master, but github might let you. It doesn't matter which branch you edit, the pre-commit hook is just for me)
* Edit the files on your fork and branch
* Submit a pull request to master
* If you want to, you can create an issue first. Ask any questions by opening a new issue.
* If you're encountering/fixing a bug and you're stuck, try clearing the cache. For example, a bug might have downloaded to the wrong folder, but after fixing the bug, you need to clear the cache, otherwise it would not download anything and display the wrong contents.
* When testing your edit, don't forget to uninstall the pip version and do `python setup.py develop` (totally didn't happen to me).

**NOTE:** running `koneko.py` with python or executing it will fail with an import error (circular import). Python imports are a mess, just use `python setup.py develop` when you want to test a change.

## Priorities
(As in, what I think I need help on and what you might want to focus on, not what will only be accepted. All PRs will be considered, regardless if it's important or not)

1. Speed: if it's slower than going to pixiv then half of its purpose is gone
    * The bottleneck is network IO and downloading images from pixiv
2. Reliable rendering: There's no point in browsing a media-heavy site if the terminal is text-only and can't render the images well
    * While it's working perfectly for my use case, it should work well for other reasonable cases (different terminal sizes, number+name for the gallery)

Flowchart of modes and their connections:

![UML](http://plantuml.com:80/plantuml/png/dPDD2y8m38Rl_HM5dZtejfk8YYY2Dy6BY1IDTHWtwGVYltVMhfkrAdWgIzuyUPUcGwMvrEQCX1W5Eww0ZgJEbTuAZWZorlNn-PaBwFdFQObONlD2RBajK8bFBO7BtR6Efmq1qLJaGrsPDKsjZIvb4u3BydGRem4I6A7zphgTtyXS77Ldu6f_oYkb-uNNhZtA5lnQp2H04ONuR0lnFCAq0mOD4ig4XR-Fp094pGud7pCZ0YDVcURYB2M1fPGo2NiIN9IjhE8nBv-alaKQjUjeqS5db3qkPfMN29gyBOUjRmJjuV-I8XpyOcHHN_znwuqBXqE6KEohHtG7)

Simplified UML diagram of the classes:

![UML](http://plantuml.com:80/plantuml/png/bLVRJjmm47tFL-InR4a-e488XDIg5PKgLUrBLKKcCRi69xPiXosY_7jzJJos0_HjFPdZCsSydl5UI8M4caTQLOeeYkiHaQdbZrM5RgGIg5TrJv6KzJLZl3uxUtTvMWiyd9oVFrLr_VufU3tRVTwTLCzLvG2NGX6flh81MwXnru1wr0RtSqKum6TAPwa-CahPyKqm5zBVPc37gKduFjHaEc11b0Hklmva6F3qkocoHQ1C_oT4AHQFr-GU6_Si5GL1BY8FjA2WPkzicz8BZaauCsallSKJb2AQy1_LSRJ7EYfhu08_47m4DiRnr54otNSzOsAGkNsQns0qIQGC3HqPzHO98laOmIofjGQBmCOphDOwEg1feBZZWeqSr9DH72VKwBqwhVj7DAs2S_G2ZdFyqXPxrY7Bq_da9oBpxv7Ed3-h6r2kKN54nGTBURUDw3KDarYwwx79bPPNH5Mw1hjDMC9NAaAFBIVy1M9FkerSkCETU8KUf2jBRfJ6c3a1bJb15JQ2x0zgwIld6_67AlwfBy8tziQ-o6xkiBxnxiPgK6UTreeszwbOmpMyYQ4wQtkbeScs26YoJOBDCZ5JZ1wmkv6mywQQecHdSjisbGENnY58gqBIN2R9jFyXiP3_CLA-OoJwmzjHK5UPTcEoD2MoUA0inmQtXUUtUaMx9Ixv95Yyqlw_zYgZDfnaUIgO0-UR3NhDqSgttZKeAL9TSewKHPxbPE-sEM0lAYH_jq6PDB4qdrJsIBMcS4iPNGULmDE0HLHi3dY5n11gRCCbj8xSguh9NMTfedsZT057fnDi7bTUE8HTQnnRiE6I37CDqm6oQsUURWi1UGj-7LFgsqqpywY79d5amoBlkbbNhv8xb27IFVFn2L-Ccvtz3J0GtNeWUL2fyAYcNixGfYCu2k06_V93gIgE-dipOjnpnjUh7qgp5k3VETQyQ38DFFeMOyA32SBIMl1LcZZ7-xZd9Tp53KE7RO73yp971gHGICKNoQPb5WXqzB_qHzi5PTUZ_k07H6t_6actw6UXRonieC56R7aiJqKxrUuqKJ2ukCZILIt7u0X1Tvu5ZTg6ZTiA155h9__hbb0yeJ64wtk-YqRJUJCPzsxGSlyw3q-0URpH1yPkNI3X5M2SD4LOKoIqOI0YUM9W_yYGiSGGK11brXof0n1fud52GH8Bsarb0UbaW0TakA1bFTAGqELrmqmq7ITzBC_5lHfy3cqfhmTcUSB2r8e1n6lW83abYZCo-JyoMVtjz1ri2dSWQfa6KoK5iC2igUYyP6pnJQUVzQqkzF2n__x_0G00)

## Conda environment

```sh
conda create -n koneko
conda activate koneko
conda env list                  # make sure you're in the correct environment...
conda install -n koneko pip     # and make sure pip is installed...
which pip                       # and pip is in your conda directory

# Or use manual installation instructions below
pip install koneko

# Use anywhere:
koneko

# To remove the conda env:
conda remove --name koneko --all
```

## Manual installation
```sh
# Use the latest stable version (recommended)
# Make sure the version number is the latest
git clone -b 'v0.4' --depth 1 https://github.com/twenty5151/koneko.git
# Use the master branch for upcoming features:
git clone -b master https://github.com/twenty5151/koneko.git
# Use the dev branch for latest features, fixes, and instability:
git clone -b dev https://github.com/twenty5151/koneko.git

cd koneko
# Manually install without PyPI; for general usage
# Both will correctly copy the required pictures
pip install .
# or
python setup.py install
# or
# Manually install for development
python setup.py develop

# On certain shells with implicit cd, typing `koneko` might cd into the dir
# Instead of running the executable
cd ~
# Use anywhere:
koneko
```

## Unit tests
Use `pytest testing.py -v`. For type checking use mypy: `mypy koneko.py --ignore-missing-imports -v`


Here's a random shell command to get (but not download) and display any pixiv image url:
```sh
curl -e 'https://www.pixiv.net' "https://i.pximg.net/img-original/img/2019/12/21/20/13/12/78403815_p0.jpg" | kitty +kitten icat --align left --place 800x480@0x5
```

## Upload to PyPI
Bump version info in `__init__.py`, `setup.py`, and `README.md`

```sh
python setup.py sdist bdist_wheel
twine upload dist/*
pip install koneko --upgrade
```

# Manual

```
Browse pixiv in the terminal using kitty's icat to display images (in the
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
```

```
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

```
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
```

## Trackers
Nine trackers in the Android app, according to [exodus](https://reports.exodus-privacy.eu.org/en/reports/jp.pxv.android/latest/):

* Amazon Advertisement
* AMoAd
* Google Ads
* Google CrashLytics
* Google DoubleClick
* Google Firebase Analytics
* Integral Ad Science
* Moat
* Twitter MoPub

Advertisers from pixiv's [privacy policy](https://policies.pixiv.net/en.html#booth):

* Looker
* Repro
* Qualaroo
* DDAI（Date Driven Advertising Initiative）
* YourAdChoices
* Rubicon Project
* i-Mobile Co., Ltd.
* Akinasista Corporation
* Axel Mark Inc.
* AppLovin
* Amazon Japan G.K.
* AmoAd Inc.
* AOL Platforms Japan K.K.
* OpenX
* Google Inc.
* CRITEO K.K.
* CyberAgent, Inc.
* Geniee, Inc.
* Supership Inc.
* GMO AD Marketing Inc.
* F@N Communications, Inc.
* Facebook Inc.
* Fluct, Inc.
* Platform One Inc.
* MicroAd Inc.
* MoPub Inc.
* Yahoo! Japan Corporation
* United, Inc.
* 株式会社Zucks
* PubMatic, Inc.
* Liftoff Mobile, Inc.
* Mobfox US LLC
* OneSignal
* Smaato, Inc.
* SMN株式会社
* 株式会社アドインテ
