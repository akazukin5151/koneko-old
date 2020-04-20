"""Export the colors for [h]elp screen keys"""

from colorama import Fore

# Private
def _letter(letter):
    """[] are red and a is magenta
    >>> _letter("a")
    ... [a]
    """
    return "".join([Fore.RED, "[", Fore.MAGENTA, letter, Fore.RED, "]", Fore.RESET])

def _letter_with_coords(letter):
    """ letter is magenta, n is blue, [] is red
    >>> _letter_with_coords("i")
    ... [i][n]
    """
    return "".join([Fore.RED, "[", Fore.MAGENTA, letter, Fore.RED, "][",
                    Fore.BLUE, "n", Fore.RED, "]", Fore.RESET])

def _two_letter_with_coords(letter):
    """ [] and {} is red, | is black, o and O is magenta, y and x is blue
    >>> _two_letter_with_coords("o")
    ... [o|O]{y}{x}
    """
    return "".join([Fore.RED, "[", Fore.MAGENTA, letter.lower(), Fore.RESET, "|",
                    Fore.MAGENTA, letter.upper(), Fore.RED, "]", coords, Fore.RESET])


_letters = ["a", "n", "p", "r", "q", "m", "b", "o", "d"]
_tlc = ["o", "d"]

# Public
# {y}{x}
coords = "".join([Fore.RED, "{", Fore.BLUE, "y", Fore.RED, "}{", Fore.BLUE,
                  "x", Fore.RED, "}", Fore.RESET])

a, n, p, r, q, m, b, o_, d_ = list(map(_letter, _letters))

i = _letter_with_coords("i")


o, d = list(map(_two_letter_with_coords, _tlc))

# For galleries
base1 = [
    coords, " view image at (x, y); ",
    i, " view nth image; ",
    d, " download image;\n",
    o, " open image in browser; view "
]

base2 = [
    n, "ext image; ",
    p, "revious image;\n",
    r, "eload and re-download all; ",
    q, "uit (with confirmation); ",
]
