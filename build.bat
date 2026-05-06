@echo off
echo Installing dependencies...
pip install pyinstaller pyautogui keyboard pyperclip pystray Pillow

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
  --hidden-import=PIL ^
  --hidden-import=PIL.Image ^
  --hidden-import=PIL.ImageDraw ^
  auto_typer.py

echo.
echo Build complete! Find AutoTyper.exe in the dist\ folder.
pause
