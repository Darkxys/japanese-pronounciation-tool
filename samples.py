import os
import re


class Samples:
    def __init__(self):
        self.samples = {
            "Forvo": self.get_forvo_samples(),
            "JSUT": self.get_jsut_samples(),
        }

    def get_jsut_samples(self):
        samples = {}
        basepath = "data/jsut_basic5000_sample"
        with open(os.path.join(basepath, "transcript_utf8.txt"), encoding="utf-8") as f:
            for line in f:
                basename, sentence = line.rstrip().split(":")
                filename = os.path.join(basepath, f"{basename}.wav")
                samples[sentence] = {
                    "filename": filename,
                    "sentence": sentence,
                }
        return samples

    def get_forvo_samples(self):
        samples = {}
        basepath = "data/greetings_and_apologies"
        for fname in sorted(os.listdir(basepath)):
            m = re.match(r"^pronunciation_ja_([^.]+).wav$", fname)
            if m:
                sentence = m.group(1)
                samples[sentence] = {
                    "filename": os.path.join(basepath, fname),
                    "sentence": sentence,
                }

        return samples
