"""
Module: app/tools/calculator.py
Purpose: Safe Python code execution using AST validation.
Fixed: Solves 'ImportError: __import__ not found' by checking imports BEFORE execution.
"""

import sys
import ast
import traceback
import multiprocessing as mp
from io import StringIO
from typing import Type
from contextlib import redirect_stdout, redirect_stderr

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.tools.utils import get_logger

logger = get_logger("PythonExecutor")

TIMEOUT_SECONDS = 10
MAX_OUTPUT_LENGTH = 5000

# Whitelisted modules for AST check
ALLOWED_MODULES = {
    'math', 'random', 'statistics', 'collections', 'itertools', 'functools', 'datetime', 're'
}

class PythonInput(BaseModel):
    code: str = Field(description="Python code to execute")

def validate_code_security(code: str) -> bool:
    """
    Parses code into an Abstract Syntax Tree (AST) to check for dangerous imports
    BEFORE executing it. much safer and more stable than overriding __import__.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False # Let the exec fail naturally later for better error msg

    for node in ast.walk(tree):
        # Check 'import x'
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split('.')[0] not in ALLOWED_MODULES:
                    raise ImportError(f"Security: Import of '{alias.name}' is not allowed.")
        
        # Check 'from x import y'
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split('.')[0] not in ALLOWED_MODULES:
                raise ImportError(f"Security: From-Import '{node.module}' is not allowed.")
                
    return True

def execute_code_safely(code: str, queue: mp.Queue):
    try:
        # 1. Security Check
        validate_code_security(code)
        
        # 2. Prepare Sandbox
        # We allow standard builtins but remove IO/System stuff
        safe_builtins = {k: v for k, v in __builtins__.items() 
                        if k not in ('open', 'input', 'eval', 'exec', 'exit', 'quit', 'help')}
        
        safe_globals = {'__builtins__': safe_builtins}
        
        # 3. Capture Output
        stdout_capture = StringIO()
        stderr_capture = StringIO()
        
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            exec(code, safe_globals)
        
        # 4. Handle Results
        output = stdout_capture.getvalue()
        errors = stderr_capture.getvalue()
        
        if errors:
            queue.put(f"Error: {errors}")
        elif not output.strip():
            queue.put("Error: Code ran but produced no output. Did you forget print()?")
        else:
            queue.put(output.strip()[:MAX_OUTPUT_LENGTH])
            
    except Exception as e:
        queue.put(f"Error: {type(e).__name__}: {str(e)}")

class SafePythonREPL(BaseTool):
    name: str = "python_interpreter_enterprise"
    description: str = "Executes Python code to verify answers. Use print() to output results."
    args_schema: Type[BaseModel] = PythonInput
    
    def _run(self, code: str) -> str:
        code = code.replace("```python", "").replace("```", "").strip()
        if not code: return "Error: Empty code"
        
        try:
            ctx = mp.get_context('spawn')
            queue = ctx.Queue()
            process = ctx.Process(target=execute_code_safely, args=(code, queue))
            process.start()
            process.join(timeout=TIMEOUT_SECONDS)
            
            if process.is_alive():
                process.terminate()
                process.join(0.5)
                if process.is_alive(): process.kill()
                return "Error: Execution timed out."
            
            if queue.empty():
                return f"Error: Process crashed (Exit {process.exitcode})"
                
            return queue.get()
            
        except Exception as e:
            return f"Error: {e}"

def get_math_tool() -> SafePythonREPL:
    return SafePythonREPL()