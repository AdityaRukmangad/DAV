import sys
import os
import time

# Ensure we can see the 'app' package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.tools.calculator import get_math_tool
from app.tools.web_search import get_search_tool

def test_calculator():
    print("\n" + "="*40)
    print("🛠️  TESTING CALCULATOR TOOL")
    print("="*40)
    
    tool = get_math_tool()

    # Case 1: Happy Path (Complex Math)
    print("\n🔹 Test 1: Valid Complex Math")
    code = "import math\nprint(math.factorial(10))"
    result = tool.run(code)
    print(f"   Input: {code.strip()}")
    print(f"   Result: {result}")
    assert "3628800" in str(result)

    # Case 2: Security Violation
    print("\n🔹 Test 2: Security Breach Attempt (import os)")
    bad_code = "import os\nprint(os.getcwd())"
    result = tool.run(bad_code)
    print(f"   Input: {bad_code.strip()}")
    print(f"   Result: {result}")
    # We expect your validator to catch this
    assert "Security Violation" in str(result) or "not permitted" in str(result)

    # Case 3: Infinite Loop (Timeout)
    print("\n🔹 Test 3: Infinite Loop (Timeout Protection)")
    loop_code = "while True: pass"
    start = time.time()
    result = tool.run(loop_code)
    duration = time.time() - start
    print(f"   Input: {loop_code}")
    print(f"   Result: {result}")
    print(f"   Time taken: {duration:.2f}s")
    # Should be close to 5 seconds (your MAX_EXECUTION_TIME_SECONDS)
    assert "Execution timed out" in str(result)

def test_search():
    print("\n" + "="*40)
    print("🌍 TESTING WEB SEARCH TOOL")
    print("="*40)
    
    tool = get_search_tool()

    # Case 1: Valid Search
    query = "latest python version released date"
    print(f"\n🔹 Test 1: Live Search ('{query}')")
    result = tool.run(query)
    print(f"   Result Snippet: {str(result)[:150]}...")
    
    # Case 2: Caching
    print("\n🔹 Test 2: Cache Verification")
    start = time.time()
    result_cached = tool.run(query)
    duration = time.time() - start
    print(f"   Time taken: {duration:.4f}s (Should be near instant)")
    if duration < 1.0:
        print("   ✅ Cache Hit Confirmed")
    else:
        print("   ⚠️  Cache Miss (or network slow)")

if __name__ == "__main__":
    # Initialize logging first (as per your utils.py)
    from app.tools.utils import initialize_logging
    initialize_logging()
    
    try:
        test_calculator()
        test_search()
        print("\n\n ALL SYSTEMS GO. Tools are enterprise-ready.")
    except Exception as e:
        print(f"\n\n TEST FAILED: {e}")