# # import re
# import pytest
#
# # split_pattern = re.compile("[._]")
# #
# # def parse_tagline(tagline):
# #     return set(split_pattern.split(tagline))
# from code_keeper import parse_tagline
# @pytest.mark.parametrize("tagline, expected_output", [
#     ("sample", set(["sample"])),
#     ("sample_tag_set.test.garden", set(['sample', 'tag', 'set', 'test', 'garden'])),
#     ("", set()),
#     ("._._.", set()),
#     ("sample_test_set.garden#1", set(['sample', 'test', 'set', 'garden#1']))
# ])
# def test_parse_tagline(tagline, expected_output):
#     assert parse_tagline(tagline) == expected_output
