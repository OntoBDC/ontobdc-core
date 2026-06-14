import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="Manage ontobdc extras")
    parser.add_argument("--enable", type=str, help="Enable an extra module")
    args = parser.parse_args()

    if args.enable:
        extra_name = args.enable
        # In a real scenario, this might modify pyproject.toml and run pip install
        # For now, just print the mock success message
        print(f"Extra '{extra_name}' enabled successfully.")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
