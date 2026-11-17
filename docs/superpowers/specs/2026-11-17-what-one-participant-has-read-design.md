# What one participant has read

An agent outside the app wants to know what was said in a call, and to be told when there is
something new. This is the reading part only: nothing here sends anything to a browser, and the
page keeps its own rendering path.

## What is decided

1. The word for the thing is **message**. A resource `message://` answers the entries that carry
   text, read as a whole. A tool that answers what one participant has not read uses the same
   word. The existing `get_transcription` keeps answering the microphone session as it does today
   (`tests/test_mcp_tools.py:165`), because a name that states the microphone cannot answer the
   record.

2. Read state is keyed to **the participant**, as agreed. It can only exist for a name that was
   joined, so a reader outside the app has to join first — `_find_participant(roster, name)` at
   `src/ziomek/mcp/tools.py:580` answers a name only for participants in the call. Read state
   ends with the participant, which is when a call ends (`src/ziomek/roster.py:358-361`), so
   nothing is kept for a reader that is not in the call, and nothing is written to disk.

3. What was read is a **set of times**, not a place in a list. A list position cannot say which
   lines are new after a reconnect, and it changes when an entry is added before it. An entry keeps
   the time it was noted as its identity (`src/ziomek/roster.py:336-342`, decided by `decide_time`
   in `src/ziomek/messages.py`), which is why an entry stays open when another one after it was
   said to be read. A time also answers a span a caller names, which is what "the last five minutes"
   meant (see Settled).
   be added.

4. Answering does not mark anything as read ✓. The act that records what was read is a separate
   call, and it sets something on an object that can be read back through `read_participant`.

5. Lines whose author is the participant itself are not answered for it ✓, so reading what was
   said gives what others said.

6. **A name in a call belongs to one participant.** `join()` refuses a name that is already in the
   call (`src/ziomek/roster.py:174-175`), so a caller is never given more than one match to choose
   between and a reading tool answers the participant that name was joined as. This is the rule,
   and it is tested at `tests/test_roster.py:104`; `_find_participant` (`src/ziomek/mcp/tools.py:580`)
   can take the match it finds because there is only one.

## The shape

- `read_messages(name)` answers the entries this participant has not read, in the order they were
  noted: the time, the name it is about, the text, and who wrote it. Nothing is changed by
  answering. With nothing recorded as read, everything is answered — that is what a join starts at,
  so a new reader gets the whole record as it agreed.
- What was read is stored as **the entries a caller said it read**, not as a moment read up to. A
  moment can only state an end, so it says the entries before that end were read — but a caller can
  be answered with part of the record and read only part of it, which is a case the caller can
  reach. An entry keeps its own time as its identity, since `decide_time` keeps each time later
  than the one before, so an entry that was not said to be read stays open instead of being closed
  by an entry that comes after it. The field is `Participant.read_times`, an attribute because it
  holds what is stored; the act that records entries is `mark_as_read(participant, entries)`.
- `message://` is registered with the other resources in `src/ziomek/mcp/resources.py` and answers
  the entries that carry text. A resource is read as a whole, so it cannot answer what one
  participant has not read; that stays the tool.

## Tests first, in the order they ask for behavior

Run as value tests reading the definitions through their exports, per `internal/tests.md`.

1. A line can be said to have happened at a time — an entry carries the moment it was noted.
2. A message is answered for one participant only, and lines that participant wrote are not
   answered for it.
3. Which messages are new for one participant is answered from what was set for it, not from what
   the last call asked for.
4. Answering does not record anything as read; saying which entries a caller read takes them out of
   what is answered next.
5. A reader that has recorded nothing is answered with the whole record as it was at its join.
6. A name in a call belongs to one participant, so a reading tool answers that one. Already tested
   at `tests/test_roster.py:104`, so nothing new is written for it.
7. What counts as a message is decided by one definition, read through its export
   (`tests/test_what_counts_as_a_message.py`).
8. The whole record is read as one thing through `message://`, answered through that one definition
   and not through a second check of its own (`tests/test_the_record_is_answered_as_one_thing.py`).

Nothing here is a test that reads a string in a file, except the registration of the resource,
which is what a client is shown as available.

## Settled

"The last five minutes" was a figure of speech, so there is no window argument: what was read is
only what a caller can be told, and the reading tool takes nothing besides the name. A reader that has
recorded nothing is answered with the whole record as it was at its join, which is what the tests ask
for.
