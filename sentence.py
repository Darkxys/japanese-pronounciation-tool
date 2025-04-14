from dataclasses import dataclass
from typing import Optional, List
import jaconv
import pykakasi

kks = pykakasi.kakasi()


class Sentence:
    def __init__(self, raw_sentence: str):
        self.raw_sentence = raw_sentence.strip()

        self.words = parse_words(raw_sentence)

        self.julius_transcript = generate_julius_transcript_from_words(self.words)

    def get_hepburn_transcript(self):
        words = []
        for word in self.words:
            if word.romanji in [".", ",", "?", "!"]:
                words[len(words) - 1] += word.romanji
            else:
                words.append(word.romanji)
        return " ".join(words)


def parse_words(sentence: str) -> List["Word"]:
    words = []

    result = kks.convert(sentence)
    for item in result:
        raw = item["hepburn"]

        word = Word(item["orig"], raw)
        words.append(word)

    return words


def generate_julius_transcript_from_words(words: List["Word"]) -> str:
    katakanas = "".join(
        (
            (word.hiragana if word.romanji not in [".", ",", "?", "!"] else "")
            for word in words
        )
    )
    return jaconv.hiragana2julius(katakanas)


@dataclass
class Word:
    hiragana: str
    romanji: str
