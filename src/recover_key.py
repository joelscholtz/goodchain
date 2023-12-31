import hashlib
import os
import re
import sqlite3
from database import Database
from keys import decrypt_private_key, read_key
from utils import print_header

def generate_random_mnemonic():
    # Make a word list
    word_list = ["lavender", "ocean", "coffee", "roses", "sandalwood", "coconut", "vanilla", "chocolate", "rain", "cinnamon"]

    # Generate random bytes
    random_bytes = os.urandom(32)

    # Calculate the checksum
    checksum_length = len(random_bytes) // 4
    checksum = hashlib.sha256(random_bytes).digest()[:checksum_length]

    # Combine the random data and checksum
    combined_data = random_bytes + checksum

    # Split the combined data into 11-bit chunks
    bits = [int.from_bytes(combined_data[i:i+11], 'big') for i in range(0, len(combined_data), 11)]

    # Create the mnemonic phrase
    mnemonic_words = []
    for bit in bits:
        word_index = bit % len(word_list)
        mnemonic_words.append(word_list[word_index])

    # Join the words
    mnemonic = " ".join(mnemonic_words)

    return mnemonic


def recover_private_key():
    print_header()
    db = Database()
    username = input('Enter username: ').lower().strip()
    user_key = input("Enter recovery key: ")

    # if username exists
    if 3 <= len(username) <= 32 and re.search('^[a-zA-Z0-9]+$', username) is not None:
        try:
            retrieve_username = db.fetch('SELECT username FROM users WHERE username=?', (username, ))
        except sqlite3.Error as e:
            print_header()
            print(f"Database error: {e}")

        if retrieve_username and retrieve_username[0][0] == username:
            # if phrase matches
            if is_valid_phrase(user_key):
                try:
                    get_hased_phrase = db.fetch('SELECT phrase FROM users WHERE username=?', (username, ))
                except sqlite3.Error as e:
                    print_header()
                    print(f"Database error: {e}")
                if get_hased_phrase and hashlib.sha256(user_key.encode()).hexdigest() == get_hased_phrase[0][0]:
                    try:
                        private_key = db.fetch('SELECT privatekey FROM users WHERE username=?', (username, ))
                    except sqlite3.Error as e:
                        print_header()
                        print_header()
                        print(f"Database error: {e}")
                    db_key= read_key()
                    if db_key != "":
                        decrypted_private_key = decrypt_private_key(db_key, private_key[0][0])
                        if isinstance(decrypted_private_key, bytes):
                            decrypted_private_key = decrypted_private_key.decode('utf-8')
                        cleaned_private_key = decrypted_private_key.replace("-----BEGIN PRIVATE KEY-----", "").replace("-----END PRIVATE KEY-----", "").strip()
                        print_header()
                        print(f"\nYour private key is: \n{cleaned_private_key}")
                    else:
                        print_header()
                        print("Private key not found")
                    return        
    print_header()    
    print('Invalid username or key')
            


def is_valid_phrase(input_text):
    if re.match(r'^[a-zA-Z\s]+$', input_text):
        return True
    else:
        return False


