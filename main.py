from dotenv import load_dotenv
from modelfang.cli import main

if __name__ == "__main__":
    load_dotenv()
    try:
        main()
    except Exception as e:
        print(f"An error occurred: {e}")
        import sys
        sys.exit(1)
