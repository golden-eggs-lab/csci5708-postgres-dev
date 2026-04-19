#!/usr/bin/env bash
# =============================================================================
# Gradescope Autograder — setup.sh
# CSCI 5708 Lab 3: DML Operation Logging
#
# Runs ONCE when the autograder Docker image is built.
# Pre-compiles PostgreSQL with the solution file so that run_autograder
# only needs to swap in the student file + incremental make.
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
# 2. Copy the solution file for the initial build
# ---------------------------------------------------------------------------
echo "=== [setup.sh] Installing solution file ==="
SRC_DIR=/autograder/source

cp "$SRC_DIR/nodeModifyTable_solution.c" \
   "$PG_SRC/src/backend/executor/nodeModifyTable.c"

# ---------------------------------------------------------------------------
# 3. Configure & compile PostgreSQL
# ---------------------------------------------------------------------------
echo "=== [setup.sh] Configuring PostgreSQL ==="
cd "$PG_SRC"

./configure --prefix="$PG_INSTALL" \
    --enable-debug --enable-cassert \
    CFLAGS="-O0 -g3" \
    > /dev/null 2>&1

echo "=== [setup.sh] Compiling PostgreSQL (this may take a few minutes) ==="
make -j"$(nproc)" > /dev/null 2>&1
make install > /dev/null 2>&1

echo "=== [setup.sh] Setup complete ==="
