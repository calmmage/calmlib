from enum import Enum

from calmlib.extras.check_mode.check_mode import check_mode


class SampleMode(Enum):
    MODE_1 = 1
    MODE_2 = 2


class SampleClass:
    def __init__(self, mode=SampleMode.MODE_1):

        self.mode = SampleMode(mode)

    @check_mode(allowed_modes=[SampleMode.MODE_1])
    def sample_method_1(self):
        print(f"sample_method1, mode: {self.mode}, allowed modes: {SampleMode.MODE_1}")

    @check_mode(allowed_modes=[SampleMode.MODE_2])
    def sample_method_2(self):
        print(f"sample_method2, mode: {self.mode}, allowed modes: {SampleMode.MODE_2}")

    @check_mode(allowed_modes=[SampleMode.MODE_1, SampleMode.MODE_2])
    def sample_method_3(self):
        print(f"sample_method12, mode: {self.mode}, allowed modes: {SampleMode.MODE_1, SampleMode.MODE_2}")

    @check_mode()
    def sample_method_4(self):
        print(f"sample_method0, mode: {self.mode}, allowed modes: None")

    @check_mode(allowed_modes=[])
    def sample_method_5(self):
        print(f"sample_method, mode: {self.mode}, allowed modes: []")


if __name__ == "__main__":
    for sample in [
        SampleClass(),
        SampleClass(mode=SampleMode.MODE_1),
        SampleClass(mode=SampleMode.MODE_2),
    ]:
        print(f"Sample: {sample.mode}")
        for func in [
            sample.sample_method_1,
            sample.sample_method_2,
            sample.sample_method_3,
            sample.sample_method_4,
            sample.sample_method_5,
        ]:
            try:
                func()
            except Exception as e:
                print(e)
        print()
