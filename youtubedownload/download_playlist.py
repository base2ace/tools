from pytube import Playlist, YouTube
from moviepy.editor import *
import re


def convert_mp4_to_mp3(input_folder):
    print(f"Starting audio conversion to mp3 format.")
    for root, subdirs, files in os.walk(input_folder):
        audio_folder = os.path.join(root, 'Audio')
        os.makedirs(audio_folder, exist_ok=True)

        for file in files:
            try:
                if file.lower().endswith('.mp4'):
                    mp4_path = os.path.join(root, file)
                    print(f"Processing " + mp4_path)
                    mp3_path = os.path.join(audio_folder, os.path.splitext(file)[0] + '.mp3')
                    video_clip = VideoFileClip(mp4_path)
                    audio_clip = video_clip.audio
                    audio_clip.write_audiofile(mp3_path)
                    audio_clip.close()
                    video_clip.close()
                    print(f"Audio conversion done for " + mp3_path)
            except Exception as e:
                print(str(e))
                pass

    print(f"Audio conversion to mp3 format is complete.")


import yt_dlp

def download_youtube_video(video_url, output_folder):
    ydl_opts = {
        'format': 'best',  # Get the best format available
        'outtmpl': os.path.join(output_folder, '%(title)s.%(ext)s'),  # Define the output template
        'noplaylist': True,  # Ensure we're only downloading a single video, not a playlist
        'quiet': False,  # Provide output for logging
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=True)
            file_name = ydl.prepare_filename(info_dict)
            print(f"Downloaded: {file_name}")
            return file_name
    except yt_dlp.utils.DownloadError as e:
        print(f"Download error again: {e}")
    except Exception as e:
        print(f"Error downloading again {video_url}: {e}")

# def download_video(video_url, output_folder):
#     try:
#         yt = YouTube(video_url)
#         video = yt.streams.get_highest_resolution()
#         video.download(output_folder)
#         fileName = video.title
#         return fileName
#     except Exception as e:
#         print(f"Error downloading {video_url}: {e}")
#         fileName = download_youtube_video(video_url, output_folder)
#         return fileName

import yt_dlp

import os
import yt_dlp


def download_video(video_url, output_folder):
    # Variable to store the downloaded file name
    downloaded_file_name = None

    def download_hook(d):
        """Function to handle download progress updates and capture the file name."""
        nonlocal downloaded_file_name  # Access the variable from the outer scope

        if d['status'] == 'finished':
            # Capture the downloaded file name
            downloaded_file_name = d['filename']
            print(f"Download complete: {downloaded_file_name}")
        elif d['status'] == 'downloading':
            print(
                f"Downloading: {d['_percent_str']} of {d['_total_bytes_str']} at {d['_speed_str']} ETA {d['_eta_str']}")

    try:
        # Define the options for yt-dlp
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',  # Download best video and audio
            'outtmpl': os.path.join(output_folder, '%(title)s.%(ext)s'),  # Save with video title as filename
            'quiet': False,  # Set to True if you don't want output printed to console
            'progress_hooks': [download_hook],  # Hook to check the status of download
            'merge_output_format': 'mp4',  # Merge the formats using ffmpeg into mp4
            'cookies-from-browser': 'chrome',
        }

        # Ensure the output directory exists
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        # Use yt-dlp to download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

    except Exception as e:
        print(f"Error Downloading Video: {video_url}")
        print(f"Error: {e}")

    # Return the downloaded file name to the caller
    return downloaded_file_name




# def download_video(video_url, output_folder):
#     # Variable to store the downloaded file name
#     downloaded_file_name = None
#
#     def download_hook(d):
#         """Function to handle download progress updates and capture the file name."""
#         nonlocal downloaded_file_name  # Access the variable from the outer scope
#
#         if d['status'] == 'finished':
#             # Capture the downloaded file name
#             downloaded_file_name = d['filename']
#             print(f"Download complete: {downloaded_file_name}")
#         elif d['status'] == 'downloading':
#             print(
#                 f"Downloading: {d['_percent_str']} of {d['_total_bytes_str']} at {d['_speed_str']} ETA {d['_eta_str']}")
#
#     try:
#         # Define the options for yt-dlp
#         ydl_opts = {
#             'format': 'best',  # Select the best quality format available
#             'outtmpl': os.path.join(output_folder, '%(title)s.%(ext)s'),  # Save with video title as filename
#             'quiet': False,  # Set to True if you don't want output printed to console
#             'progress_hooks': [download_hook],  # Hook to check the status of download
#         }
#
#         # Ensure the output directory exists
#         if not os.path.exists(output_folder):
#             os.makedirs(output_folder)
#
#         # Use yt-dlp to download the video
#         with yt_dlp.YoutubeDL(ydl_opts) as ydl:
#             ydl.download([video_url])
#
#     except Exception as e:
#         print(f"Error Downloading Video: {video_url}")
#         print(f"Error: {e}")
#
#     # Return the downloaded file name to the caller
#     return downloaded_file_name

def download_playlist(playlist_url, convert_to_mp3=False):
    try:
        playlist = Playlist(playlist_url)
        playlist_title = playlist.title
        output_folder = os.path.join("downloads", playlist_title.split()[0])

        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        print(f"Downloading playlist: {playlist_title}\n")

        for i, video_url in enumerate(playlist.video_urls, start=1):
            print(f"Starting video download {i}/{len(playlist.video_urls)}")
            download_video(video_url, output_folder)

        print("\nPlaylist download completed successfully!")
        return output_folder

    except Exception as e:
        print(f"Error downloading playlist: {e}")

def download_video_warpper(url, convert_to_audio):
    try:
        output_folder = os.path.join("downloads", "youtube_songs")

        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        print(f"Downloading Video: {url}")
        fileName = download_video(url, output_folder)

        print(fileName + ".mp4 download completed successfully!")

        return output_folder
    except:
        print(f"Error Downloading Video: {url}")
        output_folder = ""
        return output_folder

if __name__ == "__main__":
    input_file = "urls.txt"  # File containing the YouTube playlist URLs, one per line

    with open(input_file, "r") as file:
        urls = [line.strip() for line in file]

    output_folder = "downloads"

    for url in urls:
        if url.strip() != "":
            if "playlist" in url:
                output_folder = download_playlist(url, False)
            else:
                output_folder = download_video_warpper(url, False)

    if output_folder != "":
        convert_mp4_to_mp3(output_folder)

