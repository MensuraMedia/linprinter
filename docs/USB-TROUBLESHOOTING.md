# USB troubleshooting

LinPrinter prints over USB only. When a USB printer "isn't connected", "rejects jobs" or keeps
vanishing, the cause is almost always below every piece of software: **the cable**. This guide is
the order to check things in, what each message means, and the record of the week it took to learn
that on a Canon TR150.

## 1. Check in this order

1. **Another USB cable.** Plugged straight into the computer, no hub. Do this first even if the
   current cable "worked for a while" - in 2026 two faulty cables each held for minutes before
   failing, and the printer, the computer and the software were all blamed instead.
2. **Measure the link** (below). A good link loses nothing; a bad one loses a few percent or more.
3. **Turn the printer off and on** (unplug the power for 30 s). A job cut off mid-transfer can leave
   the printer's USB service stuck until then.
4. **Another socket**, then **another computer**. Only now suspect the printer's USB port or the
   computer's controller - and compare against a known-good device first.
5. **Check the print queues** (section 4): a stray queue with the printer's name breaks Print in
   other programs even when the printer is fine.

## 2. Measure the link

```bash
sudo python3 tools/usb_linktest.py 04a9:18a4                      # the printer (VID:PID from lsusb)
sudo python3 tools/usb_linktest.py 04a9:18a4 --compare 1a40:0101  # plus a known-good device
```

It reads the device's 18-byte descriptor 200 times and counts failures. It changes nothing and
prints nothing. The USB controller already retries each failed transaction three times before
reporting it, so **any** failures mean a bad link:

| Result | Meaning |
|---|---|
| 0 failed | Healthy. Look elsewhere (stuck printer, queues). |
| under 1 % | Marginal; it will fail on long jobs. Change the cable. |
| several % or more | Failing. On 2026-10-02 the bad cables lost 13.5 %; a 62 MB job can't get through. |
| printer fails, known-good device on the same controller doesn't | The computer is fine: cable, then the printer's port. |

## 3. What the messages mean

### In LinPrinter

| LinPrinter says | Cause | What to do |
|---|---|---|
| "The USB link to this printer keeps failing (N connection errors … on port 3-3 …)" | The kernel log shows `error -71` / disconnects on the printer's port in the last 10 minutes | Another cable first (section 1) |
| "A USB device on port 3-4 keeps failing to connect … can't even say what it is" | Something fails before it can identify itself; LinPrinter's remembered printer is missing | Same; it is very likely the printer |
| "The printer's USB connection isn't carrying data (ipp-usb answered 503 …)" | ipp-usb runs but can't move data over USB, or the printer is stuck holding a cut-off job | Printer off and on, or **Reconnect**; then a cable. LinPrinter does **not** fall back to CUPS here - that queue uses the same link |
| "The system print queue "…" sends jobs to serial:/dev/ttyS0, not to this printer" | A queue with the printer's name points at a serial port, parallel port or file | `sudo lpadmin -x <queue>`; CUPS recreates the right one |
| Only "Print to PDF" is listed | Nothing answers on USB and no errors were logged | Is the printer on? `lsusb`? Then section 1 |

### In the kernel log (`journalctl -k`)

| Message | Stage | Meaning |
|---|---|---|
| `Cannot enable. Maybe the USB cable is bad?` | port reset / speed negotiation | Electrical: the kernel's hint is usually right |
| `device descriptor read/64, error -71` | first contact | Electrical (`-71` = `EPROTO`, a transfer that failed on the wire) |
| `device not accepting address N, error -71` | addressing | Electrical |
| `can't set config #1, error -71` | configuring | Electrical; the device is left *addressed* but unusable - **Reconnect** retries it |
| `USB disconnect, device number N` (repeating every few seconds) | in use | The link drops; jobs are cut off |

None of these can be fixed by a driver, a CUPS setting, ipp-usb settings or USB power-management
options - they happen before or beneath all of them. (Tested: `usbcore.quirks=04a9:18a4:k`, which
turns off link power management, made no difference; device quirks can't apply anyway until the
device has delivered its IDs.)

### In the ipp-usb log (`/var/log/ipp-usb/`)

