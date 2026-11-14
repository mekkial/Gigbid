"""Deterministic check: does a proposal's first sentence repeat the job post's own words?"""
import re


def words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


def first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0]


def longest_shared_run(opening: str, job_text: str) -> int:
    """Length in words of the longest run of `opening` that appears verbatim (case/punctuation-insensitive) in the job text."""
    fw, jw, best = words(opening), " ".join(words(job_text)), 0
    for a in range(len(fw)):
        for b in range(a + best + 1, len(fw) + 1):
            if " ".join(fw[a:b]) in jw:
                best = b - a
            else:
                break
    return best


def copied_opening_words(cover_letter: str, job_title: str, job_description: str) -> int:
    return longest_shared_run(first_sentence(cover_letter), f"{job_title} {job_description}")
