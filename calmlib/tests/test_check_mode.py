from enum import Enum

import pytest


class SampleMode(Enum):
    MODE_1 = "mode_1"
    MODE_2 = "mode_2"


class SampleClass:
    def __init__(self, mode: SampleMode = None):
        self.mode = mode

    def sample_method_1(self):
        if self.mode == SampleMode.MODE_2:
            raise Exception("Method 1 not allowed in MODE_2")
        return None

    def sample_method_2(self):
        if self.mode != SampleMode.MODE_2:
            raise Exception("Method 2 only allowed in MODE_2")
        return None

    def sample_method_3(self):
        return None

    def sample_method_4(self):
        return None

    def sample_method_5(self):
        if self.mode != SampleMode.MODE_2:
            raise Exception("Method 5 only allowed in MODE_2")
        return None


def test_sample_class_default_mode_method_1():
    sample = SampleClass()
    assert sample.sample_method_1() is None


def test_sample_class_mode_1_method_1():
    sample = SampleClass(mode=SampleMode.MODE_1)
    assert sample.sample_method_1() is None


def test_sample_class_mode_2_method_1():
    sample = SampleClass(mode=SampleMode.MODE_2)
    with pytest.raises(Exception):
        sample.sample_method_1()


def test_sample_class_default_mode_method_2():
    sample = SampleClass()
    with pytest.raises(Exception):
        sample.sample_method_2()


def test_sample_class_mode_1_method_2():
    sample = SampleClass(mode=SampleMode.MODE_1)
    with pytest.raises(Exception):
        sample.sample_method_2()


def test_sample_class_mode_2_method_2():
    sample = SampleClass(mode=SampleMode.MODE_2)
    assert sample.sample_method_2() is None


def test_sample_class_default_mode_method_3():
    sample = SampleClass()
    assert sample.sample_method_3() is None


def test_sample_class_mode_1_method_3():
    sample = SampleClass(mode=SampleMode.MODE_1)
    assert sample.sample_method_3() is None


def test_sample_class_mode_2_method_3():
    sample = SampleClass(mode=SampleMode.MODE_2)
    assert sample.sample_method_3() is None


def test_sample_class_default_mode_method_4():
    sample = SampleClass()
    assert sample.sample_method_4() is None


def test_sample_class_mode_1_method_4():
    sample = SampleClass(mode=SampleMode.MODE_1)
    assert sample.sample_method_4() is None


def test_sample_class_mode_2_method_4():
    sample = SampleClass(mode=SampleMode.MODE_2)
    assert sample.sample_method_4() is None


def test_sample_class_default_mode_method_5():
    sample = SampleClass()
    with pytest.raises(Exception):
        sample.sample_method_5()


def test_sample_class_mode_1_method_5():
    sample = SampleClass(mode=SampleMode.MODE_1)
    with pytest.raises(Exception):
        sample.sample_method_5()


def test_sample_class_mode_2_method_5():
    sample = SampleClass(mode=SampleMode.MODE_2)
    assert sample.sample_method_5() is None
