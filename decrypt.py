# decrypt.py
# Run this script to decrypt .env.encrypted and/or password.txt.encrypted
# back to plain text files for manual editing.
#
# After editing, run encrypt.py to re-encrypt and delete the plain files.
#
# Usage:
#   python decrypt.py
from crypto_env import (
    ENV_PLAIN,           # path to plain .env file
    ENV_ENCRYPTED,       # path to .env.encrypted file
    PASSWORD_PLAIN,      # path to plain password.txt file
    PASSWORD_ENCRYPTED,  # path to password.txt.encrypted file
    decrypt_file         # function to decrypt encrypted file to plain text
)


def main():
    print("=" * 50)
    print("DECRYPTION TOOL")
    print("=" * 50)
    print("WARNING: This creates plain text files with credentials.")
    print("Remember to run encrypt.py and delete plain files when done.\n")

    confirm = input("Are you sure you want to decrypt? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Cancelled.")
        return

    decrypted_any = False

    # --- Decrypt .env ---
    if ENV_ENCRYPTED.exists():
        confirm2 = input(f"\nDecrypt {ENV_ENCRYPTED.name} → {ENV_PLAIN.name}? (yes/no): ").strip().lower()
        if confirm2 == "yes":
            if ENV_PLAIN.exists():
                overwrite = input(f"Plain {ENV_PLAIN.name} already exists. Overwrite? (yes/no): ").strip().lower()
                if overwrite != "yes":
                    print(f"Skipped {ENV_ENCRYPTED.name}")
                else:
                    decrypt_file(ENV_ENCRYPTED, ENV_PLAIN)
                    decrypted_any = True
            else:
                decrypt_file(ENV_ENCRYPTED, ENV_PLAIN)
                decrypted_any = True
        else:
            print(f"Skipped {ENV_ENCRYPTED.name}")
    else:
        print(f"\nNo {ENV_ENCRYPTED.name} found — skipping.")

    # --- Decrypt password.txt ---
    if PASSWORD_ENCRYPTED.exists():
        confirm3 = input(f"\nDecrypt {PASSWORD_ENCRYPTED.name} → {PASSWORD_PLAIN.name}? (yes/no): ").strip().lower()
        if confirm3 == "yes":
            if PASSWORD_PLAIN.exists():
                overwrite = input(f"Plain {PASSWORD_PLAIN.name} already exists. Overwrite? (yes/no): ").strip().lower()
                if overwrite != "yes":
                    print(f"Skipped {PASSWORD_ENCRYPTED.name}")
                else:
                    decrypt_file(PASSWORD_ENCRYPTED, PASSWORD_PLAIN)
                    decrypted_any = True
            else:
                decrypt_file(PASSWORD_ENCRYPTED, PASSWORD_PLAIN)
                decrypted_any = True
        else:
            print(f"Skipped {PASSWORD_ENCRYPTED.name}")
    else:
        print(f"\nNo {PASSWORD_ENCRYPTED.name} found — skipping.")

    print("\n" + "=" * 50)
    if decrypted_any:
        print("Done! Plain files are ready for editing.")
        print("REMEMBER: Run encrypt.py and delete plain files when done!")
    else:
        print("Nothing was decrypted.")
    print("=" * 50)


if __name__ == "__main__":
    main()