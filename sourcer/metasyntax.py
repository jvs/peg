from ast import literal_eval
from collections import defaultdict
import itertools
import re

from .expressions import *


class Grammar:
    def __init__(self, grammar):
        self.grammar = grammar
        self._env, self.parser = _create_parser(grammar)

    def __getattr__(self, name):
        if name in self._env:
            return self._env[name]
        else:
            raise AttributeError(f'Grammar has no value {name!r}.')

    def parse(self, text):
        return self.parser.parse(text)


def _create_parser(grammar):
    tree = metaparser.parse(grammar)

    from . import expressions
    env = dict(vars(expressions))

    env.update({'True': True, 'False': False, 'None': None, '#tokens': []})

    def lazy(name):
        return Lazy(lambda: env[name])

    for stmt in tree:
        env[stmt.name] = lazy(stmt.name)

    recoveries = defaultdict(list)
    for stmt in tree:
        result = stmt.evaluate(env)
        if _contains_commit(stmt):
            result = Checkpoint(result)
        if isinstance(stmt, Recover):
            recoveries[stmt.name].append(result)
        else:
            env[stmt.name] = result
        if isinstance(stmt, TokenDef):
            env['#tokens'].append(result)

    if 'start' not in env:
        raise Exception('Expected "start" definition.')

    for name, recovery in recoveries:
        if name not in env:
            raise Exception(f'Unknown rule in "recover" definition: {name}.')
        target = env[name]
        if not isinstance(target, Recover):
            target = Recover(target)
            env[name] = target
        target.add_recovery(recovery)

    parser = Parser(start=env['start'], tokens=[v for v in env['#tokens']])
    return env, parser


def _contains_commit(tree):
    for child in visit(tree):
        if isinstance(child, PostfixOp) and getattr(child.operator, 'value', None) == '!':
            return True
    return False


Whitespace = TokenPattern(r'[ \t]+', is_ignored=True)
Word = TokenPattern(r'[_a-zA-Z][_a-zA-Z0-9]*')
Symbol = TokenPattern(r'<<|>>|=>|\/\/|[=;,:\|\/\*\+\?\!\(\)\[\]\{\}]')
StringLiteral = TokenPattern(
    r'("([^"\\]|\\.)*")|'
    r"('([^'\\]|\\.)*')|"
    r'("""([^\\]|\\.)*?""")|'
    r"('''([^\\]|\\.)*?''')"
)
RegexLiteral = TokenPattern(r'`([^`\\]|\\.)*`')
Newline = TokenPattern(r'[\r\n][\s]*')
Comment = TokenPattern(r'#[^\r\n]*', is_ignored=True)

def transform_tokens(tokens):
    result = []
    depth = 0
    for token in tokens:
        # Drop newline tokens that appear within parentheses.
        if token.value in '([':
            depth += 1
        elif token.value in '])':
            depth -= 1
        elif depth > 0 and isinstance(token, Newline):
            continue
        result.append(token)
    return result

# A forward reference to the MetaExpr definition.
Ex = Lazy(lambda: MetaExpr)

# Statement separator.
Sep = Some(Newline | ';')

Name = Word * (lambda w: w.value)


def _wrap(x):
    return Skip(Newline) >> x << Skip(Newline)


class Let(Struct):
    name = Name << Commit(Choice('=', ':'))
    value = Ex

    def evaluate(self, env):
        result = _evaluate(env, self.value)
        if isinstance(result, type) and issubclass(result, Token):
            result.__name__ = self.name
        return result


class ClassDef(Struct):
    name = Commit('class') >> Name
    fields = _wrap('{') >> (Let / Sep) << '}'

    def evaluate(self, env):
        class cls(Struct): pass
        cls.__name__ = self.name
        for field in self.fields:
            setattr(cls, field.name, _evaluate(env, field.value))
        return cls


class RecoverDef(Struct):
    child = Commit('recover') >> Let

    @property
    def name(self):
        return self.child.name

    def evaluate(self, env):
        return self.child.evaluate(env)


