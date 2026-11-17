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
   joined, so a reader outside the app has to join first — `resolve_participant(name)` at
   `src/ziomek/roster.py:57` already answers names only for participants in the call. Read state
   ends with the participant, which is when a call ends (`src/ziomek/roster.py:358-361`), so
   nothing is kept for a reader that is not in the call, and nothing is written to disk.

3. The marker is a **time**, not a place in a list. A list position cannot say which lines are
   new after a reconnect, and it changes when an entry is added before it. A time also answers
   "the last five minutes", which is what you asked for. An entry needs the time it was noted —
   no entry has one today (`src/ziomek/roster.py:336-342`), so this is the one field that has to
   be added.

4. Answering does not mark anything as read ✓. The act that records what was read is a separate
   call, and it sets something on an object that can be read back through `read_participant`.

5. Lines whose author is the participant itself are not answered for it ✓, so reading what was
   said gives what others said.

6. A caller is told which name was used for the record when there is more than one match ✓, as
   `resolve_participant` answers today (`src/ziomek/roster.py:57`). This is not written down as a
   rule in any tracked file, so it stays a decision recorded here, not a rule I can point at.

## The shape

- `read_messages(name)` answers the entries this participant has not read, in the order they were
  noted: the time, the name it is about, the text, and who wrote it. Nothing is changed by
  answering. With no marker set, everything is answered — that is what a join starts at, so a new
  reader gets the whole record as it agreed.
- The marker is an attribute of the participant. An attribute is a name without a verb, so the
  field is `read_up_to` and holds the time this participant read up to. The act that sets it is
  `set_read_up_to(participant, time)`. The word position is not used: it states a place in a
  list, and this marker is not a place in a list.
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
4. Answering does not mark anything as read; setting the marker moves what is answered next.
5. A reader that has not set anything is answered with the whole record as it was at its join.
6. A name that matches more than one participant is answered with the name that was used for the
   record.
7. The whole record is read as one thing through `message://`, and only the entries that carry
   text are in it.

Nothing here is a test that reads a string in a file, except the registration of the resource,
which is what a client is shown as available.

## Open question

Whether "the last five minutes" is an argument of the reading tool, or only what a marker can
   be set to. If it is an argument, it is a second way of answering the same thing, and I would
   keep it out until there is a caller that needs it.
