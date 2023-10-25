import sqlite3
import re
import getpass
from keys import encrypt, encrypt_private_key, generate_keys, read_key, fetch_decrypted_private_key
from recover_key import generate_random_mnemonic
from utils import display_menu_and_get_choice, get_user_transactions, print_header, get_current_user_public_key, find_index_from_file, remove_from_file
from database import Database
from transaction import transaction_pool, Transaction, REWARD, REWARD_VALUE
from storage import load_from_file
import hashlib

PEPPER = b"MySecretPepperValue"

class User:

    db = Database()

    def __init__(self):
        self.current_user = None

    def validate_password(self, password):
        if 8 <= len(password) <= 32:
            if re.search('[a-z]', password) is not None:
                if re.search('[A-Z]', password) is not None:
                    if re.search('[0-9]', password) is not None:
                        if re.search('[^a-zA-Z0-9]', password) is not None:
                            return True

    def validate_username(self, username):
        if 3 <= len(username) <= 32:
            if re.search('^[a-zA-Z0-9]+$', username) is not None:
                return True

    def username_exists(self, username):
        results = self.db.fetch('SELECT username FROM users WHERE username=?', (username, ))
        return results

    def hash_password(self, password):
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            PEPPER,
            iterations=100000,
            dklen=128
        )
        return key

    def verify_password(self, stored_password, password):
        new_key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            PEPPER,
            iterations=100000,
            dklen=128
        )
        return stored_password == new_key


    def register(self):
        username = input('Enter a username: ').lower()

        if self.username_exists(username):
            print_header()
            print('Username is already taken')
            return

        if not self.validate_username(username):
            print_header()
            print('Username must be between 3 and 32 characters and contain only letters and numbers')
            return

        password = getpass.getpass('Enter a password: ')

        if not self.validate_password(password):
            print_header()
            print('Password must be between 8 and 32 characters and contain at least one lowercase letter, one uppercase letter, one number, and one special character')
            return

        confirm_password = getpass.getpass('Confirm password: ')

        while password != confirm_password:
            print_header()
            print('Passwords do not match')
            return

        hashed_pw = self.hash_password(password)

        # create keys
        user_private_key, user_public_key = generate_keys()
        database_key = read_key()
        if database_key != "":
            encrypted_private_key = encrypt_private_key(database_key, user_private_key)
        else: return

        # create mnemonic phrase
        phrase = generate_random_mnemonic()
        hashed_phrase = hashlib.sha256(phrase.encode()).hexdigest()

        try:
            self.db.execute('INSERT INTO users (username, password, privatekey, publickey, phrase) VALUES (?, ?, ?, ?, ?)', (username, hashed_pw, encrypted_private_key, user_public_key, hashed_phrase))
        except sqlite3.Error as e:
            print_header()
            print(f"Database error: {e}")
            return

        # reward user
        self.current_user = username
        self.reward_user()
        print_header(username)

        print('\nRegistration successful')
        print("\n**Important: Keep Your Recovery Key Safe** \n- Write it down and keep it offline. \n- Use this phrase to recover your private key \n- Never share it. Losing it can lead to permanent loss of your funds.")
        print("\nRECOVERY KEY: " + phrase)

        options = [{"option": "1", "text": "Go to profile", "action": lambda: "profile"}]
        choice_result = display_menu_and_get_choice(options, username)

        if choice_result == "profile":
            print_header(username)
            return

    def login(self):
        username = input('Enter your username: ').lower()
        password = getpass.getpass('Enter your password: ')

        retrieved_user =self.db.fetch('SELECT password FROM users WHERE username=?', (username, ))

        if retrieved_user and self.verify_password(retrieved_user[0][0], password):
            print_header(username)
            print('Login successful')
            self.current_user = username
        else:
            print_header()
            print('Invalid username or password')


    def logout(self):
        print_header()
        print("You've been logged out")
        self.current_user = None

    def change_username(self):
        new_username = input('Enter a new username: ').lower()

        if not self.validate_username(new_username):
            print_header(self.current_user)
            print('Username must be between 3 and 32 characters and contain only letters and numbers')
            return

        if self.username_exists(new_username):
            print_header(self.current_user)
            print('Username is already taken')
            return

        try:
            self.db.execute('UPDATE users SET username=? WHERE username=?', (new_username, self.current_user))
            print_header(new_username)
            print('Username successfully changed')
            self.current_user = new_username
        except sqlite3.IntegrityError:
            print_header(self.current_user)
            print('Username is already taken')

    def change_password(self):
        new_password = getpass.getpass('Enter a new password: ')

        if not self.validate_password(new_password):
            print_header(self.current_user)
            print('Password must be between 8 and 32 characters and contain at least one lowercase letter, one uppercase letter, one number, and one special character')
            return

        retrieved_user = self.db.fetch('SELECT password FROM users WHERE username=?', (self.current_user, ))

        if self.verify_password(retrieved_user[0][0], new_password):
            print_header(self.current_user)
            print('New password cannot be the same as the old password')
            return

        confirm_password = getpass.getpass('Confirm password: ')

        if new_password != confirm_password:
            print_header(self.current_user)
            print('Passwords do not match')
            return

        hashed_pw = self.hash_password(new_password)

        try:
            self.db.execute('UPDATE users SET password=? WHERE username=?', (hashed_pw, self.current_user))
            print_header(self.current_user)
            print('Password successfully changed')
        except sqlite3.Error as e:
            print_header(self.current_user)
            print(f"Database error: {e}")

    def reward_user(self):
        decrypted_private_key = fetch_decrypted_private_key(self.current_user)
        public_key = get_current_user_public_key(self.current_user)
        reward_transaction = Transaction(type=REWARD)

        # Since it's a reward, there are no inputs.
        reward_transaction.add_output(public_key, REWARD_VALUE)
        reward_transaction.sign(decrypted_private_key)

        transaction_pool.add_transaction(reward_transaction)

    def view_balance(self):
        transactions = load_from_file("transactions.dat")
        public_key = get_current_user_public_key(self.current_user)
        user_balance = self.calculate_balance(public_key, transactions)
        print_header(self.current_user)
        print(f"Balance for {self.current_user}: {user_balance} coins.")

    def calculate_balance(self, user_public_key, transactions):
        balance = 0
        for tx in transactions:
            if tx.output:
                output_addr, tx_amount = tx.output
                if output_addr == user_public_key:
                    balance += tx_amount
            if tx.input:
                input_addr, tx_amount = tx.input
                if input_addr == user_public_key:
                    balance -= tx_amount
                    balance -= tx.fee 
        return balance

    def view_transactions(self):
        transactions = load_from_file("transactions.dat")

        if not transactions:
            print_header(self.current_user)
            print("No transactions found.")
        else:
            print_header(self.current_user)
            print("All Transactions: \n")
            for tx in transactions:
                print(tx)

    def transfer_coins(self):
        amount_to_transfer = input("Enter number of coins to send: ")
        receiver_username = input("Enter the receiver's username: ").replace(" ", "").lower()
        transaction_fee = input("Enter transaction fee: ")

        options = [{"option": "1", "text": "Confirm transaction", "action": lambda: "confirm"},
                {"option": "2", "text": "Cancel", "action": lambda: "back"}]
        choice_result = display_menu_and_get_choice(options)
        if choice_result == "back":
            return

        try:
            amount_to_transfer = float(amount_to_transfer)
            transaction_fee = float(transaction_fee)
        except ValueError:
            print_header(self.current_user)
            print("Invalid input")
            return

        # check if username is current user
        if receiver_username == self.current_user:
            print_header(self.current_user)
            print("Cannot send coins to yourself")
            return

        if amount_to_transfer <= 0 or transaction_fee <= 0:
            print_header(self.current_user)
            print('Invalid amount')
            return

        # check if enough balance
        transactions = load_from_file("transactions.dat")
        public_key = get_current_user_public_key(self.current_user)
        balance = self.calculate_balance(public_key, transactions)
        if balance < amount_to_transfer + transaction_fee:
            print_header(self.current_user)
            print("Insufficient balance")
            return

        # check if receiver exists
        if not self.validate_username(receiver_username):
            print_header(self.current_user)
            print("Invalid username")
            return

        if not self.username_exists(receiver_username):
            print_header(self.current_user)
            print('Receiver does not exists.')
            return

        # make the transaction
        transaction = Transaction(0, transaction_fee)
        private_key = fetch_decrypted_private_key(self.current_user)
        public_key_receiver = get_current_user_public_key(receiver_username)
        transaction.add_input(public_key, amount_to_transfer)
        transaction.add_output(public_key_receiver,amount_to_transfer)

        # sign transaction
        transaction.sign(private_key)

        # check if transaction is valid
        if not transaction.is_valid():
            print_header(self.current_user)
            print("Invalid transaction")
            return

        # add to the pool
        transaction_pool.add_transaction(transaction)

        print_header(self.current_user)
        print('Transaction successful')

    def remove_transaction(self):
        # show all user transactions from the pool
        transactions = get_user_transactions("transactions.dat", self.current_user) # [number, input amount, username sender, fee]
        if transactions == []:
            print("You have no transactions")
            return
        
        print("Pending transactions: ")
        for tx in transactions:
            print(f"{str(tx[0])}. {tx[1]} to {tx[2]} with {tx[3]} transaction fee")
        print(f"{len(transactions)+1}. Back to main menu")
        
        choice = input("Enter transaction to cancel: ")
        try:
            choice = int(choice)
        except ValueError:
            print("Invalid input")
            return
        
        if choice == len(transactions)+1:
            return
        else:
            #confirm
            options = [{"option": "1", "text": "Delete transaction", "action": lambda: "confirm"},
                {"option": "2", "text": "Cancel", "action": lambda: "back"}]
            choice_result = display_menu_and_get_choice(options)
            if choice_result == "back":
                return
            
            # delete from pool
            index = find_index_from_file("transactions.dat", transactions[choice-1][1], get_current_user_public_key(self.current_user), get_current_user_public_key(transactions[choice-1][2]), transactions[choice-1][3])
            remove = remove_from_file("transactions.dat", index)
            if remove:
                print("Transaction canceled")
            else:
                print("Could not cancel transaction")
            return

    def edit_transaction(self):
        transactions = get_user_transactions("transactions.dat", self.current_user) # [number, input amount, username sender, fee]
        options = []
        if transactions == []:
            print("You have no transactions")
            return
        print("Pending transactions")
        for tx in transactions:
            print(f"{str(tx[0])}. {tx[1]} to {tx[2]} with {tx[3]} transaction fee")
        print(f"{len(transactions)+1}. Back to main menu")
        
        choice = input("Enter transaction to modify: ")
        try:
            choice = int(choice)
        except ValueError:
            print("Invalid input")
            return
        
        if choice == len(transactions)+1:
            return
        else:
            self.transaction_edit_menu(transactions, choice-1)
            return

    def transaction_edit_menu(self, transactions, tx_choice):
        options = [{"option": "1", "text": "Edit receiver's username", "action": lambda: 1},
            {"option": "2", "text": "Edit transaction fee", "action": lambda: 2},
            {"option": "3", "text": "Edit amount of coins", "action": lambda: 3},
            {"option": "4", "text": "Back to menu", "action": lambda: "back"}]
        edit_choice = display_menu_and_get_choice(options)
        if edit_choice == "back":
            return
        else:
            tx = Transaction(0, transactions[tx_choice][3])
            private_key = fetch_decrypted_private_key(self.current_user)
            public_key = get_current_user_public_key(self.current_user)
            public_key_receiver = get_current_user_public_key(transactions[tx_choice][2])
            index = find_index_from_file("transactions.dat", transactions[tx_choice][1],  public_key, public_key_receiver, transactions[tx_choice][3])
            if edit_choice == 1:
                new_username = input("Enter new username: ").replace(" ", "").lower()
                if not self.validate_username(new_username) or not self.username_exists(new_username):
                    print_header(self.current_user)
                    print("Invalid username")
                    return

                public_key_new_receiver = get_current_user_public_key(new_username)
                tx.add_input(public_key, transactions[tx_choice][1])
                tx.add_output(public_key_new_receiver, transactions[tx_choice][1])

            elif edit_choice == 2:
                new_fee = input("Enter new transaction fee: ")
                try:
                    new_fee = float(new_fee)
                except ValueError:
                    print_header(self.current_user)
                    print("Invalid input")
                    return
                if new_fee <= 0:
                    print_header(self.current_user)
                    print('Invalid amount')
                    return

                # check if enough balance
                transactions_list = load_from_file("transactions.dat")
                temp_amount = transactions[tx_choice][1]
                del transactions_list[index]
                balance = self.calculate_balance(public_key, transactions_list)
                if balance < new_fee + temp_amount:
                    print_header(self.current_user)
                    print("Insufficient balance")
                    return
                tx.fee = new_fee
                tx.add_input(public_key, transactions[tx_choice][1])
                tx.add_output(public_key_receiver,transactions[tx_choice][1])

            elif edit_choice == 3:
                new_amount = input("Enter new amount: ")
                try:
                    new_amount = float(new_amount)
                except ValueError:
                    print_header(self.current_user)
                    print("Invalid input")
                    return
                if new_amount <= 0:
                    print_header(self.current_user)
                    print('Invalid amount')
                    return

                # check if enough balance
                transactions_list = load_from_file("transactions.dat")
                temp_fee = transactions[tx_choice][3]
                del transactions_list[index]
                balance = self.calculate_balance(public_key, transactions_list)
                if balance < new_amount + temp_fee:
                    print_header(self.current_user)
                    print("Insufficient balance")
                    return

                tx.add_input(public_key, new_amount)
                tx.add_output(public_key_receiver, new_amount)

            tx.sign(private_key)
            if not tx.is_valid():
                print_header(self.current_user)
                print("Invalid transaction")
                return
            
            #confirm
            options = [{"option": "1", "text": "Save changes", "action": lambda: "confirm"},
                        {"option": "2", "text": "Cancel", "action": lambda: "back"}]
            choice_result = display_menu_and_get_choice(options)
            if choice_result == "back":
                return
            
            #remove and add new transaction
            remove = remove_from_file("transactions.dat", index)
            if remove:
                transaction_pool.add_transaction(tx)
                print_header(self.current_user)
                print('Transaction modified successfully')
                return
            else:
                print_header(self.current_user)
                print('Could not modify transaction')
                return