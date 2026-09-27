"""
magicpin AI Vera Challenge — Unified Runner & Verification Script.

Usage:
    python run.py --test      # Run all unit and contract tests
    python run.py --serve     # Start the FastAPI bot server on port 8080
    python run.py --submit    # Regenerate submission.jsonl
    python run.py --judge     # Run the judge simulator against the bot
"""

import sys
import argparse
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def run_tests():
    print("Running contract and integration tests...")
    subprocess.run([sys.executable, str(BASE_DIR / "test_candidate_bot.py")], check=True)

def generate_submission():
    print("Generating submission.jsonl...")
    subprocess.run([sys.executable, str(BASE_DIR / "generate_submission.py")], check=True)

def run_server():
    print("Starting candidate bot FastAPI server on http://0.0.0.0:8080...")
    import uvicorn
    uvicorn.run("bot:app", host="0.0.0.0", port=8080, reload=False)

def run_judge():
    print("Running judge simulator in mock evaluation mode...")
    import os
    env = os.environ.copy()
    env["BOT_URL"] = "http://127.0.0.1:8080"
    env["LLM_PROVIDER"] = "mock"
    env["TEST_SCENARIO"] = "all"
    subprocess.run([sys.executable, str(BASE_DIR / "judge_simulator.py")], env=env, check=True)

def main():
    parser = argparse.ArgumentParser(description="magicpin Vera Challenge Runner")
    parser.add_argument("--test", action="store_true", help="Run test suite")
    parser.add_argument("--submit", action="store_true", help="Regenerate submission.jsonl")
    parser.add_argument("--serve", action="store_true", help="Launch FastAPI server")
    parser.add_argument("--judge", action="store_true", help="Run judge simulator")

    if len(sys.argv) == 1:
        # Default: test + generate submission
        run_tests()
        generate_submission()
        print("\nAll checks passed! Use --serve to start the HTTP bot server.")
        return

    args = parser.parse_args()
    if args.test:
        run_tests()
    if args.submit:
        generate_submission()
    if args.serve:
        run_server()
    if args.judge:
        run_judge()

if __name__ == "__main__":
    main()
