# encrypt.py
# Run this script to encrypt your .env and password.txt files.
# After running, delete the plain .env and password.txt files.
#
# Usage:
#   python encrypt.py
#
# What it does:
#   .env             → .env.encrypted
#   password/password.txt → password/password.txt.encrypted

from crypto_env import (
    ENV_PLAIN,           # path to plain .env file
    ENV_ENCRYPTED,       # path to .env.encrypted file
    PASSWORD_PLAIN,      # path to plain password.txt file
    PASSWORD_ENCRYPTED,  # path to password.txt.encrypted file
    encrypt_file         # function to encrypt plain text file to encrypted file
)


def main():
    print("=" * 50)
    print("ENCRYPTION TOOL")
    print("=" * 50)

    encrypted_any = False

    # --- Encrypt .env ---
    if ENV_PLAIN.exists():
        confirm = input(f"\nEncrypt {ENV_PLAIN.name} → {ENV_ENCRYPTED.name}? (yes/no): ").strip().lower()
        if confirm == "yes":
            encrypt_file(ENV_PLAIN, ENV_ENCRYPTED)
            delete = input(f"Delete plain {ENV_PLAIN.name} now? (yes/no): ").strip().lower()
            if delete == "yes":
                ENV_PLAIN.unlink()
                print(f"Deleted: {ENV_PLAIN.name}")
            else:
                print(f"Kept plain {ENV_PLAIN.name} — remember to delete it manually!")
            encrypted_any = True
        else:
            print(f"Skipped {ENV_PLAIN.name}")
    else:
        print(f"\nNo plain {ENV_PLAIN.name} found — skipping.")

    # --- Encrypt password.txt ---
    if PASSWORD_PLAIN.exists():
        confirm = input(f"\nEncrypt {PASSWORD_PLAIN} → {PASSWORD_ENCRYPTED.name}? (yes/no): ").strip().lower()
        if confirm == "yes":
            encrypt_file(PASSWORD_PLAIN, PASSWORD_ENCRYPTED)
            delete = input(f"Delete plain {PASSWORD_PLAIN.name} now? (yes/no): ").strip().lower()
            if delete == "yes":
                PASSWORD_PLAIN.unlink()
                print(f"Deleted: {PASSWORD_PLAIN.name}")
            else:
                print(f"Kept plain {PASSWORD_PLAIN.name} — remember to delete it manually!")
            encrypted_any = True
        else:
            print(f"Skipped {PASSWORD_PLAIN.name}")
    else:
        print(f"\nNo plain {PASSWORD_PLAIN} found — skipping.")

    print("\n" + "=" * 50)
    if encrypted_any:
        print("Done! Encrypted files are ready.")
        print("Scripts will now decrypt at runtime using ENV_MASTER_KEY.")
    else:
        print("Nothing was encrypted.")
    print("=" * 50)


if __name__ == "__main__":
    main()