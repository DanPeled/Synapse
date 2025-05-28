from synapse.core.settings_api import (
    BooleanConstraint,
    ColorConstraint,
    ConstraintType,
    ListConstraint,
    ListOptionsConstraint,
    RangeConstraint,
    StringConstraint,
)

# ------------------ RangeConstraint ------------------


def test_range_constraint_valid():
    c = RangeConstraint(0, 10)
    result = c.validate(5)
    assert result.isValid
    assert result.normalizedValue == 5


def test_range_constraint_out_of_bounds():
    c = RangeConstraint(0, 10)
    result = c.validate(15)
    assert not result.isValid
    if result.errorMessage:
        assert "outside range" in result.errorMessage


def test_range_constraint_with_step():
    c = RangeConstraint(0, 10, step=2)
    result = c.validate(3)
    assert result.isValid
    assert result.normalizedValue == 4  # Snapped


# ------------------ ListOptionsConstraint ------------------


def test_list_options_constraint_single_valid():
    c = ListOptionsConstraint(["a", "b", "c"])
    result = c.validate("a")
    assert result.isValid


def test_list_options_constraint_single_invalid():
    c = ListOptionsConstraint(["a", "b", "c"])
    result = c.validate("x")
    assert not result.isValid


def test_list_options_constraint_multiple_valid():
    c = ListOptionsConstraint(["a", "b", "c"], allowMultiple=True)
    result = c.validate(["a", "b"])
    assert result.isValid


def test_list_options_constraint_multiple_invalid():
    c = ListOptionsConstraint(["a", "b", "c"], allowMultiple=True)
    result = c.validate(["a", "x"])
    assert not result.isValid
    if result.errorMessage:
        assert "Invalid options" in result.errorMessage


# ------------------ ColorConstraint ------------------


def test_color_constraint_hex_valid_string_short():
    c = ColorConstraint(formatType="hex")
    result = c.validate("#abc")
    assert result.isValid
    assert result.normalizedValue == "#ABC"


def test_color_constraint_hex_valid_string_full():
    c = ColorConstraint(formatType="hex")
    result = c.validate("#aabbcc")
    assert result.isValid
    assert result.normalizedValue == "#AABBCC"


def test_color_constraint_hex_valid_string_with_0x():
    c = ColorConstraint(formatType="hex")
    result = c.validate("0xAABBCC")
    assert result.isValid
    assert result.normalizedValue == "#AABBCC"


def test_color_constraint_hex_valid_int():
    c = ColorConstraint(formatType="hex")
    result = c.validate(0xAABBCC)
    assert result.isValid
    assert result.normalizedValue == "#AABBCC"


def test_color_constraint_hex_invalid_format():
    c = ColorConstraint(formatType="hex")
    result = c.validate("abc")
    assert not result.isValid


def test_color_constraint_hex_invalid_length():
    c = ColorConstraint(formatType="hex")
    result = c.validate("#abcd")
    assert not result.isValid


def test_color_constraint_hex_invalid_value():
    c = ColorConstraint(formatType="hex")
    result = c.validate("#ghz")
    assert not result.isValid


def test_color_constraint_rgb_string_valid():
    c = ColorConstraint(formatType="rgb")
    result = c.validate("rgb(10, 20, 30)")
    assert result.isValid
    assert result.normalizedValue == "rgb(10, 20, 30)"


def test_color_constraint_rgb_tuple_valid():
    c = ColorConstraint(formatType="rgb")
    result = c.validate((10, 20, 30))
    assert result.isValid
    assert result.normalizedValue == "rgb(10, 20, 30)"


def test_color_constraint_rgb_tuple_invalid_length():
    c = ColorConstraint(formatType="rgb")
    result = c.validate((10, 20))
    assert not result.isValid


def test_color_constraint_rgb_tuple_invalid_type():
    c = ColorConstraint(formatType="rgb")
    result = c.validate((10, "20", 30))
    assert not result.isValid


def test_color_constraint_rgb_value_out_of_range():
    c = ColorConstraint(formatType="rgb")
    result = c.validate((256, 20, 30))
    assert not result.isValid


def test_color_constraint_rgb_string_invalid_format():
    c = ColorConstraint(formatType="rgb")
    result = c.validate("rgb(10,20)")  # missing third value
    assert not result.isValid


def test_color_constraint_rgb_string_with_percent_not_allowed():
    c = ColorConstraint(formatType="rgb")
    result = c.validate("rgb(10%, 20%, 30%)")
    assert not result.isValid


