# CSCI 5708 — Lab 1: Buffer Replacement Policy (2nd-LRU)

**Architecture and Implementation of Database Management Systems**
**Instructor:** Chang Ge (cge@umn.edu)

---

## Overview

In this lab, you will modify the PostgreSQL buffer manager to replace its default **clock-sweep** replacement policy with a custom algorithm called **2nd-LRU** (Second Least Recently Used). This exercise will give you hands-on experience navigating and modifying the internals of a production-grade DBMS.

**Estimated time:** 8–12 hours (implementation + testing)

**Due date:** Feb 20 @ 11:59 PM CT

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Background: Buffer Management Review](#2-background-buffer-management-review)
3. [The 2nd-LRU Algorithm](#3-the-2nd-lru-algorithm)
4. [Output Format Specification (IMPORTANT)](#4-output-format-specification-important)
5. [PostgreSQL Buffer Manager Architecture](#5-postgresql-buffer-manager-architecture)
6. [Source Code Walkthrough](#6-source-code-walkthrough)
7. [What We Provide](#7-what-we-provide)
8. [Your Task: Completing `freelist.c`](#8-your-task-completing-freelistc)
9. [Compiling and Testing](#9-compiling-and-testing)
10. [Submission](#10-submission)

---

## 1. Prerequisites

This lab assumes you have already completed the **Development Environment Setup** document distributed earlier in the course. Before starting this lab, you should have:

- Docker Desktop (or Engine) installed and running
- VS Code installed with the **Dev Containers** extension
- The course repository cloned and opened in a Dev Container
- PostgreSQL source code cloned at `/work/.pg/postgres` (branch `REL_18_STABLE`)
- PostgreSQL compiled and installed to `/work/.pg/install`
- A database initialized at `/work/.pg/data` via `initdb`
- Verified that you can start the server and connect with `psql`

If any of the above is not set up, please refer to the **Development Environment Setup** document first.

**Quick check** — run these in your Dev Container terminal to verify:

```bash
export PATH=/work/.pg/install/bin:$PATH
postgres --version     # should print "postgres (PostgreSQL) 18.x"
ls /work/.pg/data/     # should show postgresql.conf, base/, etc.
```

---

## 2. Background: Buffer Management Review

### Why Buffer Management?

A DBMS cannot keep the entire database in memory. Instead, it maintains a **buffer pool** — a fixed-size region of main memory that caches frequently used disk pages. When a page is needed but not in the buffer pool, the DBMS must **evict** an existing page to make room. The algorithm that decides *which* page to evict is called the **buffer replacement policy**.

### Key Concepts

| Concept | Description |
|---|---|
| **Buffer Pool** | A fixed-size array of **frames** (slots), each holding one disk page. |
| **Buffer Descriptor** | Metadata for each frame: which page it holds, whether it's dirty, its pin count, etc. |
| **Pin / Unpin** | A process **pins** a buffer when it needs to use the page (incrementing a reference count). It **unpins** when done. A pinned buffer **cannot** be evicted. |
| **Dirty Bit** | Indicates the in-memory page has been modified and must be written back to disk before eviction. |
| **Reference Count (refcount)** | The number of processes currently using (pinning) a buffer. A buffer is a candidate for eviction only when `refcount == 0`. |
| **Replacement Policy** | The algorithm that selects which unpinned buffer to evict. Common policies: LRU, Clock, MRU, 2Q, etc. |

### LRU (Least Recently Used)

Standard LRU evicts the buffer whose most recent access is the **oldest**. If buffers have timestamps `[2, 5, 3, 7]`, LRU evicts the one with timestamp `2`.

### What is 2nd-LRU?

**2nd-LRU** is a variation that evicts the buffer with the **second-smallest** (second-least-recent) timestamp, effectively "protecting" the single oldest buffer from eviction.

---

## 3. The 2nd-LRU Algorithm

### Basic Idea

Given buffers with recent-use timestamps:

```
A(2), B(3), C(4), D(5)
```

When a new page `E` arrives at time `6` and we need to evict:
- The **least** recently used is `A(2)`.
- The **2nd-least** recently used is `B(3)`.
- **2nd-LRU evicts `B`**, not `A`.

Result:
```
A(2), E(6), C(4), D(5)
```

### Formal Rules

1. **Timestamp tracking:** Maintain a global integer counter. Every time a buffer is "used" (pinned), assign the current counter value to that buffer's timestamp, then increment the counter. Initially, all timestamps are `0`.

2. **Eviction scan:** When a buffer must be replaced:
   - Scan **all** buffers in the pool.
   - Identify **candidate** buffers: those with `refcount == 0` (not currently pinned).
   - Among candidates, find the one with the **second-smallest** timestamp. Evict it.

3. **Edge cases:**
   - If there is **exactly 1** candidate, evict it (there is no "second").
   - If there are **0** candidates, retry the scan. You may retry up to **10 rounds**.
   - After 10 failed rounds, abort with: `elog(ERROR, "5708: no buffers available");`

4. **Logging (required for grading):** See [Section 4: Output Format Specification](#4-output-format-specification-important) for the **exact** `printf` format you must use. Your output will be parsed by an automated autograder.

### Example Output (server terminal)

```
Candidate buffers: 1, 56, 59, 55, 61, 60, 67, 66, 39, 40, 45, 44, 46, 47, 48, 49
Replaced buffer: 39
Candidate buffers: 1, 56, 59, 55, 61, 60, 67, 66, 40, 45, 44, 46, 47, 48, 49
Replaced buffer: 40
```

---

## 4. Output Format Specification (IMPORTANT)

> **⚠️ Your submission will be graded by an automated autograder. The autograder parses your `printf` output to verify correctness. You MUST follow the exact format below. Any deviation (extra spaces, missing commas, different wording, etc.) will cause autograder test failures.**

### Required Output

Every time your 2nd-LRU algorithm selects a victim buffer, you must print **exactly two lines** to `stdout` using `printf`:

**Line 1 — Candidate list:**
```
Candidate buffers: T1, T2, T3, ..., Tn
```

**Line 2 — Replaced buffer:**
```
Replaced buffer: T
```

where `T1, T2, ...` are the `lru_timestamp` values of all candidate buffers (in buffer-index order), and `T` is the `lru_timestamp` of the evicted buffer.

### Format Rules

| Rule | Detail |
|---|---|
| **Prefix (line 1)** | Must be exactly `Candidate buffers: ` (with one space after the colon). |
| **Prefix (line 2)** | Must be exactly `Replaced buffer: ` (with one space after the colon). |
| **Separator** | Candidate timestamps are separated by exactly `, ` (comma + one space). |
| **No trailing comma** | Do NOT put a comma after the last timestamp. |
| **Newline** | Each line ends with exactly one `\n`. |
| **Timestamp format** | Each timestamp is printed as a plain integer via `%d` (no padding, no leading zeros). |
| **Order of candidates** | List candidate timestamps in **buffer index order** (`i = 0, 1, ..., NBuffers-1`). |
| **When to print** | Print these two lines **every time** a buffer is evicted via 2nd-LRU. Do NOT print when a buffer is taken from the freelist. |
| **No other output** | Do not add any extra `printf` statements. Extra output will confuse the autograder. |

### Exact C Code You Must Use

The following code snippets are also provided in the template file (`freelist_template.c`). **Copy them exactly** into your implementation:

**Printing the candidate list** (after scanning all buffers and before evicting):

```c
/* --- Print candidate timestamps in buffer-index order --- */
{
    int first = 1;
    printf("Candidate buffers: ");
    for (i = 0; i < NBuffers; i++)
    {
        BufferDesc *cand = GetBufferDescriptor(i);
        uint32      cs   = pg_atomic_read_u32(&cand->state);
        if (BUF_STATE_GET_REFCOUNT(cs) == 0)
        {
            if (!first)
                printf(", ");
            printf("%d", cand->lru_timestamp);
            first = 0;
        }
    }
    printf("\n");
}
```

**Printing the replaced buffer** (immediately after the candidate list):

```c
printf("Replaced buffer: %d\n", buf->lru_timestamp);
```

> **Note:** The variable names (`i`, `buf`, `cand`, `cs`) must match whatever you use in your implementation. The *format strings* — `"Candidate buffers: "`, `", "`, `"%d"`, `"\n"`, and `"Replaced buffer: %d\n"` — must be **character-for-character identical** to what is shown above.

### What the Autograder Checks

For each pair of output lines, the autograder will:

1. Parse the candidate timestamps from line 1.
2. Verify the "Replaced buffer" timestamp on line 2 is the **second-smallest** among the candidates (or the only candidate if there is exactly 1).
3. Verify each line is well-formed (correct prefixes, correct separators, no extra text).

---

## 5. PostgreSQL Buffer Manager Architecture

PostgreSQL's buffer manager lives in `src/backend/storage/buffer/`. Here is what each file does:

| File | Purpose |
|---|---|
| `buf_init.c` | Initializes the shared buffer pool at server startup. Allocates buffer descriptors, buffer blocks, and links all buffers into the initial freelist. |
| `buf_table.c` | Manages the buffer lookup hash table — maps `(tablespace, database, relation, fork, block)` tags to buffer IDs. |
| `bufmgr.c` | The main buffer manager interface. Contains `BufferAlloc()` (allocate/find a buffer for a page), `PinBuffer()` / `UnpinBuffer()`, `ReadBuffer()`, `ReleaseBuffer()`, etc. |
| `freelist.c` | Implements the buffer **replacement strategy**. Contains `StrategyGetBuffer()` which selects the next victim buffer. **This is where you will implement 2nd-LRU.** |
| `localbuf.c` | Manages **local** (backend-private) buffers for temporary tables. Not relevant to this lab. |

### The Buffer Descriptor (`BufferDesc`)

Defined in `src/include/storage/buf_internals.h`:

```c
typedef struct BufferDesc
{
    BufferTag   tag;            /* identifies which disk page is in this buffer */
    int         buf_id;         /* buffer's index (0 to NBuffers-1) */
    pg_atomic_uint32 state;     /* packed: flags + refcount + usagecount */
    int         wait_backend_pgprocno;
    int         freeNext;       /* link in freelist chain */
    int         lru_timestamp;  /* *** ADDED: timestamp for 2nd-LRU *** */
    PgAioWaitRef io_wref;
    LWLock      content_lock;
} BufferDesc;
```

Key fields for this lab:
- **`state`**: A packed 32-bit integer containing the **reference count** (pin count) and **usage count**. Use `BUF_STATE_GET_REFCOUNT(state)` to extract the refcount.
- **`lru_timestamp`**: **We added this field** for you. It stores the timestamp of the last time this buffer was pinned.
- **`buf_id`**: The index of this buffer in the global `BufferDescriptors` array.

### How Buffers Flow Through the System

```
                        BufferAlloc() needs a page
                               |
                               v
                    Is the page already cached?
                      /                    \
                    YES                     NO
                     |                       |
               PinBuffer()           StrategyGetBuffer()
           (timestamp updated)         selects a victim
                                           |
                                     PinBuffer_Locked()
                                   (timestamp updated)
                                           |
                                    Buffer is reused
                                    for the new page
```

When `StrategyGetBuffer()` is called:
1. It first checks the **freelist** — a linked list of buffers that have never been used. Initially, all buffers are on the freelist.
2. If the freelist is empty, it runs the **replacement algorithm** (originally clock-sweep; you will replace this with 2nd-LRU).

### Useful Macros and Functions

| Name | What it does |
|---|---|
| `NBuffers` | Global variable: total number of shared buffers. |
| `GetBufferDescriptor(i)` | Returns a pointer to the `BufferDesc` for buffer index `i`. |
| `pg_atomic_read_u32(&buf->state)` | Reads the buffer's state (containing refcount, usagecount, flags) without locking. |
| `BUF_STATE_GET_REFCOUNT(state)` | Extracts the reference count from a buffer state value. A buffer with `refcount == 0` is not pinned and is a candidate for eviction. |
| `LockBufHdr(buf)` | Acquires the buffer header spinlock and returns the current state. |
| `UnlockBufHdr(buf, state)` | Releases the buffer header spinlock, writing `state` back. |
| `AddBufferToRing(strategy, buf)` | If using a non-default strategy, registers the buffer in the ring. |
| `elog(ERROR, "...")` | Aborts the current transaction with an error message. |

---

## 6. Source Code Walkthrough

### Where buffers are **initialized** — `buf_init.c`

In `BufferManagerShmemInit()`, there is a loop that initializes every buffer descriptor. **We added** the line `buf->lru_timestamp = 0;` so every buffer starts with timestamp 0:

```c
for (i = 0; i < NBuffers; i++)
{
    BufferDesc *buf = GetBufferDescriptor(i);
    ClearBufferTag(&buf->tag);
    pg_atomic_init_u32(&buf->state, 0);
    buf->wait_backend_pgprocno = INVALID_PROC_NUMBER;
    buf->buf_id = i;
    buf->lru_timestamp = 0;       // <-- ADDED
    pgaio_wref_clear(&buf->io_wref);
    buf->freeNext = i + 1;
    // ...
}
```

### Where buffers are **used** (pinned) — `bufmgr.c`

There are two functions that pin buffers:

1. **`PinBuffer()`** — called when a buffer is found in the hash table (cache hit) or re-pinned. We added:
   ```c
   buf->lru_timestamp = lru_global_timestamp++;
   ```

2. **`PinBuffer_Locked()`** — called when a victim buffer is selected by `StrategyGetBuffer()` and immediately pinned (the spinlock is already held). We added the same line:
   ```c
   buf->lru_timestamp = lru_global_timestamp++;
   ```

Both reference `lru_global_timestamp`, a global counter defined in `freelist.c` and declared `extern` in `bufmgr.c`.

### Where replacement happens — `freelist.c` (YOUR TASK)

`StrategyGetBuffer()` is the function that selects a buffer for replacement. Its structure:

```
StrategyGetBuffer()
    |
    +-- Check ring strategy (if applicable) --> return buffer from ring
    |
    +-- Wake bgwriter (if needed)
    |
    +-- Try freelist --> return unused buffer
    |
    +-- ** REPLACEMENT ALGORITHM ** --> return victim buffer
         (originally: clock-sweep)
         (your task:  2nd-LRU)
```

**You only need to implement the replacement algorithm section.** Everything before it (ring strategy, bgwriter notification, freelist) is already provided and should **not** be changed.

---

## 7. What We Provide

The following files are included in the lab materials. **Do not modify them** — just copy them into the appropriate locations.

| File | Copy to | Description |
|---|---|---|
| `buf_internals.h` | `src/include/storage/buf_internals.h` | Added `int lru_timestamp;` field to `BufferDesc` struct. |
| `buf_init.c` | `src/backend/storage/buffer/buf_init.c` | Added `buf->lru_timestamp = 0;` in the initialization loop. |
| `bufmgr.c` | `src/backend/storage/buffer/bufmgr.c` | Added `extern int lru_global_timestamp;` declaration. Added `buf->lru_timestamp = lru_global_timestamp++;` in both `PinBuffer()` and `PinBuffer_Locked()`. |
| `freelist_template.c` | (see [Section 8](#8-your-task-completing-freelistc)) | Template for your implementation. Contains `TODO` markers where you write code. |
| `postgresql.conf` | `/work/.pg/data/postgresql.conf` | Pre-configured with `shared_buffers = 128kB` (16 buffer frames). |
| `buffer_add.sql` | `/work/buffer_add.sql` | Test SQL: creates a table + index, bulk-loads 10,000 rows. |
| `values10k.dat` | `/work/values10k.dat` | Test data file (10,000 rows) used by `buffer_add.sql`. |

---

## 8. Your Task: Completing `freelist.c`

We provide a **template** version of `freelist.c` (see `freelist_template.c` in this directory). This template contains the full file with the 2nd-LRU implementation section replaced by `TODO` markers.

### What you need to implement

Inside `StrategyGetBuffer()`, after the freelist section, you will see a block marked with `TODO` comments. You need to:

1. **Declare a global timestamp counter** at the top of the file (after the `#define` and before the struct definition). This integer starts at `1` and is incremented every time a buffer is pinned (handled by `bufmgr.c`).

2. **Implement the 2nd-LRU replacement** inside `StrategyGetBuffer()`:
   - Scan all `NBuffers` buffers using `GetBufferDescriptor(i)`.
   - For each buffer, read its state with `pg_atomic_read_u32(&candidate->state)`.
   - A buffer is a **candidate** if `BUF_STATE_GET_REFCOUNT(cand_state) == 0`.
   - Track the least and second-least timestamps among candidates.
   - **Print output using the EXACT format** specified in [Section 4](#4-output-format-specification-important). The exact `printf` snippets are provided in both Section 4 and in the template file — copy them verbatim.
   - Lock the chosen victim with `LockBufHdr()`, verify it's still unpinned, and return it.
   - Handle edge cases: 0 candidates (retry), 1 candidate (evict it), race conditions (buffer got pinned between scan and lock — retry).
   - After 10 failed rounds, call `elog(ERROR, "5708: no buffers available");`.

### Template markers to look for

```c
/* TODO: Declare the global timestamp counter here */

/* TODO: Implement 2nd-LRU replacement algorithm here */
```

### Important implementation notes

- **Include `<limits.h>`** for `INT_MAX` (used to initialize "infinity" for comparison).
- **Include `<stdio.h>`** for `printf()`.
- The function must return a `BufferDesc *` with the **buffer header spinlock held** (i.e., after `LockBufHdr()` but before `UnlockBufHdr()`).
- Before returning, if `strategy != NULL`, call `AddBufferToRing(strategy, buf)`.
- Set `*buf_state = local_buf_state` before returning.
- **Race condition handling:** Between scanning and locking, another process might pin the buffer. After `LockBufHdr()`, check `BUF_STATE_GET_REFCOUNT(local_buf_state) == 0` again. If the buffer is now pinned, `UnlockBufHdr()` and retry.

---

## 9. Compiling and Testing

This section walks through the **complete** compile-and-test cycle. All paths assume the environment from the **Development Environment Setup** document.

### Step 0: Set up PATH

In **every terminal** you use, start by setting the PATH:

```bash
export PATH=/work/.pg/install/bin:$PATH
```

> **Tip:** Add this to your `~/.bashrc` so it's automatic:
> ```bash
> echo 'export PATH=/work/.pg/install/bin:$PATH' >> ~/.bashrc
> source ~/.bashrc
> ```

### Step 1: Stop the server (if running)

```bash
# If started with pg_ctl:
pg_ctl -D /work/.pg/data/ stop

# If started in foreground (postgres -D ...):
# Press Ctrl+C in that terminal
```

### Step 2: Install the provided `postgresql.conf` (one-time)

We provide a pre-configured `postgresql.conf` with `shared_buffers = 128kB` (16 buffer frames), which makes replacement behavior easily observable. Copy it into the data directory:

```bash
cp postgresql.conf /work/.pg/data/postgresql.conf
```

**Verify:**
```bash
grep "^shared_buffers" /work/.pg/data/postgresql.conf
# Should show: shared_buffers = 128kB
```

### Step 3: Copy files into the source tree

```bash
# Copy the provided (pre-modified) files:
cp buf_internals.h  /work/.pg/postgres/src/include/storage/buf_internals.h
cp buf_init.c       /work/.pg/postgres/src/backend/storage/buffer/buf_init.c
cp bufmgr.c         /work/.pg/postgres/src/backend/storage/buffer/bufmgr.c

# Copy YOUR implementation:
cp freelist_template.c /work/.pg/postgres/src/backend/storage/buffer/freelist.c
```

### Step 4: Compile

```bash
cd /work/.pg/postgres

# Compile (uses all CPU cores):
make -j

# Install:
make install
```

If you see errors, read them carefully — they point to the exact file and line.

If you get strange errors after multiple edits, try a clean rebuild:
```bash
make clean && make -j && make install
```

### Step 5: Re-initialize the database (if needed)

If the server crashes on startup with shared-memory errors after recompiling, re-initialize:

```bash
rm -rf /work/.pg/data
initdb -D /work/.pg/data
cp postgresql.conf /work/.pg/data/postgresql.conf
```

### Step 6: Start the server

**Option A: Foreground (recommended — see `printf` output directly):**

```bash
export PATH=/work/.pg/install/bin:$PATH
postgres -D /work/.pg/data
```

Your `Candidate buffers:` / `Replaced buffer:` output appears directly in this terminal. Open a **separate terminal** for the client.

**Option B: Background (output in log file):**

```bash
pg_ctl -D /work/.pg/data/ start -l /work/.pg/server.log
```

View output with:
```bash
tail -f /work/.pg/server.log
# Or:
grep "Candidate buffers:\|Replaced buffer:" /work/.pg/server.log | head -30
```

### Step 7: Install test data (one-time)

The test files (`buffer_add.sql` and `values10k.dat`) are provided in the lab materials. Copy them to `/work/` if they are not already there:

```bash
# Copy test files (skip if already in /work/):
cp buffer_add.sql /work/buffer_add.sql
cp values10k.dat  /work/values10k.dat
```

> The SQL file is already configured with the correct path to `values10k.dat`. No manual editing is needed.

### Step 8: Run the test

In a separate terminal (if the server is running in the foreground):

```bash
export PATH=/work/.pg/install/bin:$PATH
psql -d postgres -f /work/buffer_add.sql
```

Expected output:
```
DROP TABLE
CREATE TABLE
CREATE INDEX
SET
COPY 10000
```

### Step 9: Verify output

Check the server terminal (foreground) or log file (background):

```bash
# Count replacements:
grep -c "Replaced buffer:" /work/.pg/server.log

# View first 20 lines:
grep "Candidate buffers:\|Replaced buffer:" /work/.pg/server.log | head -20
```

**What to verify:**
1. Output follows the **exact format** from [Section 4](#4-output-format-specification-important).
2. "Replaced buffer" timestamp is the **second-smallest** in the candidate list.
3. If there's only 1 candidate, it equals that candidate's timestamp.
4. Timestamps should be non-zero and increasing over time.

### Quick Reference: Full Compile-Test Cycle

```bash
export PATH=/work/.pg/install/bin:$PATH
pg_ctl -D /work/.pg/data/ stop 2>/dev/null
cd /work/.pg/postgres && make -j && make install
pg_ctl -D /work/.pg/data/ start -l /work/.pg/server.log
sleep 1
psql -d postgres -f /work/buffer_add.sql
grep "Candidate buffers:\|Replaced buffer:" /work/.pg/server.log | tail -10
```

---

## 10. Submission

Submit your completed `freelist.c` file to **Gradescope**. The file must be named exactly `freelist.c`.

You only need to submit this single file — the other modified source files (`buf_internals.h`, `buf_init.c`, `bufmgr.c`) are provided by us and will be used automatically during grading.
