import os
import sys
import subprocess
import argparse

def main():
    parser = argparse.ArgumentParser(description="Visionary Navigator Build Script")
    parser.add_argument("--os", choices=["macos", "windows"], default="macos", help="Target OS")
    args = parser.parse_args()

    spec_file = f"build_{args.os}.spec"
    if not os.path.exists(spec_file):
        print(f"Error: Spec file {spec_file} not found.")
        sys.exit(1)

    print(f"Building for {args.os} using {spec_file}...")
    
    cmd = [sys.executable, "-m", "PyInstaller", spec_file, "--clean", "--noconfirm"]
    result = subprocess.run(cmd)

    if result.returncode == 0:
        print(f"\n✅ Build successful! Check the 'dist' folder.")
    else:
        print(f"\n❌ Build failed with exit code: {result.returncode}")
        sys.exit(result.returncode)

if __name__ == "__main__":
    main()
