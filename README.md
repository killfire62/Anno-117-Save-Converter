# Anno 117 Save Converter for Goldberg Emulator

Built with Antigravity (Google's advanced AI coding assistant).

This repository provides a simple tool to convert Anno 117 save files (`.a8s`) to the Goldberg emulator format (`.save`) and back.

## Features
- **Automatic path detection** for standard Anno 117 and Goldberg emulator directories.
- **GUI** built with Tkinter (three tabs for import, export and single‑file conversion).
- **Command‑line interface** for scripting and batch conversions.
- **Standalone executable** (`Anno117_Save_Converter.exe`) generated with PyInstaller for easy distribution.

## Requirements
- Python 3.9+ (if running from source).
- No external dependencies beyond the standard library (Tkinter is included with Python on Windows).

## Usage
### From source (Python)
```bash
# Install (optional) a virtual environment
python -m venv venv
venv\\Scripts\\activate

# Run the GUI
python anno117_save_converter.py

# Or use the CLI
python anno117_save_converter.py --help
```
### Stand‑alone executable
Download `Anno117_Save_Converter.exe` from the **Releases** page and run it directly. No Python installation is required.

## Building the executable yourself
```bash
pip install pyinstaller
pyinstaller --onefile --noconsole anno117_save_converter.py
```
The resulting binary will be located in the `dist/` folder.

## Contributing
Feel free to open issues or submit pull requests. Please keep the code Pythonic and update the documentation when adding new features.

## License
This project is licensed under the MIT License – see the `LICENSE` file for details.
