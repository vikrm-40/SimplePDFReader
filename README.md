# Simple PDF Reader

A Python-based PDF reader built with PyMuPDF and Tkinter, featuring:
- Open and display PDF files
- Navigate with Page Up/Down, Previous/Next buttons, and mouse wheel
- Zoom in/out with buttons
- Search across the entire document with transparent highlighting
- Horizontal scrollbar and vertical scrollbar (when zoomed in)
- Centered PDF pages with equal borders
- Custom icon for Windows executable

## Recent Changes 04/11/2025
- Reorganized search UI: Entry positioned between navigation buttons, About at end
- Removed redundant Previous/Next buttons (Page Up/Down remain)
- Updated the scroll functionality to run smoothly 

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Requirements
- Python 3.8+
- PyMuPDF (`pip install PyMuPDF`)
- Pillow (`pip install Pillow`)

## Usage
1. Run `python pdf_reader.py` to start the application.
2. To create an executable, use PyInstaller:
