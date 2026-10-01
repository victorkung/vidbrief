

from vidbrief.naming import canonicalize_media_url, is_supported_url


def test_youtube_watch():
    url = "https://youtu.be/dQw4w9WgXcQ?si=abc"
    out = canonicalize_media_url(url)
    assert out == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert is_supported_url(url)


def test_youtube_playlist_stripped():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLxxxx"
    assert canonicalize_media_url(url) == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_x_status():
    url = "https://twitter.com/user/status/1234567890"
    out = canonicalize_media_url(url)
    assert out.startswith("https://x.com/")
    assert is_supported_url(url)


def test_reject_home():
    assert not is_supported_url("https://www.youtube.com/")
    assert not is_supported_url("https://x.com/home")


if __name__ == "__main__":
    test_youtube_watch()
    test_youtube_playlist_stripped()
    test_x_status()
    test_reject_home()
    print("ok")
