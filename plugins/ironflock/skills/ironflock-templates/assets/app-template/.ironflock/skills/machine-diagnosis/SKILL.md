---
name: machine-diagnosis
description: >-
  How to find out why a machine is TOO_HOT or shows NO_READING, or what is
  wrong with a machine a user asks about: which rows to read, when to read the
  machine now with current_reading, and what to tell the user. Load it before
  you answer such a question.
---

# Diagnosing a machine

A user asked why a machine is too hot, why it has no reading, or what is wrong
with it. Find the cause in the app's tables and at the machine, then answer
with the evidence. You only read: you cannot change the limit, a device or a
machine.

## 1. Find the device and its state

Run with `execute_sql`:

```sql
SELECT DISTINCT ON (device_id) device_id, device_name, state, deleted, tsp
FROM devices
ORDER BY device_id, tsp DESC
```

Leave out the rows whose `deleted` is true. `state` is `OK`, `TOO_HOT` or
`NO_READING`, and `tsp` is when the device last changed it. When the user named
no machine, take the devices whose state is not `OK`; when several match a
question about one machine, ask which one.

## 2. Read the last hour and the limit

```sql
SELECT tsp, temperature, pressure
FROM measurements
WHERE device_key = <device_id> AND tsp > now() - interval '1 hour'
ORDER BY tsp
```

```sql
SELECT max_temperature, tsp FROM settings ORDER BY tsp DESC LIMIT 1
```

Without a `settings` row the limit is 80 °C.

## 3. TOO_HOT

Compare the temperatures with the limit:

- **Rising steadily for many minutes:** the machine heats up. Give the rise in
  °C per 10 minutes and the time it crossed the limit.
- **A jump between two readings:** suspect the sensor. Call `current_reading`
  for the device and compare its value with the last row.
- **Swinging around the limit:** the machine runs close to the limit. Say so,
  and that users can change the limit on the board's Settings page. Do not
  suggest a value.

Mention the pressure when it changed at the same time. When `current_reading`
returns a `max_temperature` other than the newest `settings` row, the device
has not applied the newest limit yet: it was offline when the limit was saved
and applies it once it is back.

## 4. NO_READING

1. Note the `tsp` of the device's newest `measurements` row. A device reads
   its machine every few seconds (5 by default).
2. Call `current_reading` for the device:
   - **It returns an error:** the device runs but cannot read the machine.
     Quote the error, and ask the user to check that the machine is switched on
     and connected to the device.
   - **It returns values:** the machine can be read again, and the state
     changes with the device's next reading.
   - **The call fails:** the device is offline or the app is not running on
     it. Say since when, from the newest row of step 1.

## 5. Answer

Say the state, since when, the cause you found and the evidence: values with
their units and times. Say what the user can do. When the data shows no cause,
say so instead of guessing.

Do not:

- tell anyone that a machine running too hot is safe to keep running;
- suggest deleting the device: that only removes it from the board.
