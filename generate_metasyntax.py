from sourcer import Grammar

grammar = Grammar(r'''
    ignored token Space = `[ \t]+`
    token Word = `[_a-zA-Z][_a-zA-Z0-9]*`
    token Symbol = `<<\!|\!>>|<<|>>|=>|\/\/|[=;,:\|\/\*\+\?\!\(\)\[\]\{\}]`

    token StringLiteral = (
        `("([^"\\]|\\.)*")`
        | `('([^'\\]|\\.)*')`
        | `("""([^\\]|\\.)*?""")`
        | `('\''([^\\]|\\.)*?'\'')`
    )

    token RegexLiteral = `\`([^\`\\]|\\.)*\``
    token Newline = `[\r\n][\s]*`
    ignored token Comment = `#[^\r\n]*`

    Sep = Some(Newline | ";")
    Name = Word

    template wrap(x) => Skip(Newline) >> x << Skip(Newline)

    Comma = wrap(",")

    class RuleDef {
        name: Name << ("=" | ":")
        expr: Expr
    }

    class ClassDef {
        name: "class" >> Name
        fields: wrap("{") >> (RuleDef / Sep) << "}"
    }

    class TokenDef {
        is_ignored: ("ignore" | "ignored")?
        child: "token" >> (ClassDef | RuleDef)
    }

    class TemplateDef {
        name: "template" >> Name
        params: wrap("(") >> (wrap(Name) / Comma) << ")"
        expr: wrap("=" | ":" | "=>") >> Expr
    }

    Def = TokenDef
        | ClassDef
        | TemplateDef
        | RuleDef

    class Ref {
        name: Word
    }

    class ListLiteral {
        elements: "[" >> (wrap(Expr) / Comma) << "]"
    }

    Atom = ("(" >> wrap(Expr) << ")")
        | Ref
        | StringLiteral
        | RegexLiteral
        | ListLiteral

    class KeywordArg {
        name: Name << ("=" | ":")
        expr: Expr
    }

    class ArgList {
        args: "(" >> (wrap(KeywordArg | Expr) / Comma) << ")"
    }

    Expr = OperatorPrecedence(
        Atom,
        Postfix(ArgList),
        Postfix("?" | "*" | "+" | "!"),
        LeftAssoc(wrap("/" | "//")),
        LeftAssoc(wrap("<<" | ">>" | "<<!" | "!>>")),
        LeftAssoc(wrap("|")),
    )

    # TODO: Implement `End`.
    start = Skip(Newline) >> (Def / Sep) # << End
''')

print('[')
for node in grammar._nodes:
    print(f'    {node!r},\n')
print(']')
