"""
CUPS backend (method P2)
The system print spooler: permanent queues and the driverless queues CUPS
creates on demand (e.g. "Canon_TR150_series_USB"). Used when direct IPP isn't
possible, and for printers that need a CUPS driver (Gutenprint, HPLIP, vendor
PPDs). Only local USB queues are used: network queues are skipped
(NETWORK_PRINTING is off).

Commands: lpstat (destinations, jobs, state), lp (submit), cancel.
"""

import os
import re
import shutil
import subprocess
import time
import urllib.parse

from backends.backend_base import PrintError
from modules.manager_render import render_pdf
from utils.util_logging import get_logger

log = get_logger("cups")

QUALITY_ENUM = {"draft": 3, "normal": 4, "high": 5}


def _run(args, timeout=20):
    """Run a CUPS command; PrintError if CUPS isn't available"""
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            env=dict(os.environ, LC_ALL="C"),
        )
    except FileNotFoundError:
        raise PrintError("CUPS isn't installed (package cups-client).", "unreachable")
    except subprocess.SubprocessError as e:
        raise PrintError(f"CUPS didn't answer ({e}).", "unreachable")


def is_local_uri(uri):
    """True for USB queues: usb://, ipp-usb driverless ("(USB)" in the DNS-SD name), or loopback"""
    text = urllib.parse.unquote(uri)
    host = urllib.parse.urlsplit(uri).hostname or ""
    return uri.startswith("usb:") or "(USB)" in text or host.startswith("127.") or host == "localhost"


def parse_destinations(text):
    """[(queue, uri)] from `lpstat -l -e` output ("name type info uri")"""
    out = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and "://" in parts[-1]:
            out.append((parts[0], parts[-1]))
    return out


def parse_device_uris(text):
    """[(queue, uri)] from `lpstat -v` output ("device for NAME: URI")"""
    return re.findall(r"^device for (\S+):\s+(\S+)", text, re.M)


def queue_model(queue):
    """A readable model name from a queue name (e.g. "Canon TR150 series")"""
    name = re.sub(r"_USB$", "", queue)
    return name.replace("_", " ").strip()


def parse_jobs(text):
    """[{id, name, user, size}] from `lpstat -o` lines ("Queue-12 user 1024 Mon 22 Sep ...")"""
    jobs = []
    for line in text.splitlines():
        m = re.match(r"^(\S+-(\d+))\s+(\S+)\s+(\d+)\s+(.*)$", line)
        if m:
            jobs.append(
                {
                    "id": m.group(1),
                    "number": int(m.group(2)),
                    "user": m.group(3),
                    "size": int(m.group(4)),
                    "when": m.group(5),
                }
            )
    return jobs


def lp_options(ticket):
    """lp -o options for a ticket (standard IPP job-attribute names that CUPS accepts)"""
    opts = [
        f"print-color-mode={ticket.get('color', 'color')}",
        f"print-quality={QUALITY_ENUM.get(ticket.get('quality'), 4)}",
        f"media={ticket['size']}",
        "print-scaling=none",  # LinPrinter already fitted the pages
    ]
    if ticket.get("type"):
        opts.append(f"media-type={ticket['type']}")
    return opts


class CupsBackend:
    """Local CUPS queues (USB only)"""

    name = "cups"
    code = "P2"

    def available(self):
        """True if the CUPS client tools are installed"""
        return bool(shutil.which("lp") and shutil.which("lpstat"))

    def list_printers(self):
        """[(queue, uri)] of local USB queues, permanent and driverless"""
        if not self.available():
            return []
        seen, out = set(), []
        for queue, uri in parse_destinations(_run(["lpstat", "-l", "-e"]).stdout) + parse_device_uris(
            _run(["lpstat", "-v"]).stdout
        ):
            if queue in seen:
                continue
            seen.add(queue)
            if is_local_uri(uri):
                out.append((queue, uri))
            else:
                log.info("skipped network queue %s (network printing is off)", queue)
        return out

    def submit(self, queue, ticket, caps, pdf, pages, work_dir, job_name):
        """Render the chosen pages to PDF and hand them to CUPS; returns the CUPS job id"""
        os.makedirs(work_dir, exist_ok=True)
        path = os.path.join(work_dir, f"job-{int(time.time() * 1000)}.pdf")
        render_pdf(pdf, pages, ticket, path)
        args = ["lp", "-d", queue, "-t", job_name[:120], "-n", str(max(1, int(ticket.get("copies", 1))))]
        for opt in lp_options(ticket):
            args += ["-o", opt]
        r = _run([*args, path], timeout=120)
        m = re.search(r"request id is (\S+)", r.stdout)
        if r.returncode != 0 or not m:
            message = (r.stderr or r.stdout).strip()
            log.warning("lp failed (%s): %s", r.returncode, message)
            code = "unreachable" if "not exist" in message or "Unable to connect" in message else "rejected"
            raise PrintError(f"CUPS didn't accept the job: {message or 'no reason given'}", code)
        log.info("CUPS job %s on %s", m.group(1), queue)
        return m.group(1)

    def jobs(self, queue, which="not-completed"):
        """Jobs in a queue: [{id, name, state, done}]"""
        args = ["lpstat", "-o", queue] if which != "completed" else ["lpstat", "-W", "completed", "-o", queue]
        return [
            {
                "id": j["id"],
                "name": j["id"],
                "state": "completed" if which == "completed" else "pending",
                "done": 0,
                "created": 0,
            }
            for j in parse_jobs(_run(args).stdout)
        ]

    def job(self, queue, job_id):
        """(state, pages done, reasons): pending while listed, completed once gone"""
        waiting = any(j["id"] == job_id for j in parse_jobs(_run(["lpstat", "-o", queue]).stdout))
        return ("processing" if waiting else "completed"), 0, []

    def cancel(self, queue, job_id):
        """Cancel a CUPS job"""
        r = _run(["cancel", str(job_id)])
        if r.returncode != 0:
            raise PrintError(f"CUPS couldn't cancel the job: {r.stderr.strip()}", "rejected")

    def status(self, queue):
        """(state, reasons, markers) from `lpstat -p` (CUPS has no ink levels for most queues)"""
        text = _run(["lpstat", "-p", queue]).stdout
        state = (
            "processing"
            if "printing" in text or "now printing" in text
            else "stopped" if "disabled" in text else "idle"
        )
        return state, [], []
