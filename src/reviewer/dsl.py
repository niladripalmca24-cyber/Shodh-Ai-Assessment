from __future__ import annotations
import ast
import re
from typing import Any, Dict, List, Optional, Tuple, Union
import z3


def normalize_time_to_seconds(text: str) -> int:
    """
    Normalizes time strings like '30 minutes', '25m', '1 hour', '1800s' into integer seconds.
    """
    text = str(text).strip().lower()
    
    # Matches patterns like '30 minutes', '30m', '30 min', '1 hour', '2h', '1800s', '1800'
    m = re.match(r"^(\d+)\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h)?$", text)
    if not m:
        # Fallback to integer conversion if possible
        try:
            return int(float(text))
        except ValueError:
            raise ValueError(f"Cannot parse time duration: '{text}'")
            
    val = int(m.group(1))
    unit = m.group(2) or "s"
    
    if unit in ("seconds", "second", "secs", "sec", "s"):
        return val
    elif unit in ("minutes", "minute", "mins", "min", "m"):
        return val * 60
    elif unit in ("hours", "hour", "hrs", "hr", "h"):
        return val * 3600
    else:
        return val


class ASTNode:
    pass


class Var(ASTNode):
    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return f"Var({self.name})"


class Const(ASTNode):
    def __init__(self, value: Any):
        self.value = value

    def __repr__(self):
        return f"Const({self.value!r})"


class IsMissing(ASTNode):
    def __init__(self, field: str):
        self.field = field

    def __repr__(self):
        return f"IsMissing({self.field})"


class BinaryOp(ASTNode):
    def __init__(self, op: str, left: ASTNode, right: ASTNode):
        self.op = op  # '==', '!=', '<', '<=', '>', '>=', 'and', 'or'
        self.left = left
        self.right = right

    def __repr__(self):
        return f"BinaryOp({self.op!r}, {self.left}, {self.right})"


class UnaryOp(ASTNode):
    def __init__(self, op: str, operand: ASTNode):
        self.op = op  # 'not'
        self.operand = operand

    def __repr__(self):
        return f"UnaryOp({self.op!r}, {self.operand})"


def parse_dsl_condition(text: str) -> ASTNode:
    """
    Parses a DSL condition string into an ASTNode.
    Handles:
      - IS_MISSING(field)
      - comparisons: ==, !=, <, <=, >, >=
      - time units: e.g., 'waiting >= 30 minutes', 'wait_seconds >= 1800'
      - nested and / or / not
    """
    text = text.strip()
    
    # Pre-process time units: replace 'X minutes', 'Xm', 'X hours', 'Xh', 'X seconds' with integer seconds
    def replace_time(match):
        val = int(match.group(1))
        unit = match.group(2).lower()
        if unit.startswith("m"):
            return str(val * 60)
        elif unit.startswith("h"):
            return str(val * 3600)
        elif unit.startswith("s"):
            return str(val)
        return str(val)

    # Replace duration expressions e.g. "30 minutes", "25m", "1 hour"
    norm_text = re.sub(r"\b(\d+)\s*(minutes?|mins?|m|hours?|hrs?|h|seconds?|secs?|s)\b", replace_time, text, flags=re.IGNORECASE)
    
    # Map common field aliases
    norm_text = re.sub(r"\bwaiting\b", "wait_seconds", norm_text, flags=re.IGNORECASE)
    norm_text = re.sub(r"\bwaiting_time\b", "wait_seconds", norm_text, flags=re.IGNORECASE)
    norm_text = re.sub(r"\burgent ticket\b", "urgent == True", norm_text, flags=re.IGNORECASE)
    norm_text = re.sub(r"\bmissing category\b", "IS_MISSING(category)", norm_text, flags=re.IGNORECASE)
    
    # Also handle IS_MISSING(category) syntax
    def is_missing_repl(match):
        field = match.group(1)
        return f"__is_missing__{field}__"
    norm_text = re.sub(r"IS_MISSING\((\w+)\)", is_missing_repl, norm_text, flags=re.IGNORECASE)
    
    # Normalize Python syntax (AND -> and, OR -> or, NOT -> not)
    # Ensure word boundaries for boolean operators
    tokens = []
    for tok in re.split(r"(\s+|[()><=!]+)", norm_text):
        if tok.upper() == "AND":
            tokens.append("and")
        elif tok.upper() == "OR":
            tokens.append("or")
        elif tok.upper() == "NOT":
            tokens.append("not")
        elif tok == "=":
            tokens.append("==")
        else:
            tokens.append(tok)
    py_expr = "".join(tokens)
    
    try:
        parsed_py = ast.parse(py_expr, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"Failed to parse DSL expression '{text}' (normalized: '{py_expr}'): {e}")

    return _py_ast_to_dsl_ast(parsed_py.body)


