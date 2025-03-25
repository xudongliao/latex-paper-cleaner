#!/usr/bin/env python3
"""
LaTeX Paper Cleaner for arXiv Submission

This script creates a clean version of a LaTeX paper directory by:
1. Keeping only necessary TeX files that are actually included in the main document
2. Keeping only figures that are actually used in the paper
3. Removing all comments from TeX files
4. Keeping only bibliography entries that are actually cited in the paper
"""

import os
import re
import shutil
import argparse
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Regex patterns
INPUT_PATTERN = re.compile(r"\\(?:input|include|subfile)\{([^}]+)\}")
BIBLIOGRAPHY_PATTERN = re.compile(r"\\bibliography\{([^}]+)\}")
BIBLIOGRAPHYSTYLE_PATTERN = re.compile(r"\\bibliographystyle\{([^}]+)\}")
GRAPHICS_PATTERN = re.compile(r"\\(?:includegraphics)(?:\[[^\]]*\])?\{([^}]+)\}")
COMMENT_PATTERN = re.compile(r"(?<!\\)%.*?$", re.MULTILINE)
# Pattern to match all citation commands
CITATION_PATTERN = re.compile(
    r"\\(?:"
    r"cite[a-zA-Z]*|"  # Standard citation command
    r"nocite|"  # \nocite command
    r"cite\s+|"  # Allow spaces
    r"[a-zA-Z]*cite[a-zA-Z]*"  # Any command containing "cite"
    r")(?:\s+)?(?:\[[^\]]*\])?(?:\s+)?\{([^}]+)\}"
)
# Pattern to match BibTeX entries
BIBENTRY_PATTERN = re.compile(r"@\w+\s*\{\s*([^,]+),.*?(?=@|\Z)", re.DOTALL)

global_base_dir = None


def find_dependencies(
    tex_file,
    base_dir,
    dependencies=None,
    included_graphics=None,
    cited_keys=None,
    verbose=False,
    dep_tree=None,
    current_depth=0,
):
    """
    Recursively find all dependencies and build dependency tree.

    Args:
        tex_file: The path to the TeX file to analyze
        base_dir: The base directory of the project
        dependencies: Set of already found dependencies (for recursion)
        included_graphics: Set of already found graphics (for recursion)
        cited_keys: Set of citation keys (for recursion)
        verbose: Whether to print verbose information
        dep_tree: Dictionary to store the dependency tree structure
        current_depth: Current depth in the dependency tree

    Returns:
        (dependencies, included_graphics, cited_keys, dep_tree): Sets of file paths and citation keys
    """
    if dependencies is None:
        dependencies = set()
    if included_graphics is None:
        included_graphics = set()
    if cited_keys is None:
        cited_keys = set()
    if dep_tree is None:
        dep_tree = {"name": tex_file, "type": "tex", "children": [], "depth": 0}

    # Normalize the file path
    try:
        if not tex_file.endswith(".tex"):
            for ext in [".tex", ""]:
                test_path = tex_file + ext
                if os.path.exists(os.path.join(global_base_dir, test_path)):
                    tex_file = test_path
                    break
    except Exception as e:
        logger.error(f"Error normalizing path {tex_file}: {e}")
        return dependencies, included_graphics, cited_keys, dep_tree

    full_path = os.path.join(global_base_dir, tex_file)

    if not os.path.exists(full_path):
        logger.warning(f"File not found: {full_path}")
        return dependencies, included_graphics, cited_keys, dep_tree

    # Avoid processing the same file twice
    if tex_file in dependencies:
        return dependencies, included_graphics, cited_keys, dep_tree

    # Add this file to dependencies
    dependencies.add(tex_file)

    if verbose:
        logger.info(f"Processing: {tex_file}")

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()

        # First, remove comments to ensure we only process non-commented commands
        content_without_comments = re.sub(
            r"(?<!\\)%.*?$", "", content, flags=re.MULTILINE
        )

        # Also remove comment environments
        content_without_comments = re.sub(
            r"\\begin\{comment\}.*?\\end\{comment\}",
            "",
            content_without_comments,
            flags=re.DOTALL,
        )

        current_node = {
            "name": tex_file,
            "type": "tex",
            "children": [],
            "depth": current_depth,
        }

        # Find all \input, \include, \subfile commands in non-commented text
        for match in INPUT_PATTERN.finditer(content_without_comments):
            input_path = match.group(1).strip()
            input_dir = os.path.dirname(tex_file)
            logger.debug(f"input_path: {input_path}, input_dir: {input_dir}")

            if verbose:
                logger.info(f"++ Found recursive input: {input_path}")

            # Recursively find dependencies in the included file
            dependencies, included_graphics, cited_keys, child_tree = find_dependencies(
                input_path,
                global_base_dir,
                dependencies,
                included_graphics,
                cited_keys,
                verbose,
                dep_tree=None,
                current_depth=current_depth + 1,
            )
            if child_tree:
                current_node["children"].append(child_tree)

        # Find bibliography files
        for match in BIBLIOGRAPHY_PATTERN.finditer(content_without_comments):
            bib_files = match.group(1).split(",")
            for bib_file in bib_files:
                bib_file = bib_file.strip()
                if not bib_file.endswith(".bib"):
                    bib_file += ".bib"
                bib_path = os.path.join(os.path.dirname(tex_file), bib_file)
                dependencies.add(bib_path)
                if verbose:
                    logger.info(f"Found bibliography: {bib_path}")

        # Find bibliography style files
        for match in BIBLIOGRAPHYSTYLE_PATTERN.finditer(content_without_comments):
            bst_file = match.group(1).strip()
            if not bst_file.endswith(".bst"):
                bst_file += ".bst"
            bst_path = os.path.join(os.path.dirname(tex_file), bst_file)
            dependencies.add(bst_path)
            if verbose:
                logger.info(f"Found bibliography style: {bst_path}")

        # Find all citations in non-commented text
        for match in CITATION_PATTERN.finditer(content_without_comments):
            # Citations can be comma-separated
            keys = match.group(1).split(",")
            for key in keys:
                key_clean = key.strip()
                cited_keys.add(key_clean)
                if verbose:
                    logger.info(f"Found citation key: {key_clean}")

        # Find all graphics in non-commented text
        for match in GRAPHICS_PATTERN.finditer(content_without_comments):
            graphics_path = match.group(1).strip()

            # Handle path without extension (LaTeX can omit the extension)
            # the graphics_path is relative to the tex_file
            base_graphics_path = graphics_path

            if verbose:
                logger.info(f"Found graphics: {base_graphics_path}")

            # Try common image extensions if no extension is provided
            extensions = [
                "",
                ".pdf",
                ".png",
                ".jpg",
                ".jpeg",
                ".eps",
                ".ps",
                ".tif",
                ".tiff",
            ]
            found = False

            for ext in extensions:
                test_path = base_graphics_path + ext
                if os.path.exists(os.path.join(global_base_dir, test_path)):
                    included_graphics.add(test_path)
                    # Add graphics file to dependency tree
                    current_node["children"].append(
                        {
                            "name": test_path,
                            "type": "graphics",
                            "children": [],
                            "depth": current_depth + 1,
                        }
                    )
                    found = True
                    if verbose:
                        logger.info(f"{base_graphics_path} Resolved to: {test_path}")
                    break

            if not found:
                logger.warning(f"Image not found: {base_graphics_path}")

        return dependencies, included_graphics, cited_keys, current_node

    except Exception as e:
        logger.error(f"Error processing {tex_file}: {e}")
        return dependencies, included_graphics, cited_keys, None


