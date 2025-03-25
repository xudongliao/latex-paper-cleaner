# LaTeX Paper Cleaner

A toolset for cleaning LaTeX projects for arXiv/camera-ready submissions and verifying the resulting PDFs.

## Overview

This repository contains two main tools:

1. **LaTeX Paper Cleaner** (`latex_cleaner.py`): Creates a clean version of your LaTeX project by:

   - Only keeping necessary TeX files that are actually included in the main document
   - Only keeping figures that are actually used in the paper
   - Removing all comments from TeX files
   - Only keeping bibliography entries that are actually cited in the paper

2. **PDF Comparison Tool** (`compare_pdfs.py`): Verifies that your cleaned project compiles to the same PDF as the original by:
   - Automatically compiling both the original and cleaned versions
   - Comparing PDF content using multiple methods (hash, text, visual)
   - Identifying specific differences when they exist

## Installation

### Requirements

- Python 3.6+
- LaTeX distribution (TeX Live, MiKTeX, etc.)
- Python dependencies: `PyPDF2`, `pytesseract`, `pdf2image`, `Pillow`, `numpy`

```bash
pip install PyPDF2 pytesseract pdf2image Pillow numpy
```

For PDF to image conversion, you also need to install Poppler:

- Ubuntu/Debian: `apt-get install poppler-utils`
- macOS: `brew install poppler`
- Windows: Download from [here](https://github.com/oschwartz10612/poppler-windows/releases/)

For OCR capabilities, you need Tesseract:

- Ubuntu/Debian: `apt-get install tesseract-ocr`
- macOS: `brew install tesseract`
- Windows: Download from [here](https://github.com/UB-Mannheim/tesseract/wiki)

## Usage

### LaTeX Paper Cleaner

```bash
python latex_cleaner.py --source_dir /path/to/original/project --output_dir /path/to/cleaned/project --main_tex main.tex
```

Options:

- `--source_dir` or `-s`: Source LaTeX project directory (required)
- `--output_dir` or `-o`: Output directory for cleaned project (default: "./cleaned_project")
- `--main_tex` or `-m`: Main TeX file (relative to source_dir, will try to detect automatically if not specified)
- `--verbose` or `-v`: Enable verbose output (print all dependencies)

### PDF Comparison Tool

```bash
python compare_pdfs.py --original /path/to/original/project --cleaned /path/to/cleaned/project --main-tex main.tex
```

Options:

- `--original` or `-o`: Original LaTeX project directory (required)
- `--cleaned` or `-c`: Cleaned LaTeX project directory (required)
- `--main-tex` or `-m`: Main TeX file (relative to project directories, required)
- `--visual`: Perform visual comparison (slower but more accurate)
- `--verbose` or `-v`: Show detailed differences

## Features

### LaTeX Paper Cleaner Features

- Recursively tracks dependencies from the main TeX file
- Identifies and keeps only necessary files
- Removes all comments while preserving document structure
- Creates a clean dependency tree visualization
- Preserves both image and bibliography references

### PDF Comparison Tool Features

- Automatic compilation of both original and cleaned projects
- Multiple verification methods:
  - Hash comparison (fastest, exact match required)
  - Text content comparison (robust to metadata changes)
  - Visual comparison (catches rendering differences)
- Detailed reporting of differences when found

## Example

```bash
# Clean a LaTeX project
python latex_cleaner.py -s ~/projects/my_paper -o ./cleaned_paper -m main.tex

# Verify the cleaned project produces the same PDF
python compare_pdfs.py -o ~/projects/my_paper -c ./cleaned_paper -m main.tex --visual
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