def _py_ast_to_dsl_ast(node: ast.AST) -> ASTNode:
    if isinstance(node, ast.BoolOp):
        op = "and" if isinstance(node.op, ast.And) else "or"
        res = _py_ast_to_dsl_ast(node.values[0])
        for val in node.values[1:]:
            res = BinaryOp(op, res, _py_ast_to_dsl_ast(val))
        return res
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return UnaryOp("not", _py_ast_to_dsl_ast(node.operand))
    elif isinstance(node, ast.Compare):
        if len(node.ops) != 1 or len(node.comparators) != 1:
            raise ValueError("Chained comparisons not supported in single compare node")
        left = _py_ast_to_dsl_ast(node.left)
        right = _py_ast_to_dsl_ast(node.comparators[0])
        op_map = {
            ast.Eq: "==",
            ast.NotEq: "!=",
            ast.Lt: "<",
            ast.LtE: "<=",
            ast.Gt: ">",
            ast.GtE: ">=",
        }
        op_type = type(node.ops[0])
        if op_type not in op_map:
            raise ValueError(f"Unsupported comparison operator: {op_type}")
        return BinaryOp(op_map[op_type], left, right)
    elif isinstance(node, ast.Name):
        if node.id.startswith("__is_missing__") and node.id.endswith("__"):
            field = node.id[len("__is_missing__") : -2]
            return IsMissing(field)
        if node.id == "True":
            return Const(True)
        if node.id == "False":
            return Const(False)
        return Var(node.id)
    elif isinstance(node, ast.Constant):
        return Const(node.value)
    else:
        raise ValueError(f"Unsupported AST node in expression: {type(node)}")


def eval_dsl(node: ASTNode, ticket: Dict[str, Any]) -> Any:
    """Evaluates DSL AST on a concrete ticket dictionary."""
    if isinstance(node, Const):
        return node.value
    elif isinstance(node, Var):
        return ticket.get(node.name)
    elif isinstance(node, IsMissing):
        val = ticket.get(node.field)
        return val is None or ticket.get(f"{node.field}_missing", False) is True
    elif isinstance(node, UnaryOp):
        if node.op == "not":
            return not eval_dsl(node.operand, ticket)
        raise ValueError(f"Unknown unary op {node.op}")
    elif isinstance(node, BinaryOp):
        if node.op == "and":
            return bool(eval_dsl(node.left, ticket) and eval_dsl(node.right, ticket))
        elif node.op == "or":
            return bool(eval_dsl(node.left, ticket) or eval_dsl(node.right, ticket))
        left_val = eval_dsl(node.left, ticket)
        right_val = eval_dsl(node.right, ticket)
        if left_val is None or right_val is None:
            return False
        if node.op == "==":
            return left_val == right_val
        elif node.op == "!=":
            return left_val != right_val
        elif node.op == "<":
            return left_val < right_val
        elif node.op == "<=":
            return left_val <= right_val
        elif node.op == ">":
            return left_val > right_val
        elif node.op == ">=":
            return left_val >= right_val
        raise ValueError(f"Unknown binary op {node.op}")
    raise ValueError(f"Unknown node {type(node)}")


