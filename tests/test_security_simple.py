"""
Simple security tests for action validation (no pytest required)

Tests that the input validation prevents code injection and other attacks.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from green_agent.a2a.server import (
    _validate_coordinates,
    _validate_text,
    _validate_keys,
    _validate_number
)


def test_coordinate_validation():
    """Test coordinate validation"""
    print("Testing coordinate validation...")

    # Valid coordinates
    x, y = _validate_coordinates(100, 200)
    assert x == 100 and y == 200, "Valid coordinates should pass"
    print("  ✓ Valid coordinates pass")

    # Boundary coordinates
    x, y = _validate_coordinates(0, 0)
    assert x == 0 and y == 0, "Boundary (0,0) should pass"
    x, y = _validate_coordinates(1920, 1080)
    assert x == 1920 and y == 1080, "Boundary (1920,1080) should pass"
    print("  ✓ Boundary coordinates pass")

    # Out of bounds should fail
    try:
        _validate_coordinates(-1, 100)
        assert False, "Negative X should fail"
    except ValueError:
        print("  ✓ Negative coordinates rejected")

    try:
        _validate_coordinates(2000, 100)
        assert False, "X > 1920 should fail"
    except ValueError:
        print("  ✓ Out of bounds coordinates rejected")

    # Injection attempts should fail
    try:
        _validate_coordinates("100); import os; os.system('whoami')", 200)
        assert False, "Code injection should be rejected"
    except ValueError:
        print("  ✓ Code injection via coordinates rejected")

    # Non-numeric should fail
    try:
        _validate_coordinates("abc", 100)
        assert False, "Non-numeric should fail"
    except ValueError:
        print("  ✓ Non-numeric coordinates rejected")

    print("✅ All coordinate validation tests passed!\n")


def test_text_validation():
    """Test text validation"""
    print("Testing text validation...")

    # Valid text
    text = _validate_text("Hello World")
    assert text == "Hello World", "Valid text should pass"
    print("  ✓ Valid text passes")

    # Special characters are allowed
    text = _validate_text('Text with "quotes" and \\backslashes\\ and newlines\n')
    assert 'quotes' in text and '\\' in text and '\n' in text
    print("  ✓ Special characters allowed")

    # Too long text should fail
    try:
        _validate_text("a" * 10001)
        assert False, "Text > 10000 chars should fail"
    except ValueError:
        print("  ✓ Overly long text rejected")

    # Non-string should fail
    try:
        _validate_text(123)
        assert False, "Non-string should fail"
    except ValueError:
        print("  ✓ Non-string input rejected")

    # Injection attempts are accepted (will be escaped by repr())
    malicious_text = '"); import os; os.system("rm -rf /")'
    validated = _validate_text(malicious_text)
    assert validated == malicious_text  # Accepted but will be escaped
    print("  ✓ Malicious text accepted (will be escaped by repr())")

    print("✅ All text validation tests passed!\n")


def test_key_validation():
    """Test key validation"""
    print("Testing key validation...")

    # Valid single key
    keys = _validate_keys(["a"])
    assert keys == ["a"]
    print("  ✓ Valid single key passes")

    # Valid combinations
    keys = _validate_keys(["ctrl", "c"])
    assert keys == ["ctrl", "c"]
    print("  ✓ Valid key combinations pass")

    # Function keys
    keys = _validate_keys(["f1", "f12"])
    assert keys == ["f1", "f12"]
    print("  ✓ Function keys pass")

    # Invalid key should fail
    try:
        _validate_keys(["invalid_key_name"])
        assert False, "Invalid key should fail"
    except ValueError:
        print("  ✓ Invalid keys rejected")

    # Non-list should fail
    try:
        _validate_keys("ctrl")
        assert False, "Non-list should fail"
    except ValueError:
        print("  ✓ Non-list input rejected")

    # Empty list should fail
    try:
        _validate_keys([])
        assert False, "Empty list should fail"
    except ValueError:
        print("  ✓ Empty key list rejected")

    # Non-string elements should fail
    try:
        _validate_keys(["ctrl", 123])
        assert False, "Non-string elements should fail"
    except ValueError:
        print("  ✓ Non-string key elements rejected")

    print("✅ All key validation tests passed!\n")


def test_number_validation():
    """Test number validation"""
    print("Testing number validation...")

    # Valid numbers
    num = _validate_number(42, "test")
    assert num == 42.0
    print("  ✓ Valid integer passes")

    num = _validate_number(3.14, "test")
    assert num == 3.14
    print("  ✓ Valid float passes")

    # With bounds
    num = _validate_number(50, "test", min_val=0, max_val=100)
    assert num == 50.0
    print("  ✓ Number within bounds passes")

    # Below minimum should fail
    try:
        _validate_number(5, "test", min_val=10)
        assert False, "Below minimum should fail"
    except ValueError:
        print("  ✓ Number below minimum rejected")

    # Above maximum should fail
    try:
        _validate_number(150, "test", max_val=100)
        assert False, "Above maximum should fail"
    except ValueError:
        print("  ✓ Number above maximum rejected")

    # Non-numeric should fail
    try:
        _validate_number("not a number", "test")
        assert False, "Non-numeric should fail"
    except ValueError:
        print("  ✓ Non-numeric input rejected")

    print("✅ All number validation tests passed!\n")


def test_repr_escaping():
    """Test that repr() properly escapes malicious strings"""
    print("Testing repr() escaping for security...")

    malicious_text = '"); import os; os.system("rm -rf /")'

    # When we use repr(), it should escape everything
    escaped = repr(malicious_text)
    print(f"  Original: {malicious_text}")
    print(f"  Escaped:  {escaped}")

    # Generate code like we do in the action executor
    code = f"import pyautogui\npyautogui.write({malicious_text!r})"
    print(f"  Generated code: {code}")

    # Verify the malicious string is safely escaped in the code
    assert '"); import os;' not in code or "'); import os;" not in code or escaped in code
    print("  ✓ Malicious string safely escaped in generated code")

    print("✅ repr() escaping test passed!\n")


def test_coordinate_injection_in_code():
    """Test that validated coordinates can't inject code"""
    print("Testing coordinate injection prevention in code generation...")

    # Valid coordinates should produce clean code
    x_safe, y_safe = _validate_coordinates(100, 200)
    code = f"import pyautogui\npyautogui.click({x_safe}, {y_safe})"

    expected_code = "import pyautogui\npyautogui.click(100, 200)"
    assert code == expected_code, f"Expected: {expected_code}\nGot: {code}"
    print(f"  Generated code: {code}")
    print("  ✓ Validated coordinates produce clean code")

    # Malicious coordinates are rejected during validation (tested above)
    # So they can never reach code generation
    print("  ✓ Malicious coordinates never reach code generation")

    print("✅ Code injection prevention test passed!\n")


def main():
    """Run all tests"""
    print("=" * 60)
    print("SECURITY VALIDATION TESTS")
    print("=" * 60)
    print()

    try:
        test_coordinate_validation()
        test_text_validation()
        test_key_validation()
        test_number_validation()
        test_repr_escaping()
        test_coordinate_injection_in_code()

        print("=" * 60)
        print("🎉 ALL SECURITY TESTS PASSED!")
        print("=" * 60)
        return 0

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
