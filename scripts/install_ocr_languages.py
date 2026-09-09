"""Install pinned Tesseract fast language data after verifying SHA-256 digests."""

import argparse
import hashlib
import urllib.request
from pathlib import Path

REVISION = "87416418657359cb625c412a48b6e1d6d41c29bd"
CHECKSUMS = {
    "eng": "7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2",
    "chi_sim": "a5fcb6f0db1e1d6d8522f39db4e848f05984669172e584e8d76b6b3141e1f730",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument(
        "--languages", nargs="+", choices=sorted(CHECKSUMS), default=["eng", "chi_sim"]
    )
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    for language in args.languages:
        output = args.directory / f"{language}.traineddata"
        if output.exists():
            if hashlib.sha256(output.read_bytes()).hexdigest() != CHECKSUMS[language]:
                parser.error(
                    f"{output} already exists with different contents; choose an empty directory."
                )
            continue
        url = f"https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/{REVISION}/{language}.traineddata"
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read(16 * 1024 * 1024)
        if hashlib.sha256(data).hexdigest() != CHECKSUMS[language]:
            parser.error(f"Checksum mismatch for {language}; nothing written.")
        with output.open("xb") as stream:
            stream.write(data)
        print(f"Installed {language} in {args.directory}")


if __name__ == "__main__":
    main()