class TokenDef(Struct):
    is_ignored = Opt(Choice('ignore', 'ignored'))
    child = Commit('token') >> (ClassDef | Let)

    @property
    def name(self):
        return self.child.name

    def evaluate(self, env):
        result = self.child.evaluate(env)
        if isinstance(self.child, Let) or self.is_ignored:
            result = TokenClass(result, is_ignored=self.is_ignored)
            result.__name__ = self.name
        return result


class Template(Struct):
    name = Commit('template') >> Name
    params = '(' >> (Name / ',') << ')'
    body = _wrap(Choice('=', ':', '=>')) >> Ex

    def evaluate(self, env):
        def wrapper(*a, **k):
            subenv = dict(env)
            for param, value in itertools.chain(zip(self.params, a), k.items()):
                subenv[param] = value
            return _evaluate(subenv, self.body)
        return wrapper


class ListLiteral(Struct):
    elements = Commit('[') >> (Ex / ',') << ']'

    def evaluate(self, env):
        return Seq(*[_evaluate(env, x) for x in self.elements])


Atom = Choice(
    Commit('(') >> Ex << ')',
    Word,
    StringLiteral,
    RegexLiteral,
    ListLiteral,
)


class KeywordArg(Struct):
    name = Name << Commit(Choice('=', ':'))
    value = Ex


class ArgList(Struct):
    args = Commit('(') >> ((KeywordArg | Ex) / ',') << ')'

    def evaluate(self, env):
        a, k = [], {}
        for arg in self.args:
            if isinstance(arg, KeywordArg):
                k[arg.name] = _evaluate(env, arg.value)
            else:
                a.append(_evaluate(env, arg))
        return a, k


MetaExpr = OperatorPrecedence(
    Atom,
    Postfix(ArgList),
    Postfix(Choice('?', '*', '+', '!')),
    LeftAssoc(_wrap(Choice('/', '//'))),
    LeftAssoc(_wrap(Choice('<<', '>>'))),
    LeftAssoc(_wrap('|')),
)

metaparser = Parser(
    start=Skip(Newline) >> ((TokenDef | ClassDef | RecoverDef | Template | Let) / Sep) << End,
    tokens=[
        Whitespace,
        Word,
        Symbol,
        StringLiteral,
        RegexLiteral,
        Newline,
        Comment,
    ],
    transform_tokens=transform_tokens,
)


def _evaluate(env, obj):
    if hasattr(obj, 'evaluate'):
        return obj.evaluate(env)

    if isinstance(obj, Word):
        name = obj.value
        if name in env:
            return env[name]
        else:
            raise Exception(f'Undefined: {name!r}')

    if isinstance(obj, StringLiteral):
        return literal_eval(obj.value)

    if isinstance(obj, RegexLiteral):
        return re.compile(obj.value[1:-1])

    operators = {
        '?': Opt,
        '*': List,
        '+': Some,
        '!': Commit,
        '/': lambda a, b: Alt(a, b, allow_trailer=True),
        '//': lambda a, b: Alt(a, b, allow_trailer=False),
        '<<': Left,
        '>>': Right,
        '|': Choice,
    }

    assert hasattr(obj, 'operator')
    operator = getattr(obj.operator, 'value', None)

    if isinstance(obj, InfixOp) and operator in operators:
        left = _evaluate(env, obj.left)
        right = _evaluate(env, obj.right)
        return operators[operator](left, right)

    if isinstance(obj, PostfixOp) and operator in operators:
        return operators[operator](_evaluate(env, obj.left))

    if isinstance(obj, PostfixOp):
        func = _evaluate(env, obj.left)
        if not callable(func):
            raise Exception(f'Not a callable function: {obj.left!r}')
        args, kwargs = _evaluate(env, obj.operator)
        return func(*args, **kwargs)

    raise Exception(f'Unexpected expression: {obj!r}')
