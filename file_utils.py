import re
import os

def get_most_recent_file(directory, pattern):
    files = [f for f in os.listdir(directory) if re.match(pattern, f)]
    if not files:
        return None
    files_with_paths = [os.path.join(directory, f) for f in files]
    most_recent = max(files_with_paths, key=os.path.getmtime)
    return most_recent

def get_all_matching_files(directory, pattern):
    files = [f for f in os.listdir(directory) if re.match(pattern, f)]
    files_with_paths = [os.path.join(directory, f) for f in files]
    files_with_paths.sort(key=os.path.getmtime, reverse=True)
    return files_with_paths
