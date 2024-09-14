import pytest
from calmlib.extras.check_mode.check_mode_example import SampleClass, SampleMode


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
    with pytest.raises(Exception):
        sample.sample_method_5()
