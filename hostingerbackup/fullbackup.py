import os
import ftplib
from datetime import datetime
import argparse
import getpass
import time


class HostingerBackup:
    def __init__(self, host, username, password, remote_dir, local_dir, port=21):
        self.host = host
        self.username = username
        self.password = password
        # Clean and normalize the remote directory path
        # Ensure remote_dir always starts with a '/' and doesn't end with one unless it's the root
        self.remote_dir = self._normalize_ftp_path(remote_dir)
        print(f"Normalized remote_dir: {self.remote_dir}")  # For debugging

        self.local_dir = local_dir
        self.port = port
        self.ftp = None
        self.file_count = 0
        self.dir_count = 0
        self.total_size = 0
        self.start_time = None

    def _normalize_ftp_path(self, path):
        """Internal helper to ensure FTP paths use forward slashes and are absolute."""
        path = path.replace('\\', '/').strip('/')  # Replace backslashes, strip leading/trailing
        if not path:  # If path was just slashes or empty after stripping
            return '/'
        return '/' + path  # Ensure it's an absolute path

    def connect(self):
        """Establish FTP connection"""
        print(f"Connecting to {self.host}...")
        self.ftp = ftplib.FTP()
        self.ftp.connect(self.host, self.port)
        self.ftp.login(self.username, self.password)
        print(f"Connected to {self.host} as {self.username}")

    def disconnect(self):
        """Close FTP connection"""
        if self.ftp:
            self.ftp.quit()
            print("FTP connection closed")

    def create_backup_dir(self):
        """Create local backup directory with timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_dir = os.path.join(self.local_dir, f"hostinger_backup_{timestamp}")
        os.makedirs(self.backup_dir, exist_ok=True)
        print(f"Backup directory created: {self.backup_dir}")

    def get_remote_file_size(self, filename):
        """Get size of remote file in bytes"""
        try:
            size = self.ftp.size(filename)
            return size if size is not None else 0
        except ftplib.error_perm:  # Catch specific FTP errors for non-existent files
            return 0
        except Exception as e:
            return 0

    def download_file(self, remote_path, local_path):
        """Download a single file"""
        retries = 3
        for attempt in range(retries):
            try:
                # Use the normalized remote_path for display
                display_path = self._normalize_ftp_path(remote_path)
                file_size = self.get_remote_file_size(display_path)  # Use normalized path for size check
                print(f"Downloading: {display_path} ({file_size / 1024:.1f} KB)", end='\r')

                # Ensure local directory exists
                os.makedirs(os.path.dirname(local_path), exist_ok=True)

                with open(local_path, 'wb') as f:
                    self.ftp.retrbinary(f'RETR {display_path}', f.write)  # Use normalized path for RETR

                self.file_count += 1
                self.total_size += file_size
                return True
            except Exception as e:
                if attempt == retries - 1:
                    print(f"\nFailed to download {display_path} after {retries} attempts: {e}")
                    return False
                time.sleep(2)
        return False

    def download_directory(self, remote_path, local_path):
        """Recursively download a directory"""
        original_pwd = None
        try:
            original_pwd = self.ftp.pwd()  # Store current working directory before changing

            # Change to the current remote directory
            print(f"Entering remote directory: {remote_path}")
            self.ftp.cwd(remote_path)
            self.dir_count += 1

            items = []
            # NLST on current directory will give names relative to it
            self.ftp.retrlines('NLST', items.append)

            current_remote_dir = self.ftp.pwd()  # Get the absolute path after CWD

            for item in items:
                # Skip special directories
                if item in ['.', '..']:
                    continue

                # Construct proper remote path (always using forward slashes)
                # item from NLST is just the name, current_remote_dir is absolute
                remote_item = self._normalize_ftp_path(current_remote_dir + '/' + item)

                # Local path construction: item is already the basename
                local_item = os.path.join(local_path, item)

                try:
                    # Attempt to CWD into the item to check if it's a directory
                    # Need to store and revert PWD for each item check
                    temp_pwd = self.ftp.pwd()
                    try:
                        self.ftp.cwd(remote_item)
                        # If CWD succeeds, it's a directory
                        print(f"Found directory: {remote_item}")
                        os.makedirs(local_item, exist_ok=True)
                        self.download_directory(remote_item, local_item)  # Recursive call
                        self.ftp.cwd(temp_pwd)  # Change back to previous directory for the loop
                    except ftplib.error_perm as e_perm:
                        # If CWD fails with permission error, it's likely a file
                        # Error 550 often indicates "not a directory" for CWD attempts on files
                        if "550" in str(e_perm):  # Specifically check for 550
                            print(f"Found file: {remote_item}")
                            if not os.path.exists(local_item):
                                self.download_file(remote_item, local_item)
                            self.ftp.cwd(temp_pwd)  # Ensure we always change back
                        else:  # Other permission errors might need different handling
                            print(f"\nFTP Permission Error on {remote_item}: {e_perm}")
                            self.ftp.cwd(temp_pwd)
                            continue  # Skip to next item
                    except Exception as e_cwd:
                        print(f"\nError trying to CWD to {remote_item}: {e_cwd}")
                        self.ftp.cwd(temp_pwd)  # Ensure we always change back
                        continue  # Skip to next item
                except Exception as e:
                    print(f"\nError processing {remote_item}: {e}")
                    continue

            # After processing all items in the current directory, go up one level
            # This should only happen if we successfully cwd'd into remote_path initially
            if self.ftp.pwd() == remote_path:  # Check if we are still in the path we CWD'd into
                self.ftp.cwd('..')
            elif original_pwd:  # Fallback to original_pwd if current PWD is not what we expect
                self.ftp.cwd(original_pwd)

        except Exception as e:
            print(f"\nError accessing remote directory {remote_path}: {e}")
            if original_pwd:  # Try to change back even if initial CWD failed
                try:
                    self.ftp.cwd(original_pwd)
                except Exception as e_revert:
                    print(f"Could not revert to original directory {original_pwd}: {e_revert}")

    def run_backup(self):
        """Execute the full backup process"""
        self.start_time = time.time()
        try:
            self.connect()
            self.create_backup_dir()

            print(f"\nStarting backup from {self.remote_dir}...")
            # Initial call: remote_dir is already normalized to be absolute
            self.download_directory(self.remote_dir, self.backup_dir)

            # Print summary
            duration = time.time() - self.start_time
            print("\n" + "=" * 50)
            print("Backup Complete!")
            print(f"Directories: {self.dir_count}")
            print(f"Files: {self.file_count}")
            print(f"Total size: {self.total_size / 1024 / 1024:.2f} MB")
            print(f"Duration: {duration:.1f} seconds")
            print(f"Backup location: {self.backup_dir}")
            print("=" * 50)

        except Exception as e:
            print(f"\nBackup failed: {e}")
        finally:
            self.disconnect()


def main():
    # Get credentials if not provided as arguments
    remote_dir = 'domains'
    host = ''
    username = ''
    password = ''
    output_dir = 'C:\\Users\\LENOVO\\PycharmProjects\\pythonProject\\hostinger'

    backup = HostingerBackup(
        host=host,
        username=username,
        password=password,
        remote_dir=remote_dir,
        local_dir=output_dir
    )
    backup.run_backup()


if __name__ == "__main__":
    main()


