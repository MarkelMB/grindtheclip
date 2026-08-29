import os
import win32com.client

desktop = r"C:\Users\marke\Desktop"
shortcut_path = os.path.join(desktop, "The Choicer Voicer - Clone.lnk")
target_path = r"C:\Users\marke\.gemini\antigravity\scratch\voice_choicer\Jugar Choicer Voicer.bat"
icon_path = r"C:\Users\marke\AppData\Roaming\YeahMaybe\ChoicerVoicer\game\packs_voice\The Choicer Voicer Tutorial Pack\icon.png"

shell = win32com.client.Dispatch("WScript.Shell")
shortcut = shell.CreateShortCut(shortcut_path)
shortcut.Targetpath = target_path
shortcut.WorkingDirectory = r"C:\Users\marke\.gemini\antigravity\scratch\voice_choicer"
shortcut.IconLocation = f"{icon_path},0"
shortcut.save()
