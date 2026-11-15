from praxis_check.hello import hello_py


def test_hello_py():
    result = hello_py("World")
    assert result == "Hello, World!"
