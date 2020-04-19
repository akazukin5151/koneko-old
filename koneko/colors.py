"""Export the colors for [h]elp screen keys"""

from colorama import Fore

# Private
def _letter(letter):
    return "".join([Fore.RED, "[", Fore.MAGENTA, letter, Fore.RED, "]", Fore.RESET])

def _letter_with_coords(letter):
    return "".join([Fore.RED, "[", Fore.MAGENTA, letter, Fore.RED, "][",
                    Fore.BLUE, "n", Fore.RED, "]", Fore.RESET])

def _two_letter_with_coords(letter):
    return "".join([Fore.RED, "[", Fore.MAGENTA, letter.lower(), Fore.RESET, "|",
                    Fore.MAGENTA, letter.upper(), Fore.RED, "]", coords, Fore.RESET])


_letters = ["a", "n", "p", "r", "q", "m", "b"]
_tlc = ["o", "d"]

# Public
a, n, p, r, q, m, b = list(map(_letter, _letters))

i = _letter_with_coords("i")

coords = "".join([Fore.RED, "{", Fore.BLUE, "y", Fore.RED, "}{", Fore.BLUE,
                  "x", Fore.RED, "}", Fore.RESET])

o, d = list(map(_two_letter_with_coords, _tlc))