def remove_comments(content):
    """
    Remove comments from LaTeX files in a straightforward way.

    This function:
    1. Removes full-line comments
    2. Removes inline comments
    3. Preserves original line structure and spacing
    """
    result = []
    lines = content.splitlines(True)

    for line in lines:
        # skip the whole line comment
        stripped = line.lstrip()
        if stripped and stripped[0] == "%":
            continue

        # process the inline comment
        comment_pos = -1
        i = 0
        while i < len(line):
            if line[i] == "%":
                # ensure it is not an escaped \%
                if i == 0 or line[i - 1] != "\\":
                    comment_pos = i
                    break
            i += 1

        # add the line without comments
        if comment_pos != -1:
            # keep the part before the comment
            result.append(line[:comment_pos])
            # if the line ends with a newline, add a newline
            if line.endswith("\n"):
                result.append("\n")
        else:
            result.append(line)

    # join all lines
    text = "".join(result)

    # clean: remove consecutive 3+ empty lines
    text = re.sub(r"\n\s*\n\s*\n\s*\n+", "\n\n\n", text)

    # ensure the file ends with a newline
    if text and not text.endswith("\n"):
        text += "\n"

    return text


def filter_bib_file(src_path, dest_path, cited_keys):
    """Copy only the cited entries from a BIB file, preserving formatting."""
    try:
        with open(src_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Remove comments while preserving formatting
        content = re.sub(r"(?<!\\)%.*?$", "", content, flags=re.MULTILINE)

        # If there are no citation keys or \nocite{*} is used, keep all entries but delete comments
        if not cited_keys or "*" in cited_keys:
            logger.warning(f"Keeping all entries in {os.path.basename(src_path)}")
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(content)
            return

        # Find all BibTeX entries
        entries = []
        entry_positions = []

        for match in BIBENTRY_PATTERN.finditer(content):
            entry_text = match.group(0)
            entry_key = match.group(1).strip()
            start, end = match.span()

            # Record entry position and content
            if entry_key in cited_keys:
                entries.append(entry_text)
                entry_positions.append((start, end, entry_key))

        # If there are no matching entries, keep all
        if not entries:
            logger.warning(
                f"No matching entries found in {os.path.basename(src_path)}. Keeping all."
            )
            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(content)
            return

        # Sort entry positions by original order
        entry_positions.sort()

        # Rebuild the BIB file, preserving whitespace and formatting between entries
        filtered_content = ""
        for i, (start, end, key) in enumerate(entry_positions):
            entry_text = content[start:end]

            # Add a prefix newline for each entry (except the first one)
            if i > 0:
                # Ensure there is a newline between entries
                filtered_content += "\n\n"

            filtered_content += entry_text

        # Ensure the file ends with a newline
        if not filtered_content.endswith("\n"):
            filtered_content += "\n"

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(filtered_content)

        logger.info(
            f"Filtered BIB file: {os.path.basename(src_path)} - Kept {len(entries)} entries"
        )

    except Exception as e:
        logger.error(f"Error filtering BIB file {src_path}: {e}")
        # Directly copy the file if there's an error
        shutil.copy2(src_path, dest_path)


def copy_clean_file(src_path, dest_path, cited_keys=None):
    """Copy a file while removing comments if it's a TeX file, or filtering if it's a BIB file."""
    # Create parent directories if they don't exist
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    # For BIB files, filter out unused entries
    if src_path.endswith(".bib") and cited_keys is not None:
        filter_bib_file(src_path, dest_path, cited_keys)

    # For TeX files, remove comments before copying
    elif src_path.endswith(".tex"):
        try:
            with open(src_path, "r", encoding="utf-8") as f:
                content = f.read()

            clean_content = remove_comments(content)

            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(clean_content)
        except Exception as e:
            logger.error(f"Error cleaning {src_path}: {e}")
            # Fall back to direct copy if there's an error
            shutil.copy2(src_path, dest_path)
    else:
        # For non-TeX files, just copy directly
        shutil.copy2(src_path, dest_path)


def print_dependency_tree(tree, indent=""):
    """
    Print the dependency tree.
    """
    if not tree:
        return

    # Unicode characters
    PIPE = "│   "
    ELBOW = "└── "
    TEE = "├── "

    # Get the file name instead of the full path
    name = os.path.basename(tree["name"])

    # Add different markers based on the file type
    if tree["type"] == "graphics":
        prefix = "🖼 "  # Graphics files use image emoji
    else:
        prefix = "📄 "  # TeX files use document emoji

    # Print the current node
    logger.info(f"{indent}{prefix}{name}")

    # Process child nodes
    for i, child in enumerate(tree["children"]):
        is_last = i == len(tree["children"]) - 1
        next_indent = indent + ("    " if is_last else "│   ")
        print_dependency_tree(child, next_indent)


def clean_latex_project(source_dir, output_dir, main_tex, verbose=False):
    """
    Clean a LaTeX project by copying only necessary files and removing comments.

    Args:
        source_dir: Path to the source LaTeX project
        output_dir: Path where the clean version will be created
        main_tex: Path to the main TeX file (relative to source_dir)
        verbose: Whether to print verbose information
    """
    source_dir = os.path.abspath(source_dir)
    output_dir = os.path.abspath(output_dir)

    logger.info(f"Analyzing LaTeX project starting from {main_tex}...")

    # Find all dependencies, graphics, and citations recursively from main.tex
    dependencies, included_graphics, cited_keys, dep_tree = find_dependencies(
        main_tex, source_dir, verbose=verbose
    )

    # Print dependency tree
    logger.info("\nDependency Tree:")
    logger.info("===============")
    print_dependency_tree(dep_tree)
    logger.info("===============\n")

    logger.info(f"Found {len(dependencies)} necessary TeX files")
    logger.info(f"Found {len(included_graphics)} graphics files")
    logger.info(f"Found {len(cited_keys)} citation keys")

    if verbose:
        logger.info("TEX dependencies:")
        for dep in sorted(dependencies):
            logger.info(f"  {dep}")

        logger.info("Graphics dependencies:")
        for graphic in sorted(included_graphics):
            logger.info(f"  {graphic}")

        logger.info("Citation keys:")
        for key in sorted(cited_keys):
            logger.info(f"  {key}")

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Copy all necessary files
    logger.info(f"Copying and cleaning files to {output_dir}...")

    # List of important auxiliary files to copy if they exist
    important_files = [
        "Makefile",
        "makefile",
        "latexmkrc",
        ".latexmkrc",
        "README",
        "README.md",
        "README.txt",
        "acmart.cls",
        "IEEEtran.cls",
        "llncs.cls",
        "elsarticle.cls",
        "sigconf.cls",
        "sig-alternate.cls",
        "sig-alternate-05-2015.cls",
    ]

    # Add style files that are commonly needed
    for root, _, files in os.walk(source_dir):
        for file in files:
            if file.endswith(".sty") or file.endswith(".cls") or file.endswith(".bst"):
                rel_path = os.path.relpath(os.path.join(root, file), source_dir)
                if rel_path not in dependencies:
                    dependencies.add(rel_path)
                    if verbose:
                        logger.info(f"Added style file: {rel_path}")

    # Copy TeX files and their dependencies
    for file_path in dependencies:
        src_path = os.path.join(source_dir, file_path)
        dest_path = os.path.join(output_dir, file_path)

        if os.path.exists(src_path):
            try:
                if file_path.endswith(".bib"):
                    copy_clean_file(src_path, dest_path, cited_keys)
                else:
                    copy_clean_file(src_path, dest_path)
                if verbose:
                    logger.info(f"Copied: {file_path}")
            except Exception as e:
                logger.error(f"Error copying {file_path}: {e}")
        else:
            logger.warning(f"Dependency not found: {file_path}")

    # Copy graphics files
    for file_path in included_graphics:
        src_path = os.path.join(source_dir, file_path)
        dest_path = os.path.join(output_dir, file_path)

        if os.path.exists(src_path):
            try:
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy2(src_path, dest_path)
                if verbose:
                    logger.info(f"Copied: {file_path}")
            except Exception as e:
                logger.error(f"Error copying {file_path}: {e}")
        else:
            logger.warning(f"Graphic not found: {file_path}")

    # Copy important auxiliary files
    for file in important_files:
        src_path = os.path.join(source_dir, file)
        if os.path.exists(src_path):
            dest_path = os.path.join(output_dir, file)
            try:
                shutil.copy2(src_path, dest_path)
                if verbose:
                    logger.info(f"Copied important file: {file}")
            except Exception as e:
                logger.error(f"Error copying important file {file}: {e}")

    logger.info(f"Cleaning complete! Clean version saved to {output_dir}")


def find_main_tex_file(source_dir):
    """Try to automatically find the main TeX file in the source directory."""
    logger.info("Trying to automatically find the main TeX file...")

    # Find possible main TeX files
    tex_files = []
    for root, _, files in os.walk(source_dir):
        for file in files:
            if file.endswith(".tex"):
                tex_files.append(os.path.relpath(os.path.join(root, file), source_dir))

    # Check file content to find \documentclass command
    main_candidates = []
    for tex_file in tex_files:
        try:
            with open(os.path.join(source_dir, tex_file), "r", encoding="utf-8") as f:
                content = f.read()
                if r"\documentclass" in content:
                    main_candidates.append(tex_file)
        except Exception:
            continue

    if not main_candidates:
        logger.error(
            "Could not automatically find a main TeX file. Please specify with --main_tex."
        )
        return None

    if len(main_candidates) == 1:
        logger.info(f"Found main TeX file: {main_candidates[0]}")
        return main_candidates[0]

    # If there are multiple candidates, try to find a file named main.tex or the same as the directory
    dir_name = os.path.basename(os.path.normpath(source_dir))
    for candidate in main_candidates:
        base_name = os.path.basename(candidate)
        if base_name.lower() == "main.tex" or base_name.lower() == f"{dir_name}.tex":
            logger.info(f"Selected main TeX file: {candidate}")
            return candidate

    logger.warning(f"Multiple potential main TeX files found: {main_candidates}")
    logger.warning(f"Using the first one: {main_candidates[0]}")
    return main_candidates[0]


def main():
    """Parse arguments and run the cleaner."""
    parser = argparse.ArgumentParser(
        description="Clean LaTeX project for arXiv/Camera-ready submission"
    )
    parser.add_argument(
        "--source_dir", "-s", required=True, help="Source LaTeX project directory"
    )
    parser.add_argument(
        "--output_dir",
        "-o",
        default="./cleaned_project",
        help="Output directory for cleaned project",
    )
    parser.add_argument(
        "--main_tex", "-m", help="Main TeX file (relative to source_dir)"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output (print all dependencies)",
    )

    args = parser.parse_args()

    # try to automatically find the main TeX file
    main_tex = args.main_tex
    if not main_tex:
        main_tex = find_main_tex_file(args.source_dir)
        if not main_tex:
            parser.print_help()
            exit(1)

    global global_base_dir
    global_base_dir = args.source_dir
    clean_latex_project(
        args.source_dir, args.output_dir, main_tex, verbose=args.verbose
    )


if __name__ == "__main__":
    main()