| Message | Meaning |
|---|---|
| `libusb_bulk_transfer: Input/Output Error` | A data transfer failed on the wire - the same fault as `-71` |
| `libusb_set_configuration: Entity not found`, every ~2.5 s | ipp-usb retrying a device the link has broken; it keeps resetting it. Fix the link |
| `Device is blacklisted` | A quirk file tells ipp-usb to leave the device alone (see below) |

## 4. Print queues

CUPS (cups-browsed) creates a driverless queue for an IPP-over-USB printer by itself, named after
the printer (e.g. `Canon_TR150_series_USB`, device `implicitclass://Canon_TR150_series_USB/`). A
**permanent queue owns its name**: if someone adds a queue with that name pointing elsewhere - on
2026-10-01 a raw queue on `serial:/dev/ttyS0` appeared while the printer was off the bus - every
program's Print goes there and is rejected. `lpstat -v` shows each queue's device:

```bash
lpstat -v                    # queue -> device
sudo lpadmin -x <queue>      # remove a wrong one
```

LinPrinter 0.2.8 reads queues by their device, not their name, and warns about this case.

## 5. Driverless IPP and the TR150's interfaces

The TR150 has five USB interfaces. Interface 0 (7/1/2) is the classic printer channel; its
IEEE-1284 ID says `CMD:IVEC` - Canon's private language, spoken only by Canon's `cnijfilter2`
driver, which is not in Debian, Ubuntu or Mint. Interfaces 1 and 2 carry IPP-over-USB (7/1/4) on
**alternate setting 1**; ipp-usb serves that on `127.0.0.1:60000`, and LinPrinter prints there in
PWG raster. That is the right path: no driver is missing.

ipp-usb details worth knowing (version 0.9.24, Ubuntu 24.04 / Mint 22):

- It is started by its own udev rule each time the printer is plugged in, and exits when it's
  unplugged. Nothing needs maintaining per connection.
- Quirk sections match the **model name**, not the USB id: `[Canon TR150 series]` works,
  `[04a9:18a4]` is ignored. Local quirks go in `/etc/ipp-usb/quirks/*.conf`.
- `init-reset` already defaults to `none` in this version.
- To keep ipp-usb away from a printer (for low-level tests only - LinPrinter's direct method needs
  it): `[Canon TR150 series]` + `blacklist = true`, then `sudo systemctl restart ipp-usb`.

## 6. The TR150 case, 2026-09-21 to 2026-10-02

| When | What happened | What was concluded then |
|---|---|---|
| 09-21 | Two CUPS queues (`usb://` and ipp-usb) fought over the printer | Duplicate removed (correct) |
| 09-23 | `-71` on ports 3-5, 3-1, 3-4, 3-3; replies cut mid-transfer; "can't set config" | "The printer's USB link" - a cable had been swapped once |
| 09-24 | Host study (linux-peripherals `docs/HOST-USB.md`): one root hub for every USB 2.0 device | Host suspected; ten tests listed, none run |
| 10-01 22:31-22:55 | Printer fails to enumerate (`Cannot enable…`); a raw queue on `serial:/dev/ttyS0` appears with the printer's name | Stray queue found and deleted |
| 10-01 23:05-23:10 | Port 3-3: reconnects every 5-8 s; port 3-1: every ~45 s | "Socket quality" |
| 10-01 23:14 | LinPrinter's direct method gets HTTP 503; it falls back to CUPS; the job is cut off and retried; the printer hangs | **Bug**: no fallback onto the same link (fixed in 0.2.8) |
| 10-01 23:18 | Second cable: 2 minutes clean, then I/O errors and a failed enumeration after a power cycle | "The cable helped but isn't the cause" - **wrong** |
| 10-02 00:18 | Rear socket 3-4: fails to enumerate | |
| 10-02 00:33-00:41 | Talked to the printer directly over usbfs: configuration via Reconnect, 1284 ID read (`CMD:IVEC`), interface 1 alt 1 selected; bulk transfers fail with `-71` | |
| 10-02 00:44 | Link test: printer 27/200 + 23/200 failed; USB hub on the same controller 0/200 | "The printer's USB port" - **wrong** |
| 10-02 00:49 | **Third cable**: enumerates first time; link test 0/200 + 0/200 | **Both earlier cables were faulty** |
| 10-02 00:54 | The document prints through LinPrinter's direct method in 62 s, no errors | Resolved |

**Lesson:** a cable that works for a minute is not cleared. Measure the link, compare with a
known-good device, and change the cable before blaming the printer, the computer or the software.
