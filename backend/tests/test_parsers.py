from backend.fastapi_app.services.parsers import extract_symbols, extract_dependencies

def test_js_symbols():
    code = """
    function calculateFare(distance) { return distance * 10; }
    const x = () => { return 1; };
    class FareCalculator {
        calculate() { return 100; }
    }
    """
    symbols = extract_symbols(code, "javascript")
    assert "calculateFare" in symbols
    assert symbols["calculateFare"]["type"] == "function"
    assert "FareCalculator" in symbols
    assert symbols["FareCalculator"]["type"] == "class"
    assert "FareCalculator.calculate" in symbols
    assert symbols["FareCalculator.calculate"]["type"] == "method"

def test_ts_symbols():
    code = """
    interface User { id: string; }
    type Role = "admin" | "user";
    enum Status { ACTIVE, INACTIVE }
    class Auth { login() {} }
    """
    symbols = extract_symbols(code, "typescript")
    assert "User" in symbols
    assert symbols["User"]["type"] == "interface"
    assert "Role" in symbols
    assert symbols["Role"]["type"] == "type"
    assert "Status" in symbols
    assert symbols["Status"]["type"] == "enum"
    assert "Auth" in symbols
    assert symbols["Auth"]["type"] == "class"
    assert "Auth.login" in symbols
    assert symbols["Auth.login"]["type"] == "method"

def test_jsx_symbols():
    code = """
    export function Dashboard() {
        return <div>hello</div>
    }
    export default function App() {
        return <Dashboard />
    }
    """
    symbols = extract_symbols(code, "jsx")
    assert "Dashboard" in symbols
    assert symbols["Dashboard"]["type"] == "function"
    assert "App" in symbols
    assert symbols["App"]["type"] == "function"

def test_imports():
    code = """
    import { foo } from "./utils";
    import * as bar from "../core/bar";
    const x = require("./legacy");
    """
    deps = extract_dependencies(code, "javascript")
    targets = [d["target"] for d in deps]
    assert "./utils" in targets
    assert "../core/bar" in targets
    assert "./legacy" in targets
