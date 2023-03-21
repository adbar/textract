"Parts dedicated to content hashing and text similarity."

import re
import string

from base64 import urlsafe_b64encode
from functools import lru_cache
from hashlib import blake2b
from operator import add
from typing import Any, List, Optional


class Simhash:
    "Implement a basic Charikar hashing approach of string similarity."
    __slots__ = ["hash", "length"]

    def __init__(
        self, inputstring: str = "", length: int = 64, existing_hash: Optional[str] = None
    ) -> None:
        "Store length and existing or new hash."
        self.length = length
        self.hash = self.validate(existing_hash) or self.create_hash(inputstring)

    def _sample_tokens(self, inputstring: str) -> List[str]:
        """Split input into list of tokens and adjust length threshold to make sure
        there is enough data."""
        tokens = []
        for token in inputstring.split():
            token = token.strip(string.punctuation)
            if token.isalnum():
                tokens.append(token)
        # tokens = REGEX.findall(inputstring)
        i = 4
        sample = []
        for i in range(4, -1, -1):
            sample = [t for t in tokens if len(t) > i]
            if len(sample) >= self.length / 2:  # self.length or self.length/2
                return sample
        return sample

    def _hash(self, s: str) -> int:
        "Return a numerical hash of the string."
        return int.from_bytes(blake2b(s.encode(), digest_size=8).digest(), "big")
        # old: variable-length version of Python's builtin hash by @sean-public
        # see also Siphash13 in https://peps.python.org/pep-0456/
        # if s == "":
        #    return 0
        # mask = 2**self.length - 1
        # x = ord(s[0]) << 7
        # for c in s:
        #    x = ((x * 1000003) ^ ord(c)) & mask
        # x ^= len(s)
        # if x == -1:
        #    return -2
        # return x

    @lru_cache(maxsize=65536)
    def _vector_to_add(self, token: str) -> List[int]:
        "Create vector to add to the existing string vector"
        the_hash = self._hash(token)
        return [1 if the_hash & (1 << i) else -1 for i in range(self.length)]

    def create_hash(self, inputstring: str) -> int:
        """Calculates a Charikar simhash. References used:
        https://github.com/vilda/shash/
        https://github.com/sean-public/python-hashes/blob/master/hashes/simhash.py
        Optimized for Python by @adbar.
        """
        vector = [0] * self.length

        for token in self._sample_tokens(inputstring):
            vector = list(map(add, vector, self._vector_to_add(token)))

        return sum(1 << i for i in range(self.length) if vector[i] >= 0)

    def to_hex(self) -> str:
        "Convert the numerical hash to a hexadecimal string."
        return hex(self.hash)[2:]

    def _hash_to_int(self, inputhash) -> Optional[int]:
        "Convert the hexadecimal hash to a numerical value."
        try:
            return int(inputhash, 16)
        except (TypeError, ValueError):
            return None

    def validate(self, inputhash: Optional[Any]) -> Optional[int]:
        "Validate the input hash and return it, or None otherwise."
        if isinstance(inputhash, int) and len(str(inputhash)) == 16:
            return inputhash
        if isinstance(inputhash, str):
            if inputhash.isdigit() and 18 <= len(inputhash) <= 22:
                return int(inputhash)
            # possibly a hex string
            return self._hash_to_int(inputhash)
        return None

    def hamming_distance(self, other_hash: Any) -> int:
        "Return distance between two hashes of equal length using the XOR operator."
        # https://docs.python.org/3.10/library/stdtypes.html#int.bit_count
        return bin(self.hash ^ other_hash.hash).count("1")

    def similarity(self, other_hash: Any) -> float:
        """Calculate how similar this hash is from another simhash.
        Returns a float from 0.0 to 1.0 (linear distribution, inclusive)
        """
        return (self.length - self.hamming_distance(other_hash)) / self.length


def generate_bow_hash(string: str, length: int = 24) -> bytes:
    "Create a bag of words and generate a hash for a given string."
    # pre-process string
    words = re.findall(r"[\w-]{3,}", string.lower())
    # [w for w in s.lower().split() if len(w) > 3 and w.isalpha()]
    teststring = " ".join(words).strip()
    # perform hashing with limited size
    return blake2b(teststring.encode(), digest_size=length).digest()


def generate_hash_filename(content: str) -> str:
    "Create a filename-safe string by hashing the given content."
    return urlsafe_b64encode(generate_bow_hash(content, 12)).decode()


def content_fingerprint(content: str) -> str:
    "Calculate a simhash hex value for meaningful bits of the content."
    return Simhash(content).to_hex()
