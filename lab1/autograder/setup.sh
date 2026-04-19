#!/usr/bin/env bash
# =============================================================================
# Gradescope Autograder — setup.sh
# CSCI 5708 Lab: 2nd-LRU Buffer Replacement
#
# This script runs ONCE when the autograder Docker image is built.
# It installs all dependencies and pre-compiles PostgreSQL so that
# run_autograder only needs to swap in the student's freelist.c,
# do an incremental make, and run the test.
# =============================================================================
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

echo "=== [setup.sh] Installing build dependencies ==="
apt-get update -qq
apt-get install -y -qq locales > /dev/null
locale-gen en_US.UTF-8 > /dev/null 2>&1 || true
apt-get install -y -qq \
    build-essential \
    libreadline-dev \
    zlib1g-dev \
    flex \
    bison \
    python3 \
    python3-pip \
    git \
    pkg-config \
    libicu-dev \
    > /dev/null

# ---------------------------------------------------------------------------
# 1. Clone PostgreSQL source (REL_18_STABLE)
# ---------------------------------------------------------------------------
PG_SRC=/autograder/source/pg_src
PG_INSTALL=/autograder/source/pg_install

echo "=== [setup.sh] Cloning PostgreSQL REL_18_STABLE ==="
if [ ! -d "$PG_SRC" ]; then
    git clone --depth 1 --branch REL_18_STABLE \
        https://github.com/postgres/postgres.git "$PG_SRC"
fi

# ---------------------------------------------------------------------------
# 2. Apply the provided source modifications (buf_internals.h, buf_init.c, bufmgr.c)
# ---------------------------------------------------------------------------
echo "=== [setup.sh] Applying provided source modifications ==="
SRC_DIR=/autograder/source

cp "$SRC_DIR/buf_internals.h" "$PG_SRC/src/include/storage/buf_internals.h"
cp "$SRC_DIR/buf_init.c"      "$PG_SRC/src/backend/storage/buffer/buf_init.c"
cp "$SRC_DIR/bufmgr.c"        "$PG_SRC/src/backend/storage/buffer/bufmgr.c"

# ---------------------------------------------------------------------------
# 3. Configure & compile PostgreSQL
#    We use the reference freelist.c (solution) for the initial build so that
#    all object files except freelist.o are pre-compiled. During grading we
#    only swap freelist.c -> incremental make.
# ---------------------------------------------------------------------------
echo "=== [setup.sh] Configuring PostgreSQL ==="
cd "$PG_SRC"

# Copy the reference solution for the initial build
cp "$SRC_DIR/freelist_solution.c" "$PG_SRC/src/backend/storage/buffer/freelist.c"

./configure --prefix="$PG_INSTALL" \
    --enable-debug --enable-cassert \
    CFLAGS="-O0 -g3" \
    > /dev/null 2>&1

echo "=== [setup.sh] Compiling PostgreSQL (this may take a few minutes) ==="
make -j"$(nproc)" > /dev/null 2>&1
make install > /dev/null 2>&1

echo "=== [setup.sh] Setup complete ==="
