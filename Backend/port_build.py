#!/usr/bin/env python3
"""Stage 2 (independent of the generator): port generated headers into the target
source tree and trigger the build.

Only the Python standard library is used, and nothing here knows how the headers
are generated - it just needs the paths of the files.

Functions (the future GUI buttons call these directly):
    prepare_dir(path)               -> (abs_path, error)   check/create a folder
    port_headers(files, dst_dir)    -> (copied, backups)   copy headers into dst_dir
    run_build(build_dir, log=print) -> bool                run `cmake ..` and `make`

Command line:
    python3 port_build.py generated/general.h generated/cheri_utils.h \\
            --dst ~/sim/include --build-dir ~/sim/build
"""
import argparse
import os
import shutil
import subprocess
import sys


#Sayak: folder level handling (used by the generator for its output folder and by the porting step)
def prepare_dir(path):
    """Expand ~ and relative paths and create the folder if needed. Returns (abs_path, error_or_None)."""
    d = os.path.abspath(os.path.expanduser(path))
    try:
        os.makedirs(d, exist_ok=True)
    except OSError as e:
        return d, e.strerror or str(e)
    if not os.access(d, os.W_OK):
        return d, "directory is not writable"
    return d, None


def port_to(pairs, backup=True):
    """Copy each (source_file, target_folder) pair; target folders are created if missing.

    An existing file with the same name is first saved as <name>.bak when backup is True.
    Everything is checked before the first copy, so a bad path never leaves a half-ported tree.
    Returns (copied_paths, backup_paths). Raises OSError with a readable message.
    """
    plan = []
    for f, d in pairs:
        f = os.path.abspath(os.path.expanduser(f))
        if not os.path.isfile(f):
            raise FileNotFoundError(f"generated file not found: {f}")
        dst, err = prepare_dir(d)
        if err:
            raise OSError(f"cannot use target directory '{dst}': {err}")
        if os.path.dirname(f) == dst:
            raise OSError(f"source and target folder are the same: {dst}")
        plan.append((f, os.path.join(dst, os.path.basename(f))))
    copied, backups = [], []
    for f, target in plan:
        if backup and os.path.exists(target):
            shutil.copy2(target, target + ".bak")
            backups.append(target + ".bak")
        shutil.copy2(f, target)
        copied.append(target)
    return copied, backups


def port_headers(files, dst_dir, backup=True):
    """All files into one folder (wrapper around port_to)."""
    return port_to([(f, dst_dir) for f in files], backup)

#Sayak : added function for building the project for that we need to port the generated headers into the source tree and then build the project using cmake and make.
def run_build(build_dir, cmake_args=(), target=None, jobs=None, log=print):
    """Run `cmake ..` and then `make` inside build_dir (created if missing).

    Every output line is passed to log(), so a terminal can use print and a GUI can append
    to a text widget. Stops at the first failing step. Returns True if both steps succeeded.
    """
    bdir, err = prepare_dir(build_dir)
    if err:
        log(f"  -> cannot use build directory '{bdir}': {err}")
        return False
    steps = [["cmake"] + list(cmake_args) + [".."], ["make"] + [target] + ([f"-j{jobs}"] if jobs else [])]
    for cmd in steps:
        log(f"$ {' '.join(cmd)}    (in {bdir})")
        try:
            proc = subprocess.Popen(cmd, cwd=bdir, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, bufsize=1)
        except FileNotFoundError:
            log(f"  -> '{cmd[0]}' was not found; is it installed and on your PATH?")
            return False
        for line in proc.stdout:
            log(line.rstrip("\n"))
        if proc.wait() != 0:
            log(f"  -> '{' '.join(cmd)}' failed with exit code {proc.returncode}")
            return False
    return True


def main():
    ap = argparse.ArgumentParser(description="Port generated CHERI headers into a source tree and (optionally) build.")
    ap.add_argument("files", nargs="+", help="generated header files, e.g. generated/general.h generated/cheri_utils.h")
    ap.add_argument("--dst", required=True, help="target folder in the source tree (created if missing)")
    ap.add_argument("--no-backup", action="store_true", help="overwrite existing files without saving a .bak copy")
    ap.add_argument("--build-dir", default=None, help="if given, run 'cmake ..' and 'make' in this folder after porting")
    ap.add_argument("--cmake-arg", action="append", default=[], help="extra cmake argument, e.g. --cmake-arg=-DUSE_QEMU=ON (repeatable)")
    ap.add_argument("-j", "--jobs", type=int, default=None, help="parallel jobs for make")
    args = ap.parse_args()

    try:
        copied, backups = port_headers(args.files, args.dst, backup=not args.no_backup)
    except (OSError, FileNotFoundError) as e:
        sys.exit(f"Port failed: {e}")
    for c in copied:
        print(f"Ported {c}")
    for b in backups:
        print(f"  (previous version saved as {b})")

    if args.build_dir:
        if not run_build(args.build_dir, args.cmake_arg, target="all", jobs=args.jobs):
            sys.exit("Build failed")
        print("Build finished")


if __name__ == "__main__":
    sys.exit(main())
