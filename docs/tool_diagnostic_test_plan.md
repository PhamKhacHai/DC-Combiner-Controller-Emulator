# Tool Diagnostic Test Plan

## Scope

This plan verifies the PC tool diagnostic counter workflow. It does not require firmware changes and does not change the existing command/status/heartbeat protocol.

## Safety Notes

- Diagnostic reads do not refresh the firmware CAN command timeout.
- Use periodic command if outputs must stay ON while reading counters.
- Test OFF ALL before any group ON command.
- Do not run the original USB CAN Tool at the same time as this tool.
- Confirm CAN_H, CAN_L, and GND wiring before testing with a real board.

## Mock Mode

1. Open `DC Combiner Controller Emulator`.
2. Select `Driver mode = Mock`.
3. Click `Connect`.
4. Open the `Diagnostics` tab.
5. Click `Read All Counters`.
6. Verify the group and global tables update with numeric values.
7. Turn ON Group 1 with `Send Once`.
8. Read `Group 1 / ON Count`.
9. Expect the value to increase.
10. Click `Off All`.
11. Read `Group 1 / OFF Count`.
12. Expect the value to increase.
13. Click `Reset All Counters` and confirm.
14. Verify displayed counters clear to `0`.

## Bridge Mode Real Board

1. Close the original USB CAN Tool.
2. Connect USB-CAN-B to the board CAN bus.
3. Select `Driver mode = USB-CAN-B Bridge`.
4. Set `Node ID = 0`.
5. Set `Bitrate = 500000`.
6. Click `Connect`.
7. Click `Off All`.
8. Open the `Diagnostics` tab.
9. Click `Read All Counters`.
10. Verify RX frames with ID `0x540 + NodeID` appear in the log.
11. Start periodic command if a group must stay ON.
12. Turn ON Group 1 with valid feedback.
13. Read `Group 1 / ON Count`.
14. Expect the value to increase by at least `1`.
15. Click `Off All`.
16. Read `Group 1 / OFF Count`.
17. Expect the value to increase by at least `1`.
18. Create a feedback mismatch or group fault only under a safe bench setup.
19. Read `Feedback Mismatch`, `Group Fault`, `ON Timeout Fault`, or `Unexpected OFF Fault`.
20. Expect the related counter to increase according to the firmware event.
21. Stop periodic command and allow command timeout under a safe output state.
22. Read `CAN Timeout Count`.
23. Expect the value to increase by at least `1`.
24. Click `Reset All Counters` and confirm.
25. Read all counters again and verify values are reset or only reflect events caused after the reset response.

## Direct Mode Real Board

Use the same real-board flow as Bridge mode only after `ControlCAN.dll` loads and `VCI_OpenDevice`, `VCI_InitCAN`, and `VCI_StartCAN` all succeed.

## Expected CAN Frames

Read CAN Timeout Count:

```text
TX 0x530: 01 24 FF 00 00 00 00 00
RX 0x540: 81 24 FF vv vv vv vv 00
```

Reset all counters:

```text
TX 0x530: 02 A5 5A 00 00 00 00 00
RX 0x540: 82 00 FF 00 00 00 00 00
```
