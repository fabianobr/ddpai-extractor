"""
Automated tests for lazy video loading implementation in web/index.html.

These tests verify the HTML/JS implementation by static analysis:
- Correct src clearing method (removeAttribute, not src='')
- Correct lazy load condition (hasAttribute, not .src check)
- Loading indicator shown on play click, not on loadstart
- Loading indicator hidden on 'playing' event, not 'canplay'
- attachLazyLoadListener function exists and is wired up
"""

import pytest
from pathlib import Path

HTML_FILE = Path(__file__).parent.parent / 'web' / 'index.html'


@pytest.fixture(scope='module')
def html_content():
    return HTML_FILE.read_text()


# ── Silent Cancellation ──────────────────────────────────────────────────────

def test_uses_remove_attribute_not_empty_src(html_content):
    """Must use removeAttribute('src') not src='' — empty src triggers MEDIA_ELEMENT_ERROR."""
    assert "removeAttribute('src')" in html_content, \
        "Should use removeAttribute('src') to clear video source"


def test_no_empty_src_assignment(html_content):
    """src = '' triggers browser error — must not be used for clearing."""
    # Allow src='' only inside comments or strings in console.log etc.
    # Check that the actual assignment pattern is gone.
    lines = html_content.splitlines()
    violations = [
        (i + 1, line.strip())
        for i, line in enumerate(lines)
        if "video.src = ''" in line and not line.strip().startswith('//')
    ]
    assert not violations, \
        f"Found src='' assignment (use removeAttribute instead):\n" + \
        "\n".join(f"  line {n}: {l}" for n, l in violations)


def test_calls_load_after_remove_attribute(html_content):
    """After removeAttribute('src'), must call .load() to reset media element."""
    assert '.load()' in html_content, \
        "Should call video.load() after removeAttribute to flush buffered data"


# ── Lazy Load Trigger ────────────────────────────────────────────────────────

def test_lazy_load_uses_has_attribute_check(html_content):
    """Condition must use hasAttribute('src') — .src always returns absolute URL."""
    assert "hasAttribute('src')" in html_content, \
        "Should use hasAttribute('src') to check if video is unloaded"


def test_lazy_load_does_not_use_dot_src_check(html_content):
    """video.src is always truthy (resolves to base URL) — cannot be used as empty check."""
    # Specifically the pattern !videoElement.src used as the load guard
    assert "!videoElement.src &&" not in html_content and \
           "!videoElement.src)" not in html_content, \
        "Should not use !videoElement.src as empty check (always truthy due to URL resolution)"


def test_attach_lazy_load_listener_function_exists(html_content):
    """attachLazyLoadListener() function must be defined."""
    assert 'function attachLazyLoadListener(' in html_content, \
        "attachLazyLoadListener() function must exist"


def test_lazy_src_data_attribute_used(html_content):
    """Video paths must be stored in dataset.lazySrc, not set directly on src."""
    assert 'dataset.lazySrc' in html_content, \
        "Should store video paths in dataset.lazySrc attribute"


def test_lazy_listener_attached_for_rear_video(html_content):
    """attachLazyLoadListener must be called for rear video."""
    assert 'attachLazyLoadListener(rearVideo)' in html_content, \
        "Should attach lazy load listener to rear video"


def test_lazy_listener_attached_for_front_video(html_content):
    """attachLazyLoadListener must be called for front video."""
    assert 'attachLazyLoadListener(frontVideo)' in html_content, \
        "Should attach lazy load listener to front video"


# ── Loading Indicator ────────────────────────────────────────────────────────

def test_loading_indicator_shown_in_lazy_listener(html_content):
    """Loading indicator must be shown inside attachLazyLoadListener (on play click)."""
    # Find the attachLazyLoadListener function body
    start = html_content.find('function attachLazyLoadListener(')
    end = html_content.find('\n        }', start + 10)
    func_body = html_content[start:end]
    assert 'style.display = ' in func_body, \
        "Loading indicator should be shown inside attachLazyLoadListener"


def test_loading_hidden_on_playing_event_not_canplay(html_content):
    """Must use 'playing' event (not 'canplay') to hide loading — reliable for large files."""
    assert "addEventListener('playing'" in html_content, \
        "Should hide loading indicator on 'playing' event"


def test_no_canplay_for_loading_indicator(html_content):
    """canplay fires unreliably for large video files — must not use for loading hide."""
    lines = html_content.splitlines()
    violations = [
        (i + 1, line.strip())
        for i, line in enumerate(lines)
        if 'canplay' in line and 'loading' in line.lower()
    ]
    assert not violations, \
        f"Should not use canplay to hide loading indicator:\n" + \
        "\n".join(f"  line {n}: {l}" for n, l in violations)


def test_no_loadstart_for_loading_indicator(html_content):
    """loadstart fires even on src='' — must not use to show loading indicator."""
    lines = html_content.splitlines()
    violations = [
        (i + 1, line.strip())
        for i, line in enumerate(lines)
        if 'loadstart' in line and 'loading' in line.lower()
    ]
    assert not violations, \
        f"Should not use loadstart to show loading indicator:\n" + \
        "\n".join(f"  line {n}: {l}" for n, l in violations)


# ── Sync Conditionals ────────────────────────────────────────────────────────

def test_sync_conditions_use_lazy_src_not_dot_src(html_content):
    """Sync seek conditions must check dataset.lazySrc, not video.src (always truthy)."""
    # These bad patterns would always be true because .src resolves to base URL
    assert 'rearVideo.src || rearVideo.dataset.lazySrc' not in html_content, \
        "Sync condition should use only dataset.lazySrc, not video.src"
    assert 'frontVideo.src || frontVideo.dataset.lazySrc' not in html_content, \
        "Sync condition should use only dataset.lazySrc, not video.src"


# ── cloneNode / listener survival ────────────────────────────────────────────

def test_lazy_listener_called_inside_sync_function(html_content):
    """attachLazyLoadListener must be called inside attachVideoSyncListeners.

    cloneNode(true) destroys event listeners. If attachLazyLoadListener is called
    BEFORE the clone (e.g. in updateVideos), the play listener is lost when the
    element is replaced by its clone — videos will never load on play click.
    """
    start = html_content.find('function attachVideoSyncListeners(')
    assert start != -1, "attachVideoSyncListeners function must exist"
    next_func = html_content.find('\n        function ', start + 10)
    func_body = html_content[start:next_func if next_func != -1 else len(html_content)]

    assert 'attachLazyLoadListener' in func_body, \
        "attachLazyLoadListener must be called inside attachVideoSyncListeners " \
        "(cloneNode destroys listeners added before clone)"


def test_lazy_listener_called_after_clone_node(html_content):
    """attachLazyLoadListener must appear AFTER cloneNode in attachVideoSyncListeners.

    If called before, cloneNode replaces the element and silently destroys the play
    listener — user clicks play but src is never set and video never loads.
    """
    start = html_content.find('function attachVideoSyncListeners(')
    next_func = html_content.find('\n        function ', start + 10)
    func_body = html_content[start:next_func if next_func != -1 else len(html_content)]

    clone_pos = func_body.find('cloneNode')
    lazy_pos = func_body.find('attachLazyLoadListener')

    assert clone_pos != -1, "attachVideoSyncListeners must contain cloneNode"
    assert lazy_pos != -1, "attachLazyLoadListener must be called inside attachVideoSyncListeners"
    assert lazy_pos > clone_pos, \
        "attachLazyLoadListener must be called AFTER cloneNode — calling before means " \
        "the clone replaces the element and the play listener is silently destroyed"
