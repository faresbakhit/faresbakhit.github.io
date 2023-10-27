#!/usr/bin/env python

import os
import sys
import json
from typing import IO, NoReturn
from string import Template
from collections.abc import Mapping, Callable

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(ROOT_DIR, "docs/")
PAGES_DIR = os.path.join(ROOT_DIR, "pages/")
TEMPLATES_DIR = os.path.join(ROOT_DIR, "templates/")
MKDIR_MODE = 0o755
OPEN_FILE_KWARGS = {"encoding": "utf-8", "newline": "\n"}
READ_FILE_KWARGS = {"mode": "rt", **OPEN_FILE_KWARGS}


def error(*args: object) -> NoReturn:
    print("error:", *args, file=sys.stderr)
    sys.exit(1)


def collect_json_object(fp: IO[str]) -> tuple[str, bool]:
    object_buf = "{"
    open_ldels = 1
    test_char = fp.read(1)
    if test_char != "{":
        return test_char, False
    for line in fp:
        object_buf += line
        open_ldels += line.count("{")
        open_ldels -= line.count("}")
        if open_ldels <= 0:
            break
    fp.read(1)
    return object_buf, True


def load_template_s(filepath: str) -> str:
    print(f"load({filepath!r})")

    with open(filepath, **READ_FILE_KWARGS) as fp:
        json_object_s, exists = collect_json_object(fp)
        json_object = {}
        file_text = ""
        if exists:
            try:
                json_object = json.loads(json_object_s)
            except json.JSONDecodeError as exc:
                rel_filepath = os.path.relpath(filepath, ".")
                error("./{rel_filepath}:{exc.lineno}:{exc.colno}: {exc.msg}")
        else:
            file_text += json_object_s
        file_text += fp.read()

    template_filename = json_object.get("extends")
    if template_filename is None:
        template = Template(file_text)
    else:
        template_filepath = os.path.join(TEMPLATES_DIR, template_filename)
        template = Template(load_template_s(template_filepath))
        json_object["expanding"] = file_text

    includes = json_object.get("includes")
    if isinstance(includes, Mapping):
        for key, filepath in includes.items():
            if not os.path.isabs(filepath):
                filepath = os.path.join(ROOT_DIR, filepath)
            print(f"include({filepath!r})")
            with open(filepath, **READ_FILE_KWARGS) as fp:
                json_object[key] = fp.read()

    return template.safe_substitute(json_object)


def rm_missing_page_output(
    dirpath: str,
    basenames: list[str],
    rm: Callable[[str], None],
) -> None:
    for basename in basenames:
        path = os.path.join(dirpath, basename)
        page_path = os.path.join(PAGES_DIR, os.path.relpath(path, OUTPUT_DIR))
        if not os.path.exists(page_path):
            print(f"rm({path!r})")
            rm(path)


def main() -> None:
    if not os.path.exists(OUTPUT_DIR):
        print(f"mkdir({OUTPUT_DIR!r})")
        os.mkdir(OUTPUT_DIR, mode=MKDIR_MODE)

    for dirpath, dirnames, filenames in os.walk(PAGES_DIR):
        for dirname in dirnames:
            tomkdir = os.path.join(
                OUTPUT_DIR,
                os.path.relpath(dirpath, PAGES_DIR),
                dirname,
            )
            if not os.path.exists(tomkdir):
                print(f"mkdir({tomkdir!r})")
                os.mkdir(tomkdir, mode=MKDIR_MODE)

        for filename in filenames:
            filepath = os.path.join(dirpath, filename)

            try:
                template_s = load_template_s(filepath)
            except OSError as exc:
                rel_filepath = os.path.relpath(filepath, ".")
                error("./{rel_filepath}: {exc.filename}: {exc.strerror}")

            output_filepath = os.path.join(
                OUTPUT_DIR,
                os.path.relpath(filepath, PAGES_DIR),
            )
            with open(output_filepath, "w", **OPEN_FILE_KWARGS) as fp:
                print(f"write({output_filepath!r})")
                fp.write(template_s)

    for dirpath, dirnames, filenames in os.walk(OUTPUT_DIR, topdown=False):
        rm_missing_page_output(dirpath, filenames, os.remove)
        rm_missing_page_output(dirpath, dirnames, os.rmdir)


if __name__ == "__main__":
    main()
