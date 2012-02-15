__author__ = 'roke'

"""Tests for multimethods."""

import unittest

class MultimethodTestCase(unittest.TestCase):


    def test_multimethods(self):
        "Multimethod are actually dispatched"

        from multimethods import multimethod
        class A(object):

            @multimethod(int, int)
            def foo(self, a, b):
                return "int, int"

            @multimethod(float, float)
            def foo(self, a, b):
                return "float, float"

            @multimethod(str, str)
            def foo(self, a, b):
                return "str, str"

            @multimethod(int, condition="a>3")
            def foo(self, a):
                return "a>3"

            @multimethod(int, condition="a<=3")
            def foo(self, a):
                return "a<=3"

        x = A()
        self.assertEqual(x.foo(1, 2), "int, int")
        self.assertEqual(x.foo(1.0, 1.0), 'float, float')
        self.assertEqual(x.foo("1", "2"), 'str, str')
        self.assertEqual(x.foo(5), "a>3")
        self.assertEqual(x.foo(1), "a<=3")


        with self.assertRaises(ValueError):
            x.foo(3, 4.5)


    def test_multimethod_class_instance(self):
        "The class instance is addressed by the multimethod"

        from multimethods import multimethod
        class A(object):

            def __init__(self, c):
                self.c = c

            @multimethod(int, int)
            def foo(self, a, b):
                return self.c + a + b


        x = A(3)
        self.assertEqual(x.foo(1, 2), 6)
        self.assertIsInstance(A.foo, multimethod._Dispatcher)

    def get_reference_exception_message(self):
        def multimethod(condition=None):
            "Dummy to retrieve the exception text."
        with self.assertRaises(TypeError) as ref:
            multimethod(invalid_arg=False)
        return str(ref.exception)

    def test_multimethod_subclasse(self):
        "Multimethods work on instances of subclasses too"

        from numbers import Number
        from multimethods import multimethod

        @multimethod(Number)
        def isnumber(x):
            return True

        @multimethod(object)
        def isnumber(x):
            return False

        self.assertTrue(isnumber(3.4))
        self.assertTrue(isnumber(4))
        self.assertTrue(isnumber(2 ** 65))
        self.assertFalse(isnumber('3'))

    def test_multimethod_function(self):
        "The multimethod works on functions"

        from multimethods import multimethod

        @multimethod(int, int)
        def foo(a, b):
            return "int, int"

        @multimethod(float, float)
        def foo(a, b):
            return "float, float"

        @multimethod(str, str)
        def foo(a, b):
            return "str, str"

        @multimethod(int, condition="a>3")
        def foo(a):
            return "a>3"

        @multimethod(int, condition="a<=3")
        def foo(a):
            return "a<=3"

        self.assertEqual(foo(1, 2), 'int, int')
        self.assertEqual(foo(1.0, 1.0), 'float, float')
        self.assertEqual(foo("1", "2"), 'str, str')

        self.assertEqual(foo(5), "a>3")
        self.assertEqual(foo(1), "a<=3")

        with self.assertRaises(ValueError) as cm:
            foo(1.3)

        with self.assertRaises(TypeError) as cm:
            multimethod(int, invalid_arg=False)

        self.assertEqual(str(cm.exception), self.get_reference_exception_message())

