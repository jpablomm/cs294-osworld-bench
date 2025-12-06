"""
Security tests for action validation

Tests that the input validation prevents code injection and other attacks.
"""

import pytest
from green_agent.a2a.server import (
    _validate_coordinates,
    _validate_text,
    _validate_keys,
    _validate_number
)


class TestCoordinateValidation:
    """Test coordinate validation prevents injection"""

    def test_valid_coordinates(self):
        """Test normal coordinates pass validation"""
        x, y = _validate_coordinates(100, 200)
        assert x == 100
        assert y == 200

    def test_boundary_coordinates(self):
        """Test boundary values"""
        x, y = _validate_coordinates(0, 0)
        assert x == 0
        assert y == 0

        x, y = _validate_coordinates(1920, 1080)
        assert x == 1920
        assert y == 1080

    def test_coordinates_out_of_bounds(self):
        """Test out of bounds coordinates are rejected"""
        with pytest.raises(ValueError, match="out of bounds"):
            _validate_coordinates(-1, 100)

        with pytest.raises(ValueError, match="out of bounds"):
            _validate_coordinates(100, -1)

        with pytest.raises(ValueError, match="out of bounds"):
            _validate_coordinates(2000, 100)

        with pytest.raises(ValueError, match="out of bounds"):
            _validate_coordinates(100, 2000)

    def test_coordinates_injection_attempt(self):
        """Test injection attempts via coordinates are rejected"""
        # Try to inject code via coordinate
        with pytest.raises(ValueError):
            _validate_coordinates("100); import os; os.system('whoami')", 200)

        with pytest.raises(ValueError):
            _validate_coordinates(100, "200); __import__('os').system('ls')")

    def test_coordinates_non_numeric(self):
        """Test non-numeric coordinates are rejected"""
        with pytest.raises(ValueError, match="must be integers"):
            _validate_coordinates("abc", 100)

        with pytest.raises(ValueError, match="must be integers"):
            _validate_coordinates(100, "xyz")

        with pytest.raises(ValueError, match="must be integers"):
            _validate_coordinates(None, 100)


class TestTextValidation:
    """Test text validation prevents injection"""

    def test_valid_text(self):
        """Test normal text passes validation"""
        text = _validate_text("Hello World")
        assert text == "Hello World"

    def test_special_characters(self):
        """Test text with special characters is allowed"""
        text = _validate_text('Text with "quotes" and \\backslashes\\ and newlines\n')
        assert 'quotes' in text
        assert '\\' in text
        assert '\n' in text

    def test_text_too_long(self):
        """Test overly long text is rejected"""
        long_text = "a" * 10001
        with pytest.raises(ValueError, match="Text too long"):
            _validate_text(long_text)

    def test_text_not_string(self):
        """Test non-string input is rejected"""
        with pytest.raises(ValueError, match="must be string"):
            _validate_text(123)

        with pytest.raises(ValueError, match="must be string"):
            _validate_text(["list", "of", "strings"])

    def test_text_with_injection_attempts(self):
        """Test injection attempts in text are accepted but will be escaped"""
        # These should be accepted but will be safely escaped by repr()
        malicious_texts = [
            '"); import os; os.system("rm -rf /")',
            "\\n__import__('os').system('cat /etc/passwd')",
            "'; exec('import os; os.system(\"whoami\")')",
        ]

        for text in malicious_texts:
            # Should not raise - validation accepts them
            validated = _validate_text(text)
            # But they should be treated as literal strings, not code
            assert validated == text


class TestKeyValidation:
    """Test key validation prevents injection"""

    def test_valid_single_key(self):
        """Test single valid key"""
        keys = _validate_keys(["a"])
        assert keys == ["a"]

    def test_valid_key_combination(self):
        """Test valid key combinations"""
        keys = _validate_keys(["ctrl", "c"])
        assert keys == ["ctrl", "c"]

        keys = _validate_keys(["alt", "f4"])
        assert keys == ["alt", "f4"]

    def test_function_keys(self):
        """Test function keys are allowed"""
        for i in range(1, 13):
            keys = _validate_keys([f"f{i}"])
            assert keys == [f"f{i}"]

    def test_special_keys(self):
        """Test special keys are allowed"""
        special_keys = ["enter", "tab", "space", "backspace", "escape"]
        for key in special_keys:
            keys = _validate_keys([key])
            assert keys == [key]

    def test_invalid_key_rejected(self):
        """Test invalid keys are rejected"""
        with pytest.raises(ValueError, match="Invalid key"):
            _validate_keys(["invalid_key"])

        with pytest.raises(ValueError, match="Invalid key"):
            _validate_keys(["ctrl", "malicious"])

    def test_keys_not_list(self):
        """Test non-list input is rejected"""
        with pytest.raises(ValueError, match="must be list"):
            _validate_keys("ctrl")

        with pytest.raises(ValueError, match="must be list"):
            _validate_keys({"key": "ctrl"})

    def test_empty_keys(self):
        """Test empty key list is rejected"""
        with pytest.raises(ValueError, match="cannot be empty"):
            _validate_keys([])

    def test_keys_with_non_string(self):
        """Test keys with non-string elements are rejected"""
        with pytest.raises(ValueError, match="must be string"):
            _validate_keys(["ctrl", 123])

        with pytest.raises(ValueError, match="must be string"):
            _validate_keys([None])


class TestNumberValidation:
    """Test numeric validation"""

    def test_valid_number(self):
        """Test valid numbers pass"""
        num = _validate_number(42, "test")
        assert num == 42.0

        num = _validate_number(3.14, "test")
        assert num == 3.14

    def test_number_with_bounds(self):
        """Test number validation with bounds"""
        num = _validate_number(50, "test", min_val=0, max_val=100)
        assert num == 50.0

    def test_number_below_minimum(self):
        """Test number below minimum is rejected"""
        with pytest.raises(ValueError, match="must be >= 10"):
            _validate_number(5, "test", min_val=10)

    def test_number_above_maximum(self):
        """Test number above maximum is rejected"""
        with pytest.raises(ValueError, match="must be <= 100"):
            _validate_number(150, "test", max_val=100)

    def test_number_not_numeric(self):
        """Test non-numeric input is rejected"""
        with pytest.raises(ValueError, match="must be numeric"):
            _validate_number("not a number", "test")

        with pytest.raises(ValueError, match="must be numeric"):
            _validate_number(None, "test")

        with pytest.raises(ValueError, match="must be numeric"):
            _validate_number([1, 2, 3], "test")


class TestIntegrationSecurity:
    """Integration tests for security"""

    def test_repr_escaping(self):
        """Test that repr() properly escapes malicious strings"""
        malicious_text = '"); import os; os.system("rm -rf /")'

        # When we use repr(), it should escape everything
        escaped = repr(malicious_text)

        # The repr should contain escaped quotes
        assert '\\"' in escaped or "'" in escaped

        # Executing f"pyautogui.write({malicious_text!r})" should be safe
        code = f"import pyautogui\npyautogui.write({malicious_text!r})"

        # The code should contain the escaped string
        assert malicious_text not in code or escaped in code

    def test_coordinate_injection_in_code_generation(self):
        """Test that validated coordinates can't inject code"""
        # Valid coordinates should work
        x_safe, y_safe = _validate_coordinates(100, 200)
        code = f"import pyautogui\npyautogui.click({x_safe}, {y_safe})"

        # Code should be exactly what we expect
        assert code == "import pyautogui\npyautogui.click(100, 200)"

        # No way to inject because validation rejects non-integers
        # (tested above in TestCoordinateValidation)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
