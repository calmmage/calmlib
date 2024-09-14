from unittest import TestCase

from calmlib.autocast import autocast_args


class TestAutocast(TestCase):
    def test_single_arg_no_ann(self):
        @autocast_args()
        def test(a):
            return a

        self.assertEqual(test(1), 1)

    def test_arg_kwarg_no_ann(self):
        @autocast_args()
        def test(a, b):
            return a, b

        self.assertEqual(test(1, b=2), (1, 2))

    def test_single_arg_ann(self):
        @autocast_args()
        def test(a: str):
            return a

        self.assertEqual(test("1"), "1")
        self.assertEqual(test(1), "1")

    def test_error_handling(self):
        @autocast_args()
        def test(a: int):
            return a

        self.assertRaises(test, 'a')
