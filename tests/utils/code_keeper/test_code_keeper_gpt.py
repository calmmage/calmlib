import json
import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from calmlib.utils.code_keeper import CodeKeeper, CodeGarden, GardenArea

tmp_path = TemporaryDirectory()


@pytest.fixture
def code_garden(tmp_path):
    code_garden_path = tmp_path / 'code_garden'
    shutil.copytree('tests/fixtures/code_garden', code_garden_path)
    return CodeGarden(code_garden_path)


# 1 Test CodeGarden initialization:
def test_code_garden_initialization(code_garden, tmp_path):
    # Test with default path
    code_garden_default_path = CodeGarden()
    assert code_garden_default_path.path == Path(
        os.path.expanduser('~/code_garden'))

    # Test with custom path
    assert code_garden.path == Path(tmp_path) / 'code_garden'


# 2 Test CodeGarden save method
def test_code_garden_save(code_garden):
    # Test saving code with valid parameters
    code = "print('Hello World')"
    tags = ['test']
    area = GardenArea.inbox
    metadata = {'description': 'Test code'}
    code_garden.save(code, tags, area, metadata=metadata, force=False)
    path = code_garden.path / area.value / 'test.py'
    assert path.exists()
    assert path.read_text() == f"# metadata {json.dumps(metadata)}\n{code}"

    # Test saving code with duplicate tags and force=False
    with pytest.raises(ValueError):
        code_garden.save(code, tags, area, metadata=metadata, force=False)

    # Test saving code with duplicate tags and force=True
    code_garden.save(code, tags, area, metadata=metadata, force=True)
    assert path.exists()
    assert path.read_text() == f"# metadata {json.dumps(metadata)}\n{code}"


# 3 Test CodeGarden find method:
def test_code_garden_find(code_garden):
    # Test finding code with valid parameters
    code = "print('Hello World')"
    tags = ['test1']
    area = GardenArea.main
    metadata = {'description': 'Test code'}
    code_garden.save(code, tags, area, metadata=metadata, force=True)
    result = code_garden.find(keys=tags, area=area, keys_and=True)
    assert len(result) == 1
    assert result[tags[0]].code == code
    assert result[tags[0]].tags == tags
    assert result[tags[0]].area == area

    # Test finding code with invalid tag
    result = code_garden.find(keys=['invalid'], area=area, keys_and=True)
    assert len(result) == 0

    # Test finding code with valid and invalid tags
    result = code_garden.find(keys=['test1', 'invalid'], area=area,
                              keys_and=True)
    assert len(result) == 0

    # Test finding code with valid and invalid tags and keys_and=False
    result = code_garden.find(keys=['test1', 'invalid'], area=area,
                              keys_and=False)
    assert len(result) == 1
    assert result[tags[0]].code == code
    assert result[tags[0]].tags == tags
    assert result[tags[0]].area == area


# Test CodeKeeper initialization:
def test_code_keeper_initialization(code_garden):
    # Test with default code garden
    code_keeper = CodeKeeper()
    assert isinstance(code_keeper.code_garden, CodeGarden)

    # Test with custom code garden path
    code_keeper = CodeKeeper(code_garden)
    assert code_keeper.code_garden.path == code_garden.path


# test 5:
def test_code_keeper_remind(code_garden):
    # Test reminding with valid parameters
    code_keeper = CodeKeeper(code_garden)
    result = code_keeper.remind(keys='tag2.tag3', area=GardenArea.main,
                                keys_and=True)
    assert len(result) == 1
    assert "# test1.code1" in result

    # Test reminding with invalid tag
    result = code_keeper.remind(keys='invalid', area=GardenArea.main,
                                keys_and=True)
    assert result == ""

    # Test reminding with valid and invalid tags
    result = code_keeper.remind(keys=['test1', 'invalid'], area=GardenArea.main,
                                keys_and=True)
    assert result == ""

    # Test reminding with valid and invalid tags and keys_and=False
    result = code_keeper.remind(keys=['tag1', 'tag2'], area=GardenArea.main,
                                keys_and=False)
    assert len(result) == 2
    assert "# test1.code1" in result
    assert "# test2.code1" in result


@pytest.mark.parametrize("tags,area,expected_count,results", [
    (['tag1'], GardenArea.inbox, 2, ['inbox/tag1.py', 'inbox/tag1.tag9.py']),
    (['tag1'], None, 4, ['inbox/tag1.py', 'inbox/tag1.tag9.py',
                         'secondary/tag1.tag2.tag7.py',
                         'secondary/tag2.tag3.tag1.tag4.tag5.py']),
    (['tag2', 'tag3'], GardenArea.inbox, 1, ['inbox/tag2.tag3.py']),
    (['tag2', 'tag3'], None, 3, ['inbox/tag2.tag3.py', 'main/tag2.tag3.py',
                                 'secondary/tag2.tag3.tag1.tag4.tag5.py']),
    (['tag3'], GardenArea.secondary, 1,
     ['secondary/tag2.tag3.tag1.tag4.tag5.py']),
])
def test_code_garden_find(code_garden, tags, area, expected_count, results):
    result = code_garden.find(keys=tags, area=area, keys_and=True)
    assert len(result) == expected_count
    assert set(result.keys()) == set(results)