def dsl_to_z3(node: ASTNode, z3_vars: Dict[str, Any]) -> Any:
    """Translates a DSL AST node to a Z3 expression."""
    if isinstance(node, Const):
        if isinstance(node.value, bool):
            return z3.BoolVal(node.value)
        elif isinstance(node.value, (int, float)):
            return z3.IntVal(int(node.value))
        elif isinstance(node.value, str):
            return z3.StringVal(node.value)
        return node.value
    elif isinstance(node, Var):
        if node.name not in z3_vars:
            raise KeyError(f"Variable '{node.name}' not registered in symbolic domain")
        return z3_vars[node.name]
    elif isinstance(node, IsMissing):
        missing_var_name = f"{node.field}_missing"
        if missing_var_name in z3_vars:
            return z3_vars[missing_var_name]
        # fallback to category_missing if field is category
        if node.field == "category" and "category_missing" in z3_vars:
            return z3_vars["category_missing"]
        raise KeyError(f"Missing indicator for '{node.field}' not found in symbolic variables")
    elif isinstance(node, UnaryOp):
        if node.op == "not":
            return z3.Not(dsl_to_z3(node.operand, z3_vars))
        raise ValueError(f"Unsupported unary op {node.op}")
    elif isinstance(node, BinaryOp):
        if node.op == "and":
            return z3.And(dsl_to_z3(node.left, z3_vars), dsl_to_z3(node.right, z3_vars))
        elif node.op == "or":
            return z3.Or(dsl_to_z3(node.left, z3_vars), dsl_to_z3(node.right, z3_vars))
        
        # Handle comparisons with None
        if isinstance(node.left, Var) and isinstance(node.right, Const) and node.right.value is None:
            missing_expr = z3_vars.get(f"{node.left.name}_missing", z3_vars.get("category_missing"))
            return missing_expr if node.op in ("==", "is") else z3.Not(missing_expr)
        if isinstance(node.right, Var) and isinstance(node.left, Const) and node.left.value is None:
            missing_expr = z3_vars.get(f"{node.right.name}_missing", z3_vars.get("category_missing"))
            return missing_expr if node.op in ("==", "is") else z3.Not(missing_expr)

        left_z = dsl_to_z3(node.left, z3_vars)
        right_z = dsl_to_z3(node.right, z3_vars)
        if node.op == "==":
            return left_z == right_z
        elif node.op == "!=":
            return left_z != right_z
        elif node.op == "<":
            return left_z < right_z
        elif node.op == "<=":
            return left_z <= right_z
        elif node.op == ">":
            return left_z > right_z
        elif node.op == ">=":
            return left_z >= right_z
        raise ValueError(f"Unsupported binary op {node.op}")
    raise ValueError(f"Unsupported AST node type: {type(node)}")


