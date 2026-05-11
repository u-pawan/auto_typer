@echo off
echo Installing dependencies...
pip install pyinstaller pyautogui keyboard pyperclip pystray Pillow pynput cryptography

echo.
echo Building AutoTyper.exe...
pyinstaller ^
  --onefile ^
  --windowed ^
  --name AutoTyper ^
  --add-data "engine;engine" ^
  --add-data "ui;ui" ^
  --add-data "storage;storage" ^
  --hidden-import=pyautogui ^
  --hidden-import=keyboard ^
  --hidden-import=pyperclip ^
  --hidden-import=pystray ^
  --hidden-import=pynput ^
  --hidden-import=pynput.keyboard ^
  --hidden-import=pynput.mouse ^
  --hidden-import=PIL ^
  --hidden-import=PIL.Image ^
  --hidden-import=PIL.ImageDraw ^
  --hidden-import=cryptography ^
  --hidden-import=cryptography.fernet ^
  --hidden-import=cryptography.hazmat.primitives.kdf.pbkdf2 ^
  auto_typer.py

echo.
echo Build complete! Find AutoTyper.exe in the dist\ folder.
echo.
echo Optional: To create a portable build, place a "portable.flag" file
echo next to AutoTyper.exe — data will be stored in AutoTyper_data\
echo beside the exe instead of %%APPDATA%%\AutoTyper\
pause
