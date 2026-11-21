import pytest

from app.core.crypto import TokenCipher
from app.services.text import safe_filename, words_to_text
from app.services.youtube import youtube_video_id


@pytest.mark.parametrize(
    "url,vid",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ&t=42s", "dQw4w9WgXcQ"),
        ("https://m.youtube.com/watch?feature=share&v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ?si=abc", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/live/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("  https://www.youtube.com/watch?v=dQw4w9WgXcQ  ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/playlist?list=PL123", None),
        ("https://www.youtube.com/@channel", None),
        ("https://evil.com/watch?v=dQw4w9WgXcQ", None),
        ("https://youtube.com.evil.com/watch?v=dQw4w9WgXcQ", None),
        ("javascript:alert(1)", None),
        ("ftp://youtube.com/watch?v=dQw4w9WgXcQ", None),
    ],
)
def test_youtube_video_id(url, vid):
    assert youtube_video_id(url) == vid


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Hello World", "Hello-World"),
        ("Ça va? «oui»!", "Ca-va-oui"),
        ('quote"s/and\\slashes', "quotesandslashes"),
        ("🔥🔥🔥", "clip"),
        ("a" * 200, "a" * 80),
    ],
)
def test_safe_filename(name, expected):
    assert safe_filename(name, default="clip") == expected


def test_words_to_text():
    assert words_to_text([{"word": " Hi"}, {"word": "there. "}]) == "Hi there."


def test_token_cipher_roundtrip():
    from cryptography.fernet import Fernet

    cipher = TokenCipher(Fernet.generate_key().decode())
    assert cipher.decrypt(cipher.encrypt("ya29.token")) == "ya29.token"
    with pytest.raises(ValueError):
        TokenCipher("")
