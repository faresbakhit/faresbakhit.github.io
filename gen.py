#!/usr/bin/env python

import os
import re
import sys
import json
from typing import IO, NoReturn, cast, Any
from string import Template
from collections.abc import Mapping, Callable

ROOT_DIR_PATH = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR_PATH = os.path.join(ROOT_DIR_PATH, "docs/")
PAGES_DIR_PATH = os.path.join(ROOT_DIR_PATH, "pages/")
TEMPLATES_DIR_PATH = os.path.join(ROOT_DIR_PATH, "templates/")

OSMKDIR_MODE = 0o755
NEWLINE = "\n"
TEXT_ENCODING = "utf-8"


def error(msg: str, *args: object, prefix: str = "error: ") -> NoReturn:
    print(
        prefix + msg,
        *map(lambda obj: " "*len(prefix) + str(obj), args),
        file=sys.stderr,
        sep=NEWLINE,
    )
    sys.exit(1)


def minify_css(css: str) -> str:
    """source: https://stackoverflow.com/a/223689"""

    # remove comments - this will break a lot of hacks :-P
    css = re.sub(r'\s*/\*\s*\*/', "$$HACK1$$", css) # preserve IE<6 comment hack
    css = re.sub(r'/\*[\s\S]*?\*/', "", css)
    css = css.replace("$$HACK1$$", '/**/') # preserve IE<6 comment hack

    # url() doesn't need quotes
    css = re.sub(r'url\((["\'])([^)]*)\1\)', r'url(\2)', css)

    # spaces may be safely collapsed as generated content will collapse them anyway
    css = re.sub(r'\s+', ' ', css)

    # shorten collapsable colors: #aabbcc to #abc
    css = re.sub(r'#([0-9a-f])\1([0-9a-f])\2([0-9a-f])\3(\s|;)', r'#\1\2\3\4', css)

    # fragment values can loose zeros
    css = re.sub(r':\s*0(\.\d+([cm]m|e[mx]|in|p[ctx]))\s*;', r':\1;', css)

    out = ""
    for rule in re.findall(r'([^{]+){([^}]*)}', css):

        # we don't need spaces around operators
        selectors = [re.sub(r'(?<=[\[\(>+=])\s+|\s+(?=[=~^$*|>+\]\)])', r'', selector.strip()) for selector in rule[0].split(',')]

        # order is important, but we still want to discard repetitions
        properties = {}
        porder: list[Any] = []
        for prop in re.findall('(.*?):(.*?)(;|$)', rule[1]):
            key = prop[0].strip().lower()
            if key not in porder:
                porder.append(key)
            properties[key] = prop[1].strip()

        # output rule if it contains any declarations
        if properties:
            out += "%s{%s}" % (','.join(selectors), ''.join(['%s:%s;' % (key, properties[key]) for key in porder])[:-1])

    return out


def collect_json_object(fp: IO[bytes]) -> tuple[bytes, bool]:
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
    print(f"load({filepath!r})")

    with open(filepath, "rb") as fp:
        json_object_s, has_object_start = collect_json_object(fp)
        json_object = {}
        file_content = b""
        if has_object_start:
            try:
                json_object = json.loads(json_object_s)
            except json.JSONDecodeError as exc:
                rel_filepath = os.path.relpath(filepath, ".")
                error(f"./{rel_filepath}:{exc.lineno}:{exc.colno}: {exc.msg}")
            json_object = cast(dict[str, Any], json_object)
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
        includes = cast(Mapping[str, Any], includes)
        for key, filepath in includes.items():
            application = None
            if isinstance(filepath, Mapping):
                application = filepath["apply"]
                filepath = filepath["path"]
            if not os.path.isabs(filepath):
                filepath = os.path.join(ROOT_DIR_PATH, filepath)
            print(f"include({filepath!r})")
            with open(filepath, encoding=TEXT_ENCODING, newline=NEWLINE) as fp:
                s = fp.read()
            if application is not None:
                if application == "css-minify":
                    s = minify_css(s)
            json_object[key] = s

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
            print(f"rm({path!r})")
            rm(path)


def main() -> None:
    if not os.path.exists(OUTPUT_DIR_PATH):
        print(f"mkdir({OUTPUT_DIR_PATH!r})")
        os.mkdir(OUTPUT_DIR_PATH, mode=OSMKDIR_MODE)

    for dirpath, dirnames, filenames in os.walk(PAGES_DIR_PATH):
        reldirpath = os.path.relpath(dirpath, PAGES_DIR_PATH)
        for dirname in dirnames:
            tomkdir = os.path.join(OUTPUT_DIR_PATH, reldirpath, dirname)
            if not os.path.exists(tomkdir):
                print(f"mkdir({tomkdir!r})")
                os.mkdir(tomkdir, mode=OSMKDIR_MODE)

        for filename in filenames:
            filepath = os.path.join(dirpath, filename)

            try:
                template_s = load_template_s(filepath)
            except OSError as exc:
                rel_filepath = os.path.relpath(filepath, ".")
                error(f"./{rel_filepath}: {exc.filename}: {exc.strerror}")

            output_filepath = os.path.join(
                OUTPUT_DIR_PATH,
                os.path.relpath(filepath, PAGES_DIR_PATH),
            )
            with open(output_filepath, "wb") as fp:
                print(f"write({output_filepath!r})")
                fp.write(template_s)

    for dirpath, dirnames, filenames in os.walk(OUTPUT_DIR_PATH, topdown=False):
        rm_missing_pages(dirpath, filenames, os.remove)
        rm_missing_pages(dirpath, dirnames, os.rmdir)


if __name__ == "__main__":
    main()
