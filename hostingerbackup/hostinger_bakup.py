import os
import ftplib
from datetime import datetime, timedelta
import argparse
import getpass
import time
import sqlite3  # Import sqlite3


class HostingerBackup:
    def __init__(self, host, username, password, remote_dir, local_dir, port=21,
                 db_path="backup_history.db"):  # New db_path parameter
        self.host = host
        self.username = username
        self.password = password
        self.remote_dir = self._normalize_ftp_path(remote_dir)
        self.local_dir = local_dir
        self.port = port
        self.ftp = None
        self.file_count = 0
        self.dir_count = 0
        self.total_size = 0  # In bytes
        self.start_time_actual = None  # Actual start time of run_backup
        self.current_backup_timestamp = None  # Snapshot for this specific backup run

        self.db_path = db_path
        self.conn = None  # Database connection
        self.cursor = None  # Database cursor
        self.current_backup_id = None  # ID of the current backup record in DB

        self._init_db()  # Initialize the database upon class instantiation

        print(f"Normalized remote_dir: {self.remote_dir}")

    def _normalize_ftp_path(self, path):
        """Internal helper to ensure FTP paths use forward slashes and are absolute."""
        path = path.replace('\\', '/').strip('/')  # Replace backslashes, strip leading/trailing
        if not path:  # If path was just slashes or empty after stripping
            return '/'
        return '/' + path  # Ensure it's an absolute path

    def _init_db(self):
        """Initializes the SQLite database and creates the backups table if it doesn't exist."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS backups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backup_type TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    remote_directory TEXT NOT NULL,
                    local_directory TEXT NOT NULL,
                    files_backed_up INTEGER,
                    directories_backed_up INTEGER,
                    total_size_mb REAL,
                    status TEXT NOT NULL
                )
            ''')
            self.conn.commit()
            print(f"Database initialized: {self.db_path}")
        except sqlite3.Error as e:
            print(f"Database error during initialization: {e}")
            # Potentially re-raise or handle more gracefully
            raise

    def _get_last_backup_times(self):
        """
        Queries the database for the last successful full and incremental backup times
        for the current remote_directory.
        Returns a tuple: (last_full_backup_datetime, last_incremental_backup_datetime)
        """
        last_full = None
        last_incremental = None

        try:
            # Get last successful full backup
            self.cursor.execute(f'''
                SELECT MAX(start_time) FROM backups
                WHERE backup_type = 'full' AND status = 'success' AND remote_directory = ?
            ''', (self.remote_dir,))
            result = self.cursor.fetchone()[0]
            if result:
                last_full = datetime.fromisoformat(result)

            # Get last successful incremental backup
            self.cursor.execute(f'''
                SELECT MAX(start_time) FROM backups
                WHERE backup_type IN ('full', 'incremental') AND status = 'success' AND remote_directory = ?
            ''', (self.remote_dir,))
            result = self.cursor.fetchone()[0]
            if result:
                last_incremental = datetime.fromisoformat(result)

        except sqlite3.Error as e:
            print(f"Database error getting last backup times: {e}")

        return last_full, last_incremental

    def _record_backup_start(self, backup_type, local_dir):
        """Records the start of a backup operation in the database."""
        try:
            self.cursor.execute('''
                INSERT INTO backups (backup_type, start_time, remote_directory, local_directory, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (backup_type, self.current_backup_timestamp.isoformat(), self.remote_dir, local_dir, 'running'))
            self.conn.commit()
            self.current_backup_id = self.cursor.lastrowid  # Store the ID for later update
            print(f"Backup start recorded with ID: {self.current_backup_id}")
        except sqlite3.Error as e:
            print(f"Database error recording backup start: {e}")
            self.current_backup_id = None  # Indicate failure to get an ID

    def _update_backup_record(self, status):
        """Updates the backup record with final statistics and status."""
        if self.current_backup_id is None:
            print("Warning: No backup ID to update. Record might not have been inserted.")
            return

        try:
            end_time = datetime.now().isoformat()
            total_size_mb = self.total_size / (1024 * 1024)  # Convert bytes to MB

            self.cursor.execute('''
                UPDATE backups
                SET end_time = ?,
                    files_backed_up = ?,
                    directories_backed_up = ?,
                    total_size_mb = ?,
                    status = ?
                WHERE id = ?
            ''', (end_time, self.file_count, self.dir_count, total_size_mb, status, self.current_backup_id))
            self.conn.commit()
            print(f"Backup record ID {self.current_backup_id} updated with status: {status}")
        except sqlite3.Error as e:
            print(f"Database error updating backup record: {e}")

    def connect(self):
        """Establish FTP connection"""
        print(f"Connecting to {self.host}...")
        self.ftp = ftplib.FTP()
        self.ftp.connect(self.host, self.port)
        self.ftp.login(self.username, self.password)
        print(f"Connected to {self.host} as {self.username}")

    def disconnect(self):
        """Close FTP connection and database connection"""
        if self.ftp:
            self.ftp.quit()
            print("FTP connection closed")
        if self.conn:
            self.conn.close()
            print("Database connection closed")

    def create_backup_dir(self, suffix=""):
        """Create local backup directory with timestamp and optional suffix."""
        timestamp = self.current_backup_timestamp.strftime("%Y%m%d_%H%M%S")
        self.backup_dir = os.path.join(self.local_dir, f"hostinger_backup_{timestamp}{suffix}")
        os.makedirs(self.backup_dir, exist_ok=True)
        print(f"Backup directory created: {self.backup_dir}")

    def get_remote_file_size(self, filename):
        """Get size of remote file in bytes"""
        try:
            size = self.ftp.size(filename)
            return size if size is not None else 0
        except ftplib.error_perm:
            return 0
        except Exception as e:
            return 0

    def get_remote_modification_time(self, remote_path):
        """
        Retrieves the last modification time of a file on the FTP server using MDTM.
        Returns a datetime object (UTC) or None if not available/error.
        """
        try:
            resp = self.ftp.voidcmd(f'MDTM {remote_path}')
            timestamp_str = resp[4:].strip()

            if len(timestamp_str) >= 14:
                dt_obj = datetime.strptime(timestamp_str[:14], "%Y%m%d%H%M%S")
                return dt_obj
            return None
        except ftplib.error_perm:
            return None
        except Exception as e:
            return None

    def download_file(self, remote_path, local_path, is_incremental=False):
        """Download a single file."""
        retries = 3
        display_path = self._normalize_ftp_path(remote_path)

        for attempt in range(retries):
            try:
                file_size = self.get_remote_file_size(display_path)
                status_msg = f"Downloading: {display_path} ({file_size / 1024:.1f} KB)"
                if is_incremental:
                    status_msg = f"Incremental {status_msg}"
                print(status_msg, end='\r')

                os.makedirs(os.path.dirname(local_path), exist_ok=True)

                with open(local_path, 'wb') as f:
                    self.ftp.retrbinary(f'RETR {display_path}', f.write)

                self.file_count += 1
                self.total_size += file_size

                remote_mtime = self.get_remote_modification_time(remote_path)
                if remote_mtime:
                    # Set local file modification time to match remote if possible
                    # access time (atime) can be left as current or set to mtime for simplicity
                    os.utime(local_path,
                             (time.time(), remote_mtime.timestamp()))  # using current time for atime, mtime from remote

                return True
            except Exception as e:
                if attempt == retries - 1:
                    print(f"\nFailed to download {display_path} after {retries} attempts: {e}")
                    return False
                time.sleep(2)
        return False

    def download_directory(self, remote_path, local_path, last_incremental_time=None):
        """Recursively download a directory, with incremental logic."""
        original_pwd = None
        try:
            original_pwd = self.ftp.pwd()

            print(f"Entering remote directory: {remote_path}")
            self.ftp.cwd(remote_path)
            self.dir_count += 1

            items = []
            self.ftp.retrlines('NLST', items.append)

            current_remote_dir = self.ftp.pwd()

            for item in items:
                if item in ['.', '..']:
                    continue

                remote_item = self._normalize_ftp_path(current_remote_dir + '/' + item)
                local_item = os.path.join(local_path, item)

                try:
                    temp_pwd = self.ftp.pwd()
                    try:
                        self.ftp.cwd(remote_item)  # Attempt to CWD
                        # If CWD succeeds, it's a directory
                        print(f"Found directory: {remote_item}")
                        os.makedirs(local_item, exist_ok=True)
                        self.download_directory(remote_item, local_item, last_incremental_time)  # Recursive call
                        self.ftp.cwd(temp_pwd)
                    except ftplib.error_perm as e_perm:
                        # If CWD fails with 550, it's likely a file
                        if "550" in str(e_perm):
                            if last_incremental_time:
                                # Incremental logic: check modification time
                                remote_mtime = self.get_remote_modification_time(remote_item)
                                # Only download if remote_mtime is available and newer than last_incremental_time
                                if remote_mtime and remote_mtime > last_incremental_time:
                                    print(f"File modified: {remote_item}")
                                    self.download_file(remote_item, local_item, is_incremental=True)
                                else:
                                    # If file already exists locally and is not modified, skip
                                    if os.path.exists(local_item):
                                        pass  # print(f"Skipping unmodified/existing file: {remote_item}")
                                    else:  # If file doesn't exist locally, it's a new file, download it in incremental
                                        print(f"New file in incremental: {remote_item}")
                                        self.download_file(remote_item, local_item, is_incremental=True)

                            else:
                                # Full backup, download unconditionally
                                self.download_file(remote_item, local_item)
                            self.ftp.cwd(temp_pwd)
                        else:
                            print(f"\nFTP Permission Error on {remote_item}: {e_perm}")
                            self.ftp.cwd(temp_pwd)
                            continue
                    except Exception as e_cwd:
                        print(f"\nError trying to CWD to {remote_item}: {e_cwd}")
                        self.ftp.cwd(temp_pwd)
                        continue
                except Exception as e:
                    print(f"\nError processing {remote_item}: {e}")
                    continue

            # Go up one level after processing all items in current directory
            if self.ftp.pwd() == remote_path:
                self.ftp.cwd('..')
            elif original_pwd:
                self.ftp.cwd(original_pwd)

        except Exception as e:
            print(f"\nError accessing remote directory {remote_path}: {e}")
            if original_pwd:
                try:
                    self.ftp.cwd(original_pwd)
                except Exception as e_revert:
                    print(f"Could not revert to original directory {original_pwd}: {e_revert}")

    def run_backup(self):
        """Execute the full or incremental backup process."""
        self.start_time_actual = time.time()
        self.current_backup_timestamp = datetime.now()  # Capture start time of this run

        backup_status = 'failed'  # Default status

        try:
            self.connect()  # Connects FTP and initializes DB

            last_full_backup, last_incremental_backup = self._get_last_backup_times()

            # Determine backup type based on schedule and last backup times
            now = self.current_backup_timestamp

            is_full_backup = False
            backup_type_name = "incremental"  # Default for record

            if self.backup_type == 'full':  # Explicitly requested full backup
                is_full_backup = True
                backup_type_name = "full"
            elif self.backup_type == 'auto':
                # Check if it's time for a weekly full backup
                # current time is Sunday, June 29, 2025 at 6:18:37 PM IST
                # Pune, Maharashtra, India.
                # Assuming "weekly" means every 7 days from the last full backup,
                # or if the last full backup was more than 7 days ago.
                # Or, if today is Sunday (for a fixed weekly schedule)

                # Option 1: Based on timedelta from last full
                if last_full_backup is None or (now - last_full_backup > timedelta(weeks=1)):
                    is_full_backup = True
                    backup_type_name = "full"
                # Option 2: Based on day of week (e.g., always Sunday for full)
                # if now.weekday() == 6: # Monday is 0, Sunday is 6
                #     is_full_backup = True
                #     backup_type_name = "full"

            if is_full_backup:
                print("\nPerforming a FULL backup...")
                self.create_backup_dir(suffix="_FULL")
                self._record_backup_start("full", self.backup_dir)
                self.download_directory(self.remote_dir, self.backup_dir)
            else:  # Incremental
                print("\nPerforming an INCREMENTAL backup...")
                if last_incremental_backup is None:
                    print("No previous incremental baseline found. Performing a full backup instead.")
                    # Fallback to full if no incremental baseline
                    self.create_backup_dir(suffix="_FULL")
                    self._record_backup_start("full", self.backup_dir)  # Record as full backup
                    self.download_directory(self.remote_dir, self.backup_dir)
                    backup_type_name = "full"
                else:
                    self.create_backup_dir(suffix="_INC")
                    self._record_backup_start("incremental", self.backup_dir)
                    self.download_directory(self.remote_dir, self.backup_dir,
                                            last_incremental_time=last_incremental_backup)
                    backup_type_name = "incremental"

            backup_status = 'success'  # If we reached here, it was successful

        except Exception as e:
            print(f"\nBackup failed: {e}")
            backup_status = 'failed'  # Set status to failed
        finally:
            self.disconnect()  # Closes FTP and DB connections
            self._update_backup_record(backup_status)  # Update the record regardless of success/failure

            # Print summary
            duration = time.time() - self.start_time_actual
            print("\n" + "=" * 50)
            print("Backup Complete!")
            print(f"Type: {backup_type_name.capitalize()}")
            print(f"Directories: {self.dir_count}")
            print(f"Files: {self.file_count}")
            print(f"Total size: {self.total_size / 1024 / 1024:.2f} MB")
            print(f"Duration: {duration:.1f} seconds")
            print(f"Backup location: {self.backup_dir}")
            print("=" * 50)
            print(f"Backup details stored in {self.db_path}")


def main():
    parser = argparse.ArgumentParser(description='Hostinger Complete Website Backup')
    parser.add_argument('--host', help='FTP hostname (e.g., ftp.yourdomain.com)')
    parser.add_argument('--username', help='FTP username')
    parser.add_argument('--remote-dir', help='Remote directory to backup from', default='/')
    parser.add_argument('--output', help='Local directory to save backup', default='.')
    parser.add_argument('--type', choices=['full', 'incremental', 'auto'], default='auto',
                        help='Backup type: "full", "incremental", or "auto" (default). '
                             'Auto will decide based on last backup state.')
    parser.add_argument('--db-file', default='backup_history.db',
                        help='Path to the SQLite database file for backup history.')

    args = parser.parse_args()

    host = args.host or input("Enter FTP hostname: ")
    username = args.username or input("Enter FTP username: ")
    password = getpass.getpass("Enter FTP password: ")
    remote_dir = args.remote_dir
    output_dir = os.path.expanduser(args.output)


    remote_dir = 'domains'
    host = '82.25.107.7'
    username = 'u423778680'
    password = 'c1wTRY66^6'
    output_dir = 'C:\\Users\\LENOVO\\PycharmProjects\\pythonProject\\hostinger'
    db_path = 'backup_history.db'

    backup = HostingerBackup(
        host=host,
        username=username,
        password=password,
        remote_dir=remote_dir,
        local_dir=output_dir,
        db_path=args.db_file
    )

    # The backup_type attribute is set in HostingerBackup's __init__
    # and then used by run_backup to decide behavior.
    backup.backup_type = args.type

    backup.run_backup()


if __name__ == "__main__":
    main()