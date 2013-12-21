import unittest

import re
from peg import *


Int = Transform(re.compile(r'\d+'), int)
Number = Token(r'\d+')


class TestSimpleExpressions(unittest.TestCase):
    def test_single_token_success(self):
        ans = parse_all(Number, '123')
        self.assertIsInstance(ans, BaseToken)
        self.assertIsInstance(ans, Number)
        self.assertEqual(ans.content, '123')

    def test_single_token_failure(self):
        with self.assertRaises(ParseError):
            parse_all(Number, '123X')

    def test_prefix_token_success(self):
        ans = parse(Number, '123ABC')
        self.assertIsInstance(ans, ParseResult)
        token, pos = ans
        self.assertIsInstance(token, BaseToken)
        self.assertIsInstance(token, Number)
        self.assertEqual(token.content, '123')
        self.assertEqual(pos, 3)

    def test_prefix_token_failure(self):
        with self.assertRaises(ParseError):
            parse(Number, 'ABC')

    def test_simple_transform(self):
        ans = parse_all(Int, '123')
        self.assertEqual(ans, 123)

    def test_left_assoc(self):
        Add = LeftAssoc(Int, '+', Int)
        ans = parse_all(Add, '1+2+3+4')
        A = lambda x, y: BinaryOperation(x, '+', y)
        self.assertEqual(ans, A(A(A(1, 2), 3), 4))

    def test_right_assoc(self):
        Arrow = RightAssoc(Int, '->', Int)
        ans = parse_all(Arrow, '1->2->3->4')
        A = lambda x, y: BinaryOperation(x, '->', y)
        self.assertEqual(ans, A(1, A(2, A(3, 4))))

    def test_simple_struct(self):
        class Pair(Struct):
            def __init__(self):
                self.left = Int
                self.sep = ','
                self.right = Int

        ans = parse_all(Pair, '10,20')
        self.assertIsInstance(ans, Pair)
        self.assertEqual(ans.left, 10)
        self.assertEqual(ans.sep, ',')
        self.assertEqual(ans.right, 20)

if __name__ == '__main__':
    unittest.main()