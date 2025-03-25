#!/usr/bin/env python3
"""
PDF Comparison Tool for LaTeX Cleaner

This script compiles both the original and cleaned LaTeX projects,
then compares the resulting PDFs to ensure they are identical.
"""

import os
import sys
import subprocess
import argparse
import logging
import hashlib
import difflib
import re
from PyPDF2 import PdfReader
from pdf2image import convert_from_path
from PIL import Image
import numpy as np

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def compile_latex(project_dir, main_tex):
    """
    Compile a LaTeX project and return the path to the generated PDF.

    Args:
        project_dir: Path to the LaTeX project directory
        main_tex: Path to the main TeX file (relative to project_dir)

    Returns:
        Path to the generated PDF file, or None if compilation failed
    """
    try:
        # Ensure we're in the project directory
        original_dir = os.getcwd()
        os.chdir(project_dir)

        # Get the base path and filename of main_tex
        tex_dir = os.path.dirname(main_tex)
        if tex_dir:
            os.chdir(tex_dir)
            main_tex_file = os.path.basename(main_tex)
        else:
            main_tex_file = main_tex

        # Remove potential .tex extension to get PDF name
        pdf_name = os.path.splitext(main_tex_file)[0] + ".pdf"

        # Try to compile using latexmk (more reliable)
        logger.info(f"Compiling {main_tex_file} in {os.getcwd()}")
        result = subprocess.run(
            ["latexmk", "-pdf", main_tex_file, "--shell-escape"],
            capture_output=True,
            text=True,
        )

        # If latexmk fails, try pdflatex
        if result.returncode != 0:
            logger.warning("latexmk failed, trying pdflatex...")
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", main_tex_file],
                capture_output=True,
                text=True,
            )

            # Run bibtex if needed
            if "No file" in result.stdout and ".aux" in result.stdout:
                logger.info("Running bibtex...")
                subprocess.run(
                    ["bibtex", os.path.splitext(main_tex_file)[0]], capture_output=True
                )

                # Run pdflatex again (twice to ensure references are correct)
                subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", main_tex_file],
                    capture_output=True,
                    text=True,
                )
                subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", main_tex_file],
                    capture_output=True,
                    text=True,
                )

        # Check if PDF was generated
        if os.path.exists(pdf_name):
            # Return absolute path
            pdf_path = os.path.abspath(pdf_name)
            logger.info(f"Successfully compiled: {pdf_path}")
            return pdf_path
        else:
            logger.error(f"PDF not generated. Compilation failed.")
            return None

    except Exception as e:
        logger.error(f"Error compiling LaTeX: {e}")
        return None
    finally:
        # Restore original directory
        os.chdir(original_dir)


def hash_file(file_path):
    """Calculate SHA-256 hash of a file"""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()


def compare_pdf_hashes(pdf1_path, pdf2_path):
    """Compare hashes of two PDF files"""
    hash1 = hash_file(pdf1_path)
    hash2 = hash_file(pdf2_path)

    if hash1 == hash2:
        logger.info("PDF hashes match perfectly! Content is identical.")
        return True
    else:
        logger.info("PDF hashes don't match. Further checking needed.")
        return False


def extract_pdf_text(pdf_path):
    """Extract text content from a PDF"""
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n\n"
        return text
    except Exception as e:
        logger.error(f"Error extracting PDF text: {e}")
        return None


def compare_pdf_text(pdf1_path, pdf2_path, verbose=False):
    """Compare text content of two PDFs"""
    text1 = extract_pdf_text(pdf1_path)
    text2 = extract_pdf_text(pdf2_path)

    if text1 is None or text2 is None:
        return False

    # Normalize text (remove excess whitespace)
    text1 = re.sub(r"\s+", " ", text1).strip()
    text2 = re.sub(r"\s+", " ", text2).strip()

    if text1 == text2:
        logger.info("PDF text content matches perfectly!")
        return True
    else:
        # Show differences
        diff = difflib.unified_diff(
            text1.splitlines(),
            text2.splitlines(),
            fromfile="Original PDF",
            tofile="Cleaned PDF",
            lineterm="",
        )

        if verbose:
            diff_text = "\n".join(list(diff))
            logger.info(f"PDF text content has differences:\n{diff_text}\n...")
        return False


def convert_pdf_to_images(pdf_path, dpi=300):
    """Convert PDF to list of images"""
    try:
        return convert_from_path(pdf_path, dpi=dpi)
    except Exception as e:
        logger.error(f"Error converting PDF to images: {e}")
        return []


def compare_pdf_visually(pdf1_path, pdf2_path, threshold=0.01):
    """Compare visual content of two PDFs"""
    images1 = convert_pdf_to_images(pdf1_path)
    images2 = convert_pdf_to_images(pdf2_path)

    if len(images1) != len(images2):
        logger.info(
            f"PDFs have different page counts: Original {len(images1)} pages, Cleaned {len(images2)} pages"
        )
        return False

    identical = True
    for i, (img1, img2) in enumerate(zip(images1, images2)):
        # Ensure both images have the same dimensions
        if img1.size != img2.size:
            logger.info(
                f"Page {i+1} has different dimensions: {img1.size} vs {img2.size}"
            )
            identical = False
            continue

        # Convert to NumPy arrays for comparison
        arr1 = np.array(img1)
        arr2 = np.array(img2)

        # Calculate differences
        diff_pixels = np.sum(arr1 != arr2)
        total_pixels = arr1.size
        diff_ratio = diff_pixels / total_pixels

        if diff_ratio > threshold:
            logger.info(f"Page {i+1} has difference ratio: {diff_ratio:.2%}")
            identical = False

    return identical


def main():
    parser = argparse.ArgumentParser(
        description="Compare PDFs from original and cleaned LaTeX projects"
    )
    parser.add_argument(
        "--original", "-o", required=True, help="Original LaTeX project directory"
    )
    parser.add_argument(
        "--cleaned", "-c", required=True, help="Cleaned LaTeX project directory"
    )
    parser.add_argument(
        "--main-tex",
        "-m",
        required=True,
        help="Main TeX file (relative to project directory)",
    )
    parser.add_argument(
        "--visual",
        action="store_true",
        help="Perform visual comparison (slower but more accurate)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed differences"
    )

    args = parser.parse_args()

    # Compile both projects
    logger.info("Compiling original project...")
    original_pdf = compile_latex(args.original, args.main_tex)
    if not original_pdf:
        logger.error("Original project compilation failed!")
        return 1

    logger.info("Compiling cleaned project...")
    cleaned_pdf = compile_latex(args.cleaned, args.main_tex)
    if not cleaned_pdf:
        logger.error("Cleaned project compilation failed!")
        return 1

    # Compare PDFs
    logger.info("Comparing PDF files...")
    if compare_pdf_hashes(original_pdf, cleaned_pdf):
        logger.info("✅ Congratulations! The PDFs are identical.")
        return 0

    # Hashes differ, check text content
    logger.info("Comparing PDF text content...")
    text_identical = compare_pdf_text(original_pdf, cleaned_pdf, args.verbose)

    # Perform visual comparison if requested
    if args.visual:
        logger.info("Performing visual comparison...")
        visually_identical = compare_pdf_visually(original_pdf, cleaned_pdf)
        if visually_identical:
            logger.info("✅ Visual content is identical!")
        else:
            logger.info("❌ Visual content has differences.")

    # Summarize results
    if text_identical:
        logger.info("✅ Text content is identical! PDFs may only differ in metadata.")
        return 0
    else:
        logger.info(
            "❌ PDF content has differences. The cleaning process may have affected the document."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