@pytest.mark.parametrize("tagline,area,expected_count,results", [
    ('tag1', GardenArea.inbox, 2, ['inbox/tag1.py', 'inbox/tag1.tag9.py']),
    ('tag1', None, 4, ['inbox/tag1.py', 'inbox/tag1.tag9.py',
                       'secondary/tag1.tag2.tag7.py',
                       'secondary/tag2.tag3.tag1.tag4.tag5.py']),
    ('tag2.tag3', GardenArea.inbox, 1, ['inbox/tag2.tag3.py']),
    ('tag3.tag2', None, 3, ['inbox/tag2.tag3.py', 'main/tag2.tag3.py',
                            'secondary/tag2.tag3.tag1.tag4.tag5.py']),
    (['tag3'], GardenArea.secondary, 1,
     ['secondary/tag2.tag3.tag1.tag4.tag5.py']),
])
def test_code_keeper_remind(code_garden, tagline, area, expected_count,
                            results):
    code_keeper = CodeKeeper(code_garden)
    result = code_keeper.remind(keys=tagline, area=area)
    # assert len(result) == expected_count
    assert all([key in result for key in results])
    # print(result)


# test 0: generate_summary_by_tag
@pytest.mark.parametrize("limit,swimlines,expected_result", [
    (None, 5,
     'tag2: 5\n'
     'tag1: 4\n'
     'tag3: 3\n'
     'tag4: 2\n'
     'tag5: 1\n'
     '~~~~~~~~~~~~~~~~~~\n'
     'tag7: 1\n'
     'tag9: 1\n'
     'code: 1\n'
     'keeper: 1\n'
     'garden: 1\n'
     '~~~~~~~~~~~~~~~~~~\n'
     'remind: 1\n'
     '~~~~~~~~~~~~~~~~~~'),
    (3, 5, "tag2: 5\ntag1: 4\ntag3: 3\n~~~~~~~~~~~~~~~~~~"),
    (None, 2, 'tag2: 5\n'
              'tag1: 4\n'
              '~~~~~~~~~~~~~~~~~~\n'
              'tag3: 3\n'
              'tag4: 2\n'
              '~~~~~~~~~~~~~~~~~~\n'
              'tag5: 1\n'
              'tag7: 1\n'
              '~~~~~~~~~~~~~~~~~~\n'
              'tag9: 1\n'
              'code: 1\n'
              '~~~~~~~~~~~~~~~~~~\n'
              'keeper: 1\n'
              'garden: 1\n'
              '~~~~~~~~~~~~~~~~~~\n'
              'remind: 1\n'
              '~~~~~~~~~~~~~~~~~~'),
])
def test_generate_summary_by_tag(code_garden, limit, swimlines,
                                 expected_result):
    result = code_garden.generate_summary_by_tag(limit=limit,
                                                 swimlines=swimlines)
    assert result == expected_result

    # # Check if the output is sorted in descending order of tag count
    # all_patterns = code_garden.find("")
    # counter = Counter()
    # for pattern in all_patterns.values():
    #     counter.update(pattern.tags)
    # tags_sorted_by_count = [tag for tag, count in counter.most_common()]
    # tags_in_result = [line.split(":")[0] for line in
    #                   result.split(code_garden.SWIMLINE)[0].split("\n") if line]
    # assert tags_sorted_by_count[:len(tags_in_result)] == tags_in_result


# test 6 Test CodeKeeper plant method:
def test_code_keeper_plant(code_garden):
    # Test planting with valid parameters
    code_keeper = CodeKeeper(code_garden)
    code = "print('Hello World')"
    tagline = "main/test"
    code_keeper.plant(code, tagline, force=True)
    result = code_keeper.remind(keys='test', area=GardenArea.main,
                                keys_and=True)
    assert "# main/test.py" in result

    # Test planting with duplicate tag and force=False
    with pytest.raises(ValueError):
        code_keeper.plant(code, tagline, area=GardenArea.main, force=False)

    # Test planting with duplicate tag and force=True
    code_keeper.plant(code, tagline, area=GardenArea.main, force=True)
    result = code_keeper.remind(keys='test', area=GardenArea.main,
                                keys_and=True)
    assert result == "# main/test.py\nprint('Hello World')\n\n"


# 7 Test CodeKeeper _parse_tagline method:
def test_code_keeper_parse_tagline():
    code_keeper = CodeKeeper()

    # Test parsing tagline with no slashes
    tagline = 'test'
    result = code_keeper._parse_tagline(tagline)
    assert result == ['test']

    # Test parsing tagline with one slash
    tagline = 'test1.test2'
    result = code_keeper._parse_tagline(tagline)
    assert result == ['test1', 'test2']

    # Test parsing tagline with multiple slashes
    tagline = 'test1.test2_test3'
    result = code_keeper._parse_tagline(tagline)
    assert result == ['test1', 'test2_test3']


# 8 Test CodeGarden _find_paths method:
def test_code_garden_find_paths(code_garden):
    # Test finding paths with valid parameters and keys_and=True
    result = list(code_garden._find_paths(keys=['tag1'], area=GardenArea.inbox,
                                          keys_and=True))
    assert len(result) == 2
    assert {r.name for r in result} == {'tag1.py', 'tag1.tag9.py'}
