"""Word handling: normalization, masking, letter matching.

All comparisons use normalized form (lowercase, ё → е).
The original word is kept for display; matching uses normalize().
"""


def normalize(text: str) -> str:
    """Lowercase and replace ё with е.

    >>> normalize("МОЛОДЁЖЬ")
    'молодежь'
    """
    return text.lower().replace("ё", "е")


def make_mask(word: str) -> tuple[bool, ...]:
    """Create initial mask for a word.

    Alphabetic characters are hidden (False).
    Non-alphabetic (hyphens, spaces, digits) are pre-revealed (True).

    >>> make_mask("КИНО-ТЕАТР")
    (False, False, False, False, True, False, False, False, False, False)
    """
    return tuple(not c.isalpha() for c in word)


def reveal_letter(
    word: str, mask: tuple[bool, ...], letter: str
) -> tuple[bool, ...]:
    """Reveal every position in *word* matching *letter* (normalized).

    Positions already revealed stay revealed.
    """
    norm_letter = normalize(letter)
    norm_word = normalize(word)
    return tuple(
        revealed or norm_word[i] == norm_letter
        for i, revealed in enumerate(mask)
    )


def count_occurrences(word: str, letter: str) -> int:
    """Count how many times *letter* appears in *word* (both normalized)."""
    return normalize(word).count(normalize(letter))


def is_fully_revealed(mask: tuple[bool, ...]) -> bool:
    """True when every position in the mask is revealed."""
    return all(mask)


def check_word(guess: str, answer: str) -> bool:
    """Check if *guess* matches *answer* after normalization."""
    return normalize(guess) == normalize(answer)
