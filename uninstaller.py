# Let's import the necessary libraries.
# 're' is for Regular Expressions (finding text patterns).
# 'subprocess' lets Python run terminal/cmd commands just like a real user.
# 'os' is to interact with the Operating System (finding folders, variables).
# 'shutil' is a utility to perform high-level file operations (like destroying full folders).
import os
import re
import shutil
import subprocess


def get_installed_apps_from_winget():
    """
    Executes 'winget list' to retrieve all installed applications.
    Parses the raw text output into a clean list of structured dictionaries.
    """
    print("\n[System] Querying Winget for installed applications. Please wait...")
    try:
        # Running 'winget list' in the background.
        # capture_output=True means we want to intercept the text it spits out.
        # encoding="utf-8" is crucial because Windows terminal can output weird characters that break Python.
        result = subprocess.run(
            ["winget", "list"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",  # If there's an alien character, just ignore it instead of crashing.
        )

        # returncode 0 means the command executed perfectly. Anything else is an error.
        if result.returncode != 0:
            print("[Error] Failed to populate application list from Winget.")
            return []

        # Split the massive block of text into a list of individual lines.
        raw_lines = result.stdout.splitlines()
        apps_list = []

        # Winget outputs a header (Name, Id, Version, etc.) and then a separator line of dashes '---'.
        # We need to find that dash line to know where the actual apps start.
        start_index = -1

        # enumerate() gives us both the index number (i) and the content (line).
        for i, line in enumerate(raw_lines):
            # If the line starts with dashes, the next line (i + 1) is our first app!
            if line.startswith("---") or "---" in line:
                start_index = i + 1
                break

        # Fallback safeguard: if Winget updates its layout and we can't find '---',
        # we just assume the apps start at line 2. Better safe than crashing.
        if start_index == -1 or start_index >= len(raw_lines):
            start_index = 2

        # Now, we loop only through the lines that actually contain app data.
        for line in raw_lines[start_index:]:
            # If the line is empty (just spaces), skip it.
            if not line.strip():
                continue

            # Winget spaces columns out dynamically to make it look pretty in the terminal.
            # We use 're.split' to chop the line wherever there are 2 or more spaces.
            # This perfectly isolates the Name, ID, Version, etc.
            parts = re.split(r"\s{2,}", line.strip())

            # As long as we caught at least a Name and an ID, we're good.
            if len(parts) >= 2:
                app_name = parts[0]
                app_id = parts[1]

                # Append a dictionary (key-value pair) to our main list.
                apps_list.append({"name": app_name, "id": app_id})

        return apps_list

    except Exception as e:
        # Catch-all for unexpected crashes (e.g., Winget is not installed).
        print(f"[Critical Error] Failed parsing software subsystem mapping: {e}")
        return []


def execute_package_uninstall(package_id, package_name):
    """
    Triggers 'winget uninstall' to remove targeted components cleanly.
    Returns True if successful, False otherwise.
    """
    print(f"\n[Uninstaller] Purging application: {package_name}...")
    try:
        # Building the terminal command. '--accept-source-agreements' stops Winget from pausing to ask for Y/N.
        command = [
            "winget",
            "uninstall",
            "--id",
            package_id,
            "--accept-source-agreements",
        ]

        # check=True tells Python to raise an exception if the command fails.
        subprocess.run(command, check=True)
        print(f"[Success] {package_name} removed from system shell configuration.")
        return True
    except subprocess.CalledProcessError:
        print(
            f"[Error] Winget environment rejected processing removal parameters for: {package_name}"
        )
        return False


def clean_safe_leftovers(app_name):
    """
    Fase 2: The Leftover Hunter.
    Safely scans specific Windows caching directories (AppData, LocalAppData, ProgramData)
    for remnant folders related to the uninstalled app.
    """
    print(f"\n[Scanner] Initiating safe leftover scan for: {app_name}...")

    # We ask Windows for the real paths of these system folders.
    # Hardcoding "C:\Users\Name..." is a rookie mistake; env vars are the pro way.
    appdata = os.environ.get("APPDATA")  # Usually C:\Users\Name\AppData\Roaming
    localappdata = os.environ.get("LOCALAPPDATA")  # Usually C:\Users\Name\AppData\Local
    programdata = os.environ.get("PROGRAMDATA")  # Usually C:\ProgramData

    # Put them in a list. If one of them is None (which shouldn't happen, but we are seniors), we filter it out.
    search_paths = [path for path in [appdata, localappdata, programdata] if path]

    # Apps often have long names like "VLC media player", but the folder is just "vlc".
    # We grab the very first word of the app name to use as a broad search keyword.
    # split()[0] breaks the string by spaces and gets the first chunk.
    search_keyword = app_name.split()[0].lower()

    # We will store the paths of suspicious leftover folders here.
    found_leftovers = []

    # Loop through each major system directory...
    for base_path in search_paths:
        try:
            # os.listdir gets everything inside that folder (files and other folders).
            for item in os.listdir(base_path):
                # We build the full path: e.g., C:\Users\Name\AppData\Roaming\Discord
                full_item_path = os.path.join(base_path, item)

                # We only care about Directories (folders). Leftover files alone are usually harmless.
                if os.path.isdir(full_item_path):
                    # If our keyword (e.g., 'discord') is anywhere in the folder name...
                    if search_keyword in item.lower():
                        # Gotcha! Add it to the list.
                        found_leftovers.append(full_item_path)
        except PermissionError:
            # Sometimes Windows locks system folders. We just gracefully ignore and move on.
            continue

    # If we didn't find anything, just tell the user and exit the function.
    if not found_leftovers:
        print("[Scanner] No obvious leftover directories found. The system is clean.")
        return

    # If we did find stuff, we MUST ask the user. Blind deletion is dangerous.
    print(f"\n[Warning] Found {len(found_leftovers)} potential leftover folder(s):")
    for leftover in found_leftovers:
        print(f" -> {leftover}")

    choice = (
        input("\nDo you want to PERMANENTLY delete these remnant folders? (y/n): ")
        .strip()
        .lower()
    )

    if choice == "y":
        for folder in found_leftovers:
            if os.path.exists(folder):
                try:
                    print(f"[Cleanup] Shredding directory: {folder}...")
                    # shutil.rmtree obliterates a folder and EVERYTHING inside it. Powerful and dangerous.
                    shutil.rmtree(folder)
                    print("[Cleanup] Directory destroyed.")
                    
                except FileNotFoundError:
                    print(
                        f"[Cleanup] Directory already deleted: {folder}."
                    )
            else:
                print(f"[Cleanup] Directory {folder} does not exist, skipping...")
    else:
        print("[Action Log] Leftover cleanup bypassed by the user.")


def prompt_software_removal():
    """
    Orchestrates the visualization and batch uninstallation lifecycle of system software components.
    Now includes Phase 2 Leftover scanning.
    """
    # Guard trigger confirmation step to prevent accidental clicks.
    confirm_enter = (
        input(
            "\nAre you sure you want to initialize the Application Uninstallation sub-shell? (y/n): "
        )
        .strip()
        .lower()
    )
    if confirm_enter != "y":
        print("[Action Log] Uninstaller interface cancelled. Returning to main menu.")
        return

    # Gathering apps from Winget.
    installed_apps = get_installed_apps_from_winget()
    if not installed_apps:
        print("[Error Log] No installed components found. Aborting workflow.")
        return

    # Enforcing strict alphabetical order as the global default behavior.
    # lambda x: x["name"].lower() tells Python to sort by the 'name' key of the dictionary, ignoring uppercase/lowercase.
    sorted_apps = sorted(installed_apps, key=lambda x: x["name"].lower())

    # Printing compiled inventory on screen mapped dynamically 1 to X.
    print("\n========================================")
    print("      CURRENTLY INSTALLED SOFTWARE      ")
    print("========================================")
    for index, app in enumerate(sorted_apps, start=1):
        print(f"{index}. {app['name']}")
    print("========================================")

    user_input = input(
        "\nEnter the numbers of the software you want to UNINSTALL, separated by spaces (e.g., '4 12'): "
    ).strip()
    if not user_input:
        print("[Action Log] Empty parameter block submitted. Aborting operation.")
        return

    # Parsing inputs into an array (list) of integers.
    selected_indexes = []
    for token in user_input.split():
        if token.isdigit():
            selected_indexes.append(int(token))
        else:
            print(
                f"[Input Warning] '{token}' is not a valid number mapping string. Skipping."
            )

    # Validating if the numbers the user typed actually exist in our list.
    valid_apps_to_remove = []
    for idx in selected_indexes:
        actual_pos = (
            idx - 1
        )  # Arrays start at 0, but our list starts at 1. We must subtract 1.
        if 0 <= actual_pos < len(sorted_apps):
            valid_apps_to_remove.append(sorted_apps[actual_pos])
        else:
            print(
                f"[Input Warning] Index position '{idx}' points outside database matrix bounds. Skipping."
            )

    if not valid_apps_to_remove:
        print(
            "[Action Log] Queue buffer empty. No valid applications selected. Aborting."
        )
        return

    # Secondary deep verification checkpoint. Never execute destruction without confirmation.
    print(
        "\n[CRITICAL VERIFICATION] The following applications will be REMOVED permanently from this machine:"
    )
    for app in valid_apps_to_remove:
        print(f" -> {app['name']} ({app['id']})")

    final_security_gate = (
        input(
            "\nAre you absolutely certain you want to commit this destruction sequence? (y/n): "
        )
        .strip()
        .lower()
    )

    if final_security_gate == "y":
        # Let's loop through the apps the user wants gone.
        for app in valid_apps_to_remove:
            # First, we run the official uninstaller.
            success = execute_package_uninstall(app["id"], app["name"])

            # If the official uninstaller worked, we initiate Phase 2: Leftover Hunt.
            if success:
                clean_safe_leftovers(app["name"])

        print(
            "\n[System Log] Finished executing scheduled batch uninstallation and cleanup routines."
        )
    else:
        print("\n[Action Log] Process cancelled by user. Operational state preserved.")
