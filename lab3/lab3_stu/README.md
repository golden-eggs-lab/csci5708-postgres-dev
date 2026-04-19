# CSCI 5708 — Lab 3: DML Operation Logging

**Architecture and Implementation of Database Management Systems**

**Instructor:** Chang Ge (cge@umn.edu)

**Due date:** April 30 @ 11:59 PM CT

---

## Overview

You will instrument PostgreSQL's executor to log DML operations (INSERT, DELETE, UPDATE) based on the integer value of the first column.

| Operation | Condition to log | Log format |
|---|---|---|
| INSERT | 1st column is **odd** | `DML_LAB_LOG: INSERT val=%d` |
| DELETE | 1st column is **even** | `DML_LAB_LOG: DELETE val=%d` |
| UPDATE | old OR new 1st column is **divisible by 3** | `DML_LAB_LOG: UPDATE old_val=%d new_val=%d` |

A GUC variable `dml_lab.enable_logging` toggles logging on/off. All logging uses `elog(INFO, ...)`.

You will modify **one file**: `src/backend/executor/nodeModifyTable.c`

---

## Background

When PostgreSQL executes INSERT, DELETE, or UPDATE statements, the work is done by the **executor** module. The key file is `nodeModifyTable.c`, which contains these static functions:

- **`ExecInsert()`** — handles each row insertion. The variable `slot` (a `TupleTableSlot *`) holds the tuple being inserted. After `table_tuple_insert()` completes, the tuple data in `slot` is available.

- **`ExecDelete()`** — handles each row deletion. It receives a `tupleid` (an `ItemPointer`) identifying which row to delete, but does **not** receive the tuple data as a slot. To read the old tuple's column values, you must fetch it yourself.

- **`ExecUpdate()`** — handles each row update. It receives `oldSlot` (the old tuple) and `slot` (the new tuple), both as `TupleTableSlot *`.

### Reading a column from a TupleTableSlot

```c
bool    isnull;
Datum   val = slot_getattr(slot, 1, &isnull);  /* 1 = first column */

if (!isnull)
{
    int32 v = DatumGetInt32(val);
    /* use v */
}
```

`slot_getattr` is declared in `executor/tuptable.h` (included via `access/tableam.h`). `DatumGetInt32` is in `postgres.h`.

### Fetching an old tuple by tupleid (for DELETE)

```c
TupleTableSlot *fetchslot;
fetchslot = table_slot_create(resultRelationDesc, NULL);

if (table_tuple_fetch_row_version(resultRelationDesc, tupleid,
                                  SnapshotAny, fetchslot))
{
    /* fetchslot now contains the old tuple — use slot_getattr */
}

ExecDropSingleTupleTableSlot(fetchslot);
```

`table_slot_create` and `table_tuple_fetch_row_version` are in `access/tableam.h`. `SnapshotAny` is defined in `utils/snapmgr.h`. Both headers are already included by the file.

---

## Your Task

There are **4 TODOs** in the template file `nodeModifyTable.c`:

### TODO 1 — GUC and helper (near the top of the file)

Add the following:

1. `#include "utils/guc.h"`
2. A static `bool` flag for the GUC (default `false`)
3. A static `bool` to track if the GUC has been registered
4. A static function `_dml_lab_register_guc()` that:
   - Returns immediately if already registered
   - Calls `DefineCustomBoolVariable("dml_lab.enable_logging", ...)` linking to your flag
   - Calls `MarkGUCPrefixReserved("dml_lab")`

This is the same pattern as Lab 2.

### TODO 2 — INSERT logging (inside `ExecInsert()`)

After `table_tuple_insert()`, add code to:
1. Register the GUC
2. If logging is enabled, read the first column with `slot_getattr(slot, 1, &isnull)`
3. If non-null and the value is odd (`val % 2 != 0`), call:
   ```c
   elog(INFO, "DML_LAB_LOG: INSERT val=%d", val);
   ```

### TODO 3 — DELETE logging (inside `ExecDelete()`)

Before the `ldelete:` label (i.e., before `ExecDeleteAct` is called), add code to:
1. Register the GUC
2. If logging is enabled and `tupleid` is not NULL:
   - Create a temporary slot with `table_slot_create(resultRelationDesc, NULL)`
   - Fetch the old tuple with `table_tuple_fetch_row_version(..., SnapshotAny, ...)`
   - If found, read the first column
   - If non-null and even (`val % 2 == 0`), call:
     ```c
     elog(INFO, "DML_LAB_LOG: DELETE val=%d", val);
     ```
   - Drop the temporary slot with `ExecDropSingleTupleTableSlot(fetchslot)`

### TODO 4 — UPDATE logging (inside `ExecUpdate()`)

After the `switch(result)` block (when `TM_Ok` was the outcome), add code to:
1. Register the GUC
2. If logging is enabled:
   - Read old value: `slot_getattr(oldSlot, 1, &old_isnull)`
   - Read new value: `slot_getattr(slot, 1, &new_isnull)`
   - If both non-null and either value is divisible by 3, call:
     ```c
     elog(INFO, "DML_LAB_LOG: UPDATE old_val=%d new_val=%d", old_val, new_val);
     ```

---

## Compiling and Testing

```bash
# Copy your file into the source tree
cp nodeModifyTable.c /work/.pg/postgres/src/backend/executor/

# Build
cd /work/.pg/postgres && make -j$(nproc) && make install

# Restart server
pg_ctl -D /work/.pg/data stop 2>/dev/null; pg_ctl -D /work/.pg/data -l /tmp/pg.log start
```

Test in psql:
```sql
CREATE TABLE test(id int, name text);

SET dml_lab.enable_logging = on;

-- INSERT: odd id → logged
INSERT INTO test VALUES (1, 'a');
-- INFO:  DML_LAB_LOG: INSERT val=1

-- INSERT: even id → NOT logged
INSERT INTO test VALUES (2, 'b');
-- (no output)

-- DELETE: even id → logged
DELETE FROM test WHERE id = 2;
-- INFO:  DML_LAB_LOG: DELETE val=2

-- UPDATE: old=1 → new=3 (3 is div by 3) → logged
UPDATE test SET id = 3 WHERE id = 1;
-- INFO:  DML_LAB_LOG: UPDATE old_val=1 new_val=3

SET dml_lab.enable_logging = off;
DELETE FROM test WHERE id = 3;
-- (no output — logging disabled)
```

---

## Submission

Upload **one file** to Gradescope: `nodeModifyTable.c`
