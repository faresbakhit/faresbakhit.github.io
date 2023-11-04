#!/usr/bin/env python

import os
import sys
import json
from typing import IO, NoReturn
from string import Template
from collections.abc import Mapping, Callable

ROOT_DIR_PATH = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR_PATH = os.path.join(ROOT_DIR_PATH, "docs/")
PAGES_DIR_PATH = os.path.join(ROOT_DIR_PATH, "pages/")
TEMPLATES_DIR_PATH = os.path.join(ROOT_DIR_PATH, "templates/")

OSMKDIR_MODE = 0o755
NEWLINE = "\n"
TEXT_ENCODING = "utf-8"

if os.getenv("GENPY_NO_LOG") is None:
    log = print
else:

    def log(*args, **kwargs) -> None:
        pass


def error(msg: str, *args: object, prefix: str = "error: ") -> NoReturn:
    """print the arguments to stderr and exit with status code 1"""
    indent = lambda o: len(prefix) * " " + str(o)
    print(
        prefix + msg,
        *map(indent, args),
        file=sys.stderr,
        sep=NEWLINE,
    )
    sys.exit(1)


def collect_json_object(fp: IO[bytes]) -> tuple[str, bool]:
    """Returns the read string and if the file has a JSON object start"""
    object_buf = b"{"
    open_ldels = 1
    test_char = fp.read(1)
    if test_char != b"{":
        return test_char, False
    for line in fp:
        object_buf += line
        open_ldels += line.count(b"{")
        open_ldels -= line.count(b"}")
        if open_ldels <= 0:
            break
    fp.read(1)
    return object_buf, True


def load_template_s(filepath: str) -> bytes:
    log(f"load({filepath!r})")

    with open(filepath, "rb") as fp:
        json_object_s, has_object_start = collect_json_object(fp)
        json_object = {}
        file_content = b""
        if has_object_start:
            try:
                json_object = json.loads(json_object_s)
            except json.JSONDecodeError as exc:
                rel_filepath = os.path.relpath(filepath, ".")
                error("./{rel_filepath}:{exc.lineno}:{exc.colno}: {exc.msg}")
        else:
            file_content += json_object_s
        file_content += fp.read()

    try:
        file_text = file_content.decode(TEXT_ENCODING)
    except ValueError:
        return file_content

    template_filename = json_object.get("extends")
    if template_filename is None:
        template = Template(file_text)
    else:
        template_filepath = os.path.join(TEMPLATES_DIR_PATH, template_filename)
        template = Template(load_template_s(template_filepath).decode(TEXT_ENCODING))
        json_object["expanding"] = file_text

    includes = json_object.get("includes")
    if isinstance(includes, Mapping):
        for key, filepath in includes.items():
            if not os.path.isabs(filepath):
                filepath = os.path.join(ROOT_DIR_PATH, filepath)
            log(f"include({filepath!r})")
            with open(filepath, encoding=TEXT_ENCODING, newline=NEWLINE) as fp:
                json_object[key] = fp.read()

    return template.safe_substitute(json_object).encode(TEXT_ENCODING)


def rm_missing_pages(
    dirpath: str,
    basenames: list[str],
    rm: Callable[[str], None],
) -> None:
    for basename in basenames:
        path = os.path.join(dirpath, basename)
        page_path = os.path.join(
            PAGES_DIR_PATH,
            os.path.relpath(path, OUTPUT_DIR_PATH),
        )
        if not os.path.exists(page_path):
            log(f"rm({path!r})")
            rm(path)


def main() -> None:
    if not os.path.exists(OUTPUT_DIR_PATH):
        log(f"mkdir({OUTPUT_DIR_PATH!r})")
        os.mkdir(OUTPUT_DIR_PATH, mode=OSMKDIR_MODE)

    for dirpath, dirnames, filenames in os.walk(PAGES_DIR_PATH):
        reldirpath = os.path.relpath(dirpath, PAGES_DIR_PATH)
        for dirname in dirnames:
            tomkdir = os.path.join(OUTPUT_DIR_PATH, reldirpath, dirname)
            if not os.path.exists(tomkdir):
                log(f"mkdir({tomkdir!r})")
                os.mkdir(tomkdir, mode=OSMKDIR_MODE)

        for filename in filenames:
            filepath = os.path.join(dirpath, filename)

            try:
                template_s = load_template_s(filepath)
            except OSError as exc:
                rel_filepath = os.path.relpath(filepath, ".")
                error("./{rel_filepath}: {exc.filename}: {exc.strerror}")

            output_filepath = os.path.join(
                OUTPUT_DIR_PATH,
                os.path.relpath(filepath, PAGES_DIR_PATH),
            )
            with open(output_filepath, "wb") as fp:
                log(f"write({output_filepath!r})")
                fp.write(template_s)

    for dirpath, dirnames, filenames in os.walk(OUTPUT_DIR_PATH, topdown=False):
        rm_missing_pages(dirpath, filenames, os.remove)
        rm_missing_pages(dirpath, dirnames, os.rmdir)


if __name__ == "__main__":
    main()
