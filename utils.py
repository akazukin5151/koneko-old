import os
import imghdr

import pixcat

import pure
from lscat import main as lscat
from koneko import Image, Users, Gallery


def verify_full_download(filepath):
    verified = imghdr.what(filepath)
    if not verified:
        os.remove(filepath)
        return False
    return True


def show_artist_illusts(path, renderer="lscat"):
    """
    Use specified renderer to display all images in the given path
    Default is "lscat"; can be "lscat old" or "lsix" (needs to install lsix first)
    """
    if renderer != "lscat":
        lscat_path = os.getcwd()

    with pure.cd(path):
        if renderer == "lscat":
            lscat(path)
        elif renderer == "lscat old":
            os.system(f"{lscat_path}/legacy/lscat")
        elif renderer == "lsix":
            os.system(f"{lscat_path}/legacy/lsix")


def display_image_vp(filepath):
    os.system(f"kitty +kitten icat --silent {filepath}")


# - Prompt functions
def begin_prompt(printmessage=True):
    messages = (
        "",
        "Welcome to koneko v0.2\n",
        "Select an action:",
        "1. View artist illustrations",
        "2. Open pixiv post",
        "3. View following artists",
        "4. Search for artists\n",
        "?. Info",
        "m. Manual",
        "q. Quit",
    )
    if printmessage:
        for message in messages:
            print(" " * 24, message)

    pixcat.Image("pics/71471144_p0.png").thumbnail(500).show(align="left", y=0)
    command = input("\nEnter a command: ")
    return command


def artist_user_id_prompt():
    artist_user_id = input("Enter artist ID or url:\n")
    return artist_user_id


@pure.catch_ctrl_c
def show_man_loop():
    os.system("clear")
    print(Image.__doc__)
    print(" " * 3, "=" * 30)
    print(Gallery.__doc__)
    print(" " * 3, "=" * 30)
    print(Users.__doc__)
    while True:
        help_command = input("\n\nPress any key to return: ")
        if help_command or help_command == "":
            os.system("clear")
            break


@pure.catch_ctrl_c
def info_screen_loop():
    os.system("clear")
    messages = (
        "",
        "koneko こねこ version 0.1 beta\n",
        "Browse pixiv in the terminal using kitty's icat to display images",
        "with images embedded in the terminal\n",
        "View a gallery of an artist's illustrations with mode 1",
        "View a post with mode 2. Posts support one or multiple images\n",
        "Thank you for using koneko!",
        "Please star, report bugs and contribute in:",
        "https://github.com/twenty5151/koneko",
        "GPLv3 licensed\n",
        "Credits to amasyrup (甘城なつき):",
        "Welcome image: https://www.pixiv.net/en/artworks/71471144",
        "Current image: https://www.pixiv.net/en/artworks/79494300",
    )

    for message in messages:
        print(" " * 23, message)

    pixcat.Image("pics/79494300_p0.png").thumbnail(650).show(align="left", y=0)

    while True:
        help_command = input("\n\nPress any key to return: ")
        if help_command or help_command == "":
            os.system("clear")
            break
