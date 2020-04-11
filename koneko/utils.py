import os
import shutil
import imghdr

import pixcat

import pure
import lscat
import koneko


def verify_full_download(filepath):
    verified = imghdr.what(filepath)
    if not verified:
        os.remove(filepath)
        return False
    return True


def show_artist_illusts(path, renderer="lscat", **kwargs):
    """
    Use specified renderer to display all images in the given path
    Default is "lscat"; can be "lscat old" or "lsix" (needs to install lsix first)
    """
    if renderer != "lscat":
        lscat_path = os.getcwd()

    with pure.cd(path):
        if renderer == "lscat":
            lscat.Gallery(path, **kwargs)
        elif renderer == "lscat old":
            from pathlib import Path
            os.system(f"{Path(lscat_path).parent}/legacy/lscat")
        elif renderer == "lsix":
            from pathlib import Path
            os.system(f"{Path(lscat_path).parent}/legacy/lsix")


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
        "c. Clear koneko cache",
        "q. Quit",
    )
    if printmessage:
        for message in messages:
            print(" " * 24, message)

    pixcat.Image("../pics/71471144_p0.png").thumbnail(500).show(align="left", y=0)
    command = input("\nEnter a command: ")
    return command


def artist_user_id_prompt():
    artist_user_id = input("Enter artist ID or url:\n")
    return artist_user_id


@pure.catch_ctrl_c
def show_man_loop():
    os.system("clear")
    print(koneko.Image.__doc__)
    print(" " * 3, "=" * 30)
    print(koneko.Gallery.__doc__)
    print(" " * 3, "=" * 30)
    print(koneko.Users.__doc__)
    while True:
        help_command = input("\n\nPress any key to return: ")
        if help_command or help_command == "":
            os.system("clear")
            break


@pure.catch_ctrl_c
def clear_cache_loop():
    print("Do you want to remove all cached images?")
    print("This will not remove images you explicitly downloaded.")
    while True:
        help_command = input("\nEnter y to confirm: ")
        if help_command == "y":
            shutil.rmtree("/tmp/koneko/")
            os.system('clear')
            break
        else:
            print("Operation aborted!")
            os.system('clear')
            break


@pure.catch_ctrl_c
def info_screen_loop():
    os.system("clear")
    messages = (
        "",
        "koneko こねこ version 0.2 beta\n",
        "Browse pixiv in the terminal using kitty's icat to display",
        "images with images embedded in the terminal\n",
        "View an artist's illustrations with mode 1",
        "View a post with mode 2. Posts support one or multiple images.",
        "View artists you followed with mode 3.",
        "Search for artists and browse their works with mode 4.\n",
        "Thank you for using koneko!",
        "Please star, report bugs and contribute in:",
        "https://github.com/twenty5151/koneko",
        "GPLv3 licensed\n",
        "Credits to amasyrup (甘城なつき):",
        "Welcome image: https://www.pixiv.net/en/artworks/71471144",
        "Current image: https://www.pixiv.net/en/artworks/79494300",
    )

    for message in messages:
        print(" " * 26, message)

    pixcat.Image("../pics/79494300_p0.png").thumbnail(750).show(align="left", y=0)

    while True:
        help_command = input("\nPress any key to return: ")
        if help_command or help_command == "":
            os.system("clear")
            break
