import unittest
import os
import sys
import io

def run_failed_only():
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir='.', pattern='test_*.py')
    
    # Use a buffer to capture output
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print("All tests passed successfully (100% pass rate).")
        print(f"Total tests run: {result.testsRun}")
        return

    print("FAILED TEST LOGS:")
    print("=" * 50)
    
    if result.failures:
        print(f"\nFAILURES ({len(result.failures)}):")
        for test, err in result.failures:
            print("-" * 30)
            print(f"Test: {test}")
            print(err)
            
    if result.errors:
        print(f"\nERRORS ({len(result.errors)}):")
        for test, err in result.errors:
            print("-" * 30)
            print(f"Test: {test}")
            print(err)
    
    print("=" * 50)
    print(f"Summary: {result.testsRun} run, {len(result.failures)} failed, {len(result.errors)} errors.")

if __name__ == "__main__":
    run_failed_only()