def test_color_constraint_hsv_string_valid():
    c = ColorConstraint(formatType="hsv")
    result = c.validate("hsv(180, 50, 75)")
    assert result.isValid
    assert result.normalizedValue == "hsv(180, 50, 75)"


def test_color_constraint_hsv_tuple_valid():
    c = ColorConstraint(formatType="hsv")
    result = c.validate((180, 50, 75))
    assert result.isValid
    assert result.normalizedValue == "hsv(180, 50, 75)"


def test_color_constraint_hsv_tuple_invalid_length():
    c = ColorConstraint(formatType="hsv")
    result = c.validate((180, 50))
    assert not result.isValid


def test_color_constraint_hsv_tuple_invalid_type():
    c = ColorConstraint(formatType="hsv")
    result = c.validate((180, 50, "75"))
    assert not result.isValid


def test_color_constraint_hsv_value_out_of_range():
    c = ColorConstraint(formatType="hsv")
    result = c.validate((361, 50, 75))  # Hue > 360
    assert not result.isValid


def test_color_constraint_hsv_string_invalid_format():
    c = ColorConstraint(formatType="hsv")
    result = c.validate("hsv(180, 50)")  # missing V
    assert not result.isValid


def test_color_constraint_hsv_string_with_percent_not_allowed():
    c = ColorConstraint(formatType="hsv")
    result = c.validate("hsv(180, 50%, 75%)")
    assert not result.isValid


def test_color_constraint_wrong_type_input():
    c = ColorConstraint(formatType="hex")
    result = c.validate(12.34)  # float invalid for hex
    assert not result.isValid

    c = ColorConstraint(formatType="rgb")
    result = c.validate(123)  # int invalid for rgb string/tuple
    assert not result.isValid

    c = ColorConstraint(formatType="hsv")
    result = c.validate("notacolor")
    assert not result.isValid


def test_color_constraint_to_dict():
    c = ColorConstraint()
    d = c.toDict()
    assert d["type"] == ConstraintType.kColor.value
    assert d["formatType"] == "hex"

    c_rgb = ColorConstraint(formatType="rgb")
    d_rgb = c_rgb.toDict()
    assert d_rgb["formatType"] == "rgb"

    c_hsv = ColorConstraint(formatType="hsv")
    d_hsv = c_hsv.toDict()
    assert d_hsv["formatType"] == "hsv"


# ------------------ ListConstraint ------------------


def test_list_constraint_valid_length():
    c = ListConstraint(minLength=1, maxLength=3)
    result = c.validate([1, 2])
    assert result.isValid


def test_list_constraint_too_short():
    c = ListConstraint(minLength=2)
    result = c.validate([1])
    assert not result.isValid


def test_list_constraint_too_long():
    c = ListConstraint(maxLength=2)
    result = c.validate([1, 2, 3])
    assert not result.isValid


def test_list_constraint_with_itemConstraint():
    item_c = RangeConstraint(0, 10)
    c = ListConstraint(itemConstraint=item_c)
    result = c.validate([5, 8])
    assert result.isValid


def test_list_constraint_with_invalid_item():
    item_c = RangeConstraint(0, 10)
    c = ListConstraint(itemConstraint=item_c)
    result = c.validate([5, 20])
    assert not result.isValid
    if result.errorMessage:
        assert "Item at index" in result.errorMessage


# ------------------ StringConstraint ------------------


def test_string_constraint_valid():
    c = StringConstraint(minLength=2, maxLength=5)
    result = c.validate("abc")
    assert result.isValid


def test_string_constraint_too_short():
    c = StringConstraint(minLength=4)
    result = c.validate("abc")
    assert not result.isValid


def test_string_constraint_pattern_valid():
    c = StringConstraint(pattern=r"^abc\d+$")
    result = c.validate("abc123")
    assert result.isValid


def test_string_constraint_pattern_invalid():
    c = StringConstraint(pattern=r"^abc\d+$")
    result = c.validate("xyz")
    assert not result.isValid


# ------------------ BooleanConstraint ------------------


def test_boolean_constraint_true_values():
    c = BooleanConstraint()
    for val in [True, "true", "1", "yes", 1]:
        result = c.validate(val)
        assert result.isValid
        assert result.normalizedValue is True


def test_boolean_constraint_false_values():
    c = BooleanConstraint()
    for val in [False, "false", "0", "no", 0]:
        result = c.validate(val)
        assert result.isValid
        assert result.normalizedValue is False


def test_boolean_constraint_invalid():
    c = BooleanConstraint()
    result = c.validate("maybe")
    assert not result.isValid
