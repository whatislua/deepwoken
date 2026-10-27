"""Builder 101: reads a build from a deepwoken.co builder link (the build's name and the talents in it),
and spots those talents in text read off your screen (the talent cards you're offered on level up)."""
import difflib
import html
import re
import urllib.request

BUILDER_URL = re.compile(r"^https?://(www\.)?deepwoken\.co/builder\?id=([A-Za-z0-9_-]+)")


def fetch(url, timeout=15):
    """{'name': str, 'talents': [str]} for a deepwoken.co builder link."""
    url = url.strip()
    if not BUILDER_URL.match(url):
        raise ValueError("paste a link like https://deepwoken.co/builder?id=...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ElgansitoDemolisherMacro)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        page = r.read().decode("utf-8", "replace")
    return parse(page)


def parse(page):
    title = re.search(r"<title>(.*?)</title>", page, re.S)
    name = html.unescape(title.group(1)).replace("- Deepwoken Builder", "").strip() if title else "Build"
    talents, every = [], []
    # Each talent on the page is an element with data-talent-name; picked ones have aria-pressed="true".
    for m in re.finditer(r'<[^>]*data-talent-name="([^"]+)"[^>]*>', page):
        t = html.unescape(m.group(1)).strip()
        if t and t not in every:
            every.append(t)
        if t and 'aria-pressed="true"' in m.group(0) and t not in talents:
            talents.append(t)
    if not talents:
        raise ValueError("no talents found in that build (is it public?)")
    # every = all talents the builder page lists, so a card can be told apart from a misread
    return {"name": name, "talents": talents, "all": every}


def norm(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def find_talents(screen_text, talents, threshold=0.86):
    """Talents (from the build) whose names appear in OCR text, allowing small OCR mistakes."""
    words = norm(screen_text).split()
    found = []
    for t in talents:
        tw = norm(t).split()
        if not tw:
            continue
        n = len(tw)
        target = " ".join(tw)
        for i in range(0, max(len(words) - n + 1, 0)):
            window = " ".join(words[i:i + n])
            if window == target or difflib.SequenceMatcher(None, window, target).ratio() >= threshold:
                found.append(t)
                break
    return found


def canon(text):
    """Lowercase letters with the game font's usual OCR mix-ups folded together (c/e, l/i, rn/m...)."""
    t = norm(text).replace(" ", "")
    for a, b in (("rn", "m"), ("vv", "w"), ("c", "e"), ("l", "i"), ("1", "i"), ("|", "i"), ("0", "o"), ("5", "s")):
        t = t.replace(a, b)
    return t


def match_title(title, talents, threshold=0.8):
    """The talent a card's title is (best match above the threshold), or None."""
    got = canon(title)
    if len(got) < 3:
        return None
    best, best_score = None, threshold
    for t in talents:
        want = canon(t)
        if not want:
            continue
        score = difflib.SequenceMatcher(None, got, want).ratio()
        if want in got and len(want) >= 5 and len(want) >= 0.6 * len(got):
            score = max(score, 0.9)  # a little extra text around the title (a trailing mark, a stray letter)
        if score > best_score:
            best, best_score = t, score
    return best


def best_match(title, names):
    """(name, score) of the closest name to a card title, using the same OCR-forgiving comparison."""
    got = canon(title)
    best, best_score = None, 0.0
    if len(got) < 3:
        return None, 0.0
    for t in names:
        want = canon(t)
        if not want:
            continue
        score = difflib.SequenceMatcher(None, got, want).ratio()
        if want in got and len(want) >= 5 and len(want) >= 0.6 * len(got):
            score = max(score, 0.9)
        if score > best_score:
            best, best_score = t, score
    return best, best_score


def classify(title, build, every=()):
    """('in', name) for a card in your build, ('out', name) for a known talent that isn't in it
    (from `every`, the full list on the deepwoken.co page), or (None, None) when unsure."""
    name, score = best_match(title, build)
    if score >= 0.8:
        return "in", name
    other, other_score = best_match(title, [t for t in every if t not in build])
    if other_score >= 0.8 and other_score > score:
        return "out", other
    # Text that isn't a known talent (another menu, scenery, a half-read title) is never marked.
    return None, None