class RestrictedPythonParser:
    """
    Safely inspects Python source without executing untrusted code.
    Extracts ordered decision rules: list of (condition_ast, return_queue).
    Flags any disallowed AST constructs as unsupported.
    """
    DISALLOWED_NODES = (
        ast.Import,
        ast.ImportFrom,
        ast.While,
        ast.For,
        ast.Try,
        ast.With,
        ast.AsyncFunctionDef,
        ast.ClassDef,
        ast.Delete,
        ast.Global,
        ast.Nonlocal,
        ast.Lambda,
    )

    def __init__(self, code: str, target_func: str = "route_ticket"):
        self.code = code
        self.target_func = target_func
        self.unsupported_constructs: List[str] = []

    def parse(self) -> Tuple[List[Tuple[Optional[ASTNode], str]], List[str]]:
        try:
            tree = ast.parse(self.code)
        except SyntaxError as e:
            return [], [f"SyntaxError: {e}"]

        # Check for disallowed constructs anywhere in file
        for node in ast.walk(tree):
            if isinstance(node, self.DISALLOWED_NODES):
                self.unsupported_constructs.append(type(node).__name__)
            # Reject arbitrary calls unless it's a known unit converter or dict get
            elif isinstance(node, ast.Call):
                func_name = None
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                
                if func_name not in ("minutes", "seconds", "hours", "len", "get"):
                    self.unsupported_constructs.append(f"DisallowedCall({func_name})")

        if self.unsupported_constructs:
            return [], list(set(self.unsupported_constructs))

        # Find target function
        func_def = None
        for item in tree.body:
            if isinstance(item, ast.FunctionDef) and item.name == self.target_func:
                func_def = item
                break

        if not func_def:
            return [], [f"Function '{self.target_func}' not found in snippet"]

        rules: List[Tuple[Optional[ASTNode], str]] = []
        errs: List[str] = []
        self._extract_if_branches(func_def.body, rules, errs)
        return rules, errs

    def _extract_if_branches(
        self, body: List[ast.stmt], rules: List[Tuple[Optional[ASTNode], str]], errs: List[str]
    ):
        for stmt in body:
            if isinstance(stmt, ast.If):
                # Convert if condition to DSL AST
                cond_ast = self._convert_test(stmt.test, errs)
                # Look for return inside body
                ret_queue = self._find_return(stmt.body)
                if ret_queue and cond_ast:
                    rules.append((cond_ast, ret_queue))
                
                # Check else/elif branch
                if stmt.orelse:
                    self._extract_if_branches(stmt.orelse, rules, errs)
            elif isinstance(stmt, ast.Return):
                val = self._eval_literal_return(stmt.value)
                if val:
                    rules.append((None, val))

    def _convert_test(self, test_node: ast.AST, errs: List[str]) -> Optional[ASTNode]:
        try:
            # Handle ticket.get(...) or ticket['...']
            return self._py_node_to_dsl(test_node)
        except Exception as e:
            errs.append(f"Failed to translate test condition: {e}")
            return None

    def _py_node_to_dsl(self, node: ast.AST) -> ASTNode:
        if isinstance(node, ast.Compare):
            op_type = type(node.ops[0])
            # Detect ticket.get(...) is None / == None
            is_right_none = (
                isinstance(node.comparators[0], ast.Constant) and node.comparators[0].value is None
            ) or (isinstance(node.comparators[0], ast.Name) and node.comparators[0].id == "None")
            
            if is_right_none:
                field = None
                if isinstance(node.left, ast.Call) and isinstance(node.left.func, ast.Attribute):
                    if node.left.func.attr == "get" and node.left.args and isinstance(node.left.args[0], ast.Constant):
                        field = str(node.left.args[0].value)
                elif isinstance(node.left, ast.Subscript) and isinstance(node.left.slice, ast.Constant):
                    field = str(node.left.slice.value)
                elif isinstance(node.left, ast.Name):
                    field = node.left.id

                if field:
                    if op_type in (ast.Eq, ast.Is):
                        return IsMissing(field)
                    elif op_type in (ast.NotEq, ast.IsNot):
                        return UnaryOp("not", IsMissing(field))

            left = self._py_node_to_dsl(node.left)
            right = self._py_node_to_dsl(node.comparators[0])
            op_map = {
                ast.Eq: "==",
                ast.NotEq: "!=",
                ast.Lt: "<",
                ast.LtE: "<=",
                ast.Gt: ">",
                ast.GtE: ">=",
                ast.Is: "==",
                ast.IsNot: "!=",
            }
            op_type = type(node.ops[0])
            if op_type not in op_map:
                raise ValueError(f"Unsupported comparison op {op_type}")
            return BinaryOp(op_map[op_type], left, right)
        elif isinstance(node, ast.BoolOp):
            op = "and" if isinstance(node.op, ast.And) else "or"
            res = self._py_node_to_dsl(node.values[0])
            for val in node.values[1:]:
                res = BinaryOp(op, res, self._py_node_to_dsl(val))
            return res
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return UnaryOp("not", self._py_node_to_dsl(node.operand))
        elif isinstance(node, ast.Name):
            if node.id == "None":
                return Const(None)
            if node.id in ("True", "False"):
                return Const(node.id == "True")
            return Var(node.id)
        elif isinstance(node, ast.Constant):
            return Const(node.value)
        elif isinstance(node, ast.Subscript):
            # ticket['category'] or ticket['wait_seconds']
            if isinstance(node.slice, ast.Constant):
                key = str(node.slice.value)
                if key == "category":
                    return Var("category")
                elif key in ("wait_seconds", "waiting_time", "wait_time"):
                    return Var("wait_seconds")
                elif key == "urgent":
                    return Var("urgent")
                elif key == "vip":
                    return Var("vip")
                return Var(key)
        elif isinstance(node, ast.Call):
            # ticket.get('category') or unit helper
            if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
                if node.args and isinstance(node.args[0], ast.Constant):
                    field = str(node.args[0].value)
                    return Var(field)
            elif isinstance(node.func, ast.Name) and node.func.id in ("minutes", "mins"):
                if node.args and isinstance(node.args[0], ast.Constant):
                    return Const(int(node.args[0].value) * 60)
            elif isinstance(node.func, ast.Name) and node.func.id in ("hours", "hrs"):
                if node.args and isinstance(node.args[0], ast.Constant):
                    return Const(int(node.args[0].value) * 3600)
            elif isinstance(node.func, ast.Name) and node.func.id in ("seconds", "secs"):
                if node.args and isinstance(node.args[0], ast.Constant):
                    return Const(int(node.args[0].value))
        raise ValueError(f"Cannot translate Python AST node: {ast.dump(node)}")

    def _find_return(self, stmts: List[ast.stmt]) -> Optional[str]:
        for s in stmts:
            if isinstance(s, ast.Return):
                return self._eval_literal_return(s.value)
        return None

    def _eval_literal_return(self, val_node: Optional[ast.AST]) -> Optional[str]:
        if val_node is None:
            return None
        if isinstance(val_node, ast.Constant):
            return str(val_node.value)
        return None
