from clingo import ast


class VariableCollector(ast.Transformer):
    def __init__(self) -> None:
        self.variables: list[str] = []

    def visit_Variable(self, node: ast.AST) -> ast.AST:
        name = node.name
        if name != "_" and name not in self.variables:
            self.variables.append(name)
        return node


def variables_in_body(body: list[ast.AST]) -> list[str]:
    collector = VariableCollector()

    for literal in body:
        collector(literal)

    return collector.variables


def ast_to_string(node: ast.AST) -> str:
    return str(node)


def body_to_string(body: list[ast.AST]) -> str:
    return ", ".join(str(lit) for lit in body)


def is_rule_statement(statement: ast.AST) -> bool:
    return statement.ast_type == ast.ASTType.Rule


def rule_start_line(rule: ast.AST) -> int:
    return rule.location.begin.line