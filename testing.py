import koneko
import os

def test_split_backslash_last():
    assert koneko.split_backslash_last("https://www.pixiv.net/en/users/2232374") == "2232374"
    assert koneko.split_backslash_last("https://www.pixiv.net/en/artworks/78823485") == "78823485"


def test_generate_filepath():
    assert koneko.generate_filepath("78823485_p0.jpg") == f"{os.path.expanduser('~')}/Downloads/78823485_p0.jpg"

def test_prefix_filename():
    assert koneko.prefix_filename("old.jpg", "new", 2) == "02_new.jpg"
    assert koneko.prefix_filename("old.jpg", "new", 10) == "10_new.jpg"

