import ast
import tree_sitter_javascript as ts_javascript
import tree_sitter_typescript as ts_typescript
from tree_sitter import Language, Parser

JS_LANGUAGE = Language(ts_javascript.language())
TS_LANGUAGE = Language(ts_typescript.language_typescript())
TSX_LANGUAGE = Language(ts_typescript.language_tsx())

js_parser = Parser(JS_LANGUAGE)
ts_parser = Parser(TS_LANGUAGE)
tsx_parser = Parser(TSX_LANGUAGE)

def get_parser(language):
    if language == "javascript":
        return js_parser
    elif language == "typescript":
        return ts_parser
    elif language in ("jsx", "tsx"):
        # Use tsx parser for both jsx and tsx
        return tsx_parser
    return None

def extract_symbols_python(code: str):
    symbols = {}
    try:
        tree = ast.parse(code)
    except Exception:
        return symbols

    def traverse(node, prefix=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}{child.name}"
                symbols[name] = {
                    "type": "method" if prefix else "function",
                    "start_line": child.lineno,
                    "end_line": getattr(child, "end_lineno", child.lineno),
                    "body_dump": ast.dump(child)
                }
            elif isinstance(child, ast.ClassDef):
                name = f"{prefix}{child.name}"
                symbols[name] = {
                    "type": "class",
                    "start_line": child.lineno,
                    "end_line": getattr(child, "end_lineno", child.lineno),
                    "body_dump": ast.dump(child)
                }
                traverse(child, prefix=f"{name}.")
                
    try:
        traverse(tree)
    except Exception:
        pass
    return symbols

def get_node_text(node, code_bytes):
    return code_bytes[node.start_byte:node.end_byte]

def extract_symbols_treesitter(code: str, language: str):
    parser = get_parser(language)
    symbols = {}
    if not parser:
        return symbols

    if isinstance(code, str):
        code_bytes = code.encode("utf-8")
    else:
        code_bytes = code

    try:
        tree = parser.parse(code_bytes)
    except Exception:
        return symbols

    def traverse(node, prefix=""):
        node_type = node.type
        sym_type = None
        name_str = None

        if node_type in ("function_declaration", "generator_function_declaration"):
            sym_type = "function"
            for child in node.children:
                if child.type == "identifier":
                    name_str = get_node_text(child, code_bytes).decode("utf-8", errors="ignore")
                    break
        elif node_type == "class_declaration":
            sym_type = "class"
            for child in node.children:
                if child.type in ("identifier", "type_identifier"):
                    name_str = get_node_text(child, code_bytes).decode("utf-8", errors="ignore")
                    break
        elif node_type == "method_definition":
            sym_type = "method"
            for child in node.children:
                if child.type == "property_identifier":
                    name_str = get_node_text(child, code_bytes).decode("utf-8", errors="ignore")
                    break
        elif node_type == "interface_declaration":
            sym_type = "interface"
            for child in node.children:
                if child.type == "type_identifier":
                    name_str = get_node_text(child, code_bytes).decode("utf-8", errors="ignore")
                    break
        elif node_type == "type_alias_declaration":
            sym_type = "type"
            for child in node.children:
                if child.type == "type_identifier":
                    name_str = get_node_text(child, code_bytes).decode("utf-8", errors="ignore")
                    break
        elif node_type == "enum_declaration":
            sym_type = "enum"
            for child in node.children:
                if child.type == "identifier":
                    name_str = get_node_text(child, code_bytes).decode("utf-8", errors="ignore")
                    break
        elif node_type == "variable_declarator":
            # check if it's an arrow function or function expression
            has_func_value = False
            for child in node.children:
                if child.type in ("arrow_function", "function", "function_expression"):
                    has_func_value = True
                    break
            if has_func_value:
                sym_type = "function"
                for child in node.children:
                    if child.type == "identifier":
                        name_str = get_node_text(child, code_bytes).decode("utf-8", errors="ignore")
                        break

        # export defaults
        if node_type == "export_statement":
            for child in node.children:
                if child.type in ("function_declaration", "class_declaration"):
                    # Process the exported child directly
                    traverse(child, prefix)

        if sym_type and name_str:
            full_name = f"{prefix}{name_str}"
            # method belongs to class prefix
            symbols[full_name] = {
                "type": sym_type,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "body_dump": get_node_text(node, code_bytes).decode("utf-8", errors="ignore")
            }
            if sym_type == "class":
                # traverse children of class with prefix
                for child in node.children:
                    if child.type == "class_body":
                        for method_node in child.children:
                            traverse(method_node, prefix=f"{full_name}.")
        else:
            # Continue traversing
            for child in node.children:
                traverse(child, prefix)

    try:
        traverse(tree.root_node)
    except Exception:
        pass
        
    return symbols

def extract_symbols(code: str, language: str):
    if language == "python":
        return extract_symbols_python(code)
    else:
        return extract_symbols_treesitter(code, language)

def extract_dependencies(code: str, language: str):
    deps = []
    if language == "python":
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        deps.append({"type": "import", "target": alias.name})
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        deps.append({"type": "import_from", "target": f"{module}.{alias.name}"})
        except Exception:
            pass
    else:
        parser = get_parser(language)
        if parser:
            if isinstance(code, str):
                code_bytes = code.encode("utf-8")
            else:
                code_bytes = code
                
            try:
                tree = parser.parse(code_bytes)
                def traverse(node):
                    if node.type == "import_statement":
                        for child in node.children:
                            if child.type == "string":
                                target = get_node_text(child, code_bytes).decode("utf-8", errors="ignore").strip("\"'")
                                deps.append({"type": "import", "target": target})
                    elif node.type == "call_expression":
                        is_require = False
                        for child in node.children:
                            if child.type == "identifier" and get_node_text(child, code_bytes) == b"require":
                                is_require = True
                            elif is_require and child.type == "arguments":
                                for arg in child.children:
                                    if arg.type == "string":
                                        target = get_node_text(arg, code_bytes).decode("utf-8", errors="ignore").strip("\"'")
                                        deps.append({"type": "import", "target": target})
                    for child in node.children:
                        traverse(child)
                traverse(tree.root_node)
            except Exception:
                pass
    return deps
