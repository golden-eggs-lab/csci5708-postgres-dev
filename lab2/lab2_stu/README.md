# CSCI 5708 — Lab 2: B-tree Index Instrumentation

**Architecture and Implementation of Database Management Systems**

**Instructor:** Chang Ge (cge@umn.edu)

**Due date:** April 1 @ 11:59 PM CT

---

## Overview

You will instrument PostgreSQL's B-tree index to collect three runtime counters:

| Counter | What it counts |
|---|---|
| `bt_internal_visits` | Internal (non-leaf) pages visited during tree descent |
| `bt_leaf_visits` | Leaf pages visited during tree descent |
| `bt_splits` | Page splits during insertion |

A GUC (runtime configuration) variable `btree_lab.enable_stats` toggles collection on/off. When enabled, each insert or scan prints one stats line via `elog(INFO, ...)`.

You will modify **three files** in `src/backend/access/nbtree/`:

- **`nbtsearch.c`** — define counters, increment them during tree descent
- **`nbtinsert.c`** — increment split counter when a page splits
- **`nbtree.c`** — register the GUC, reset/print counters in `btinsert`, `btbeginscan`, `btendscan`

---

## Background

A B-tree index has **internal pages** (for navigation) and **leaf pages** (where index entries live). To find a key, PostgreSQL descends from root through internal pages to a leaf. When a page overflows during insertion, it **splits** into two.

The key function for tree descent is `_bt_search()` in `nbtsearch.c`. It loops through pages top-to-bottom. Inside the loop, `P_ISLEAF(opaque)` tells you whether the current page is a leaf.

Page splits happen in `_bt_insertonpg()` in `nbtinsert.c`, which calls `_bt_split()` when a page is full.

The top-level entry points in `nbtree.c` are:
- `btinsert()` — called for each INSERT
- `btbeginscan()` — called when a SELECT starts scanning an index
- `btendscan()` — called when the scan finishes

---

## Output Format

Use this exact `elog` call — the autograder parses this format:

```c
elog(INFO, "BTREE_LAB_STATS: internal=%d leaf=%d splits=%d",
     bt_internal_visits, bt_leaf_visits, bt_splits);
```

**Print this** in `btinsert()` (after the insert) and `btendscan()` (before resetting), only when `btree_lab_stats` is true.

Example output in psql:
```
INFO:  BTREE_LAB_STATS: internal=1 leaf=1 splits=0
```

---

## Your Task

### File 1: `nbtsearch.c` — 2 TODOs

**TODO 1** — Near the top, define four file-scope (non-static) variables:
- `bool btree_lab_stats = false;` — the GUC flag
- `int bt_internal_visits = 0;`
- `int bt_leaf_visits = 0;`
- `int bt_splits = 0;`

These must be non-static so other files can `extern` them.

**TODO 2** — In `_bt_search()`, inside the descent loop:
- Part A: When `P_ISLEAF(opaque)` is true → increment `bt_leaf_visits` (if stats enabled)
- Part B: Otherwise (internal page) → increment `bt_internal_visits` (if stats enabled)

### File 2: `nbtinsert.c` — 2 TODOs

**TODO 1** — Add `extern` declarations for `btree_lab_stats` and `bt_splits`.

**TODO 2** — After `_bt_split()` is called in `_bt_insertonpg()`, increment `bt_splits` (if stats enabled).

### File 3: `nbtree.c` — 3 TODOs

**TODO 1** — At the top:
- Add `#include "utils/guc.h"`
- Add `extern` declarations for all four variables
- Implement `_bt_lab_register_guc()`:

```c
static bool guc_registered = false;

static void
_bt_lab_register_guc(void)
{
    if (guc_registered)
        return;
    guc_registered = true;

    DefineCustomBoolVariable(
        "btree_lab.enable_stats",
        "Enable B-tree lab statistics",
        NULL,
        &btree_lab_stats,   /* pointer to your bool flag */
        false,               /* default OFF */
        PGC_USERSET,
        0,
        NULL, NULL, NULL
    );

    MarkGUCPrefixReserved("btree_lab");
}
```

**TODO 2** — In `btinsert()`:
1. Call `_bt_lab_register_guc()`
2. Reset all three counters to 0
3. *(existing `_bt_doinsert()` call — don't touch)*
4. If stats enabled, print with `elog(INFO, ...)`

**TODO 3** — In scan functions:
- Part A (`btbeginscan`): register GUC, reset counters to 0
- Part B (`btendscan`): if stats enabled print with `elog(INFO, ...)`; then reset counters to 0

---

## Compiling and Testing

```bash
# Copy your files into the source tree
cp nbtsearch.c nbtinsert.c nbtree.c /work/.pg/postgres/src/backend/access/nbtree/

# Build
cd /work/.pg/postgres && make -j$(nproc) && make install

# Restart server
pg_ctl -D /work/.pg/data stop 2>/dev/null; pg_ctl -D /work/.pg/data -l /tmp/pg.log start
```

Test in psql:
```sql
CREATE TABLE test(k int);
CREATE INDEX idx ON test(k);

SET btree_lab.enable_stats = on;
INSERT INTO test SELECT generate_series(1, 1000);
-- You should see stats lines for each insert

SELECT * FROM test WHERE k = 500;
-- INFO:  BTREE_LAB_STATS: internal=1 leaf=1 splits=0

SET btree_lab.enable_stats = off;
SELECT * FROM test WHERE k = 500;
-- No output (stats disabled)
```

---

## Submission

Upload **three files** to Gradescope: `nbtsearch.c`, `nbtinsert.c`, `nbtree.c`.
