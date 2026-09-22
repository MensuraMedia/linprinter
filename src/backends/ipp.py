"""
IPP (Internet Printing Protocol) codec and client, standard library only.

Encoding follows RFC 8010 (binary message format); operations and attributes
follow RFC 8011 and PWG 5100.x (IPP Everywhere). Only what LinPrinter needs:

  Get-Printer-Attributes, Validate-Job, Print-Job, Get-Jobs,
  Get-Job-Attributes, Cancel-Job, Identify-Printer

Attributes are written as (name, tag, values). Values are Python values; a
collection's value is a list of member attributes in the same form. Decoded
responses become dicts: {name: value} (single value) or {name: [values]}
(several), with collections as dicts.
"""

import http.client
import os
import struct
import urllib.parse
from collections import OrderedDict

# -- tags (RFC 8010 §3.5) ------------------------------------------------------
OPERATION, JOB, END, PRINTER, UNSUPPORTED_GROUP = 0x01, 0x02, 0x03, 0x04, 0x05
GROUP_TAGS = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07}
OUT_OF_BAND = {0x10: "unsupported", 0x12: "unknown", 0x13: "no-value"}
INTEGER, BOOLEAN, ENUM = 0x21, 0x22, 0x23
OCTET, DATETIME, RESOLUTION, RANGE = 0x30, 0x31, 0x32, 0x33
BEG_COLLECTION, TEXT_LANG, NAME_LANG, END_COLLECTION = 0x34, 0x35, 0x36, 0x37
TEXT, NAME, KEYWORD, URI, URI_SCHEME, CHARSET, LANGUAGE, MIME, MEMBER = (
    0x41,
    0x42,
    0x44,
    0x45,
    0x46,
    0x47,
    0x48,
    0x49,
    0x4A,
)
STRING_TAGS = {TEXT, NAME, KEYWORD, URI, URI_SCHEME, CHARSET, LANGUAGE, MIME, MEMBER, OCTET}

# -- operations (RFC 8011 §5.2, PWG 5100.13) -----------------------------------
PRINT_JOB, VALIDATE_JOB, CANCEL_JOB = 0x0002, 0x0004, 0x0008
GET_JOB_ATTRIBUTES, GET_JOBS, GET_PRINTER_ATTRIBUTES = 0x0009, 0x000A, 0x000B
IDENTIFY_PRINTER = 0x003C
OPERATION_NAMES = {
    PRINT_JOB: "Print-Job",
    VALIDATE_JOB: "Validate-Job",
    CANCEL_JOB: "Cancel-Job",
    GET_JOB_ATTRIBUTES: "Get-Job-Attributes",
    GET_JOBS: "Get-Jobs",
    GET_PRINTER_ATTRIBUTES: "Get-Printer-Attributes",
    IDENTIFY_PRINTER: "Identify-Printer",
}

# job-state (RFC 8011 §5.3.7) and printer-state (§5.4.11)
JOB_STATES = {
    3: "pending",
    4: "pending-held",
    5: "processing",
    6: "processing-stopped",
    7: "canceled",
    8: "aborted",
    9: "completed",
}
PRINTER_STATES = {3: "idle", 4: "processing", 5: "stopped"}
QUALITY = {"draft": 3, "normal": 4, "high": 5}


class IppError(Exception):
    """An IPP request failed: status code, message and a short code for the UI"""

    def __init__(self, message, status=None, code="error"):
        super().__init__(message)
        self.status = status
        self.code = code  # "unreachable" | "rejected" | "unsupported" | "busy" | "error"


# -- encoding -------------------------------------------------------------------
def _value(tag, value):
    """Bytes of one attribute value"""
    if tag in (INTEGER, ENUM):
        return struct.pack(">i", int(value))
    if tag == BOOLEAN:
        return b"\x01" if value else b"\x00"
    if tag == RANGE:
        return struct.pack(">ii", int(value[0]), int(value[1]))
    if tag == RESOLUTION:
        x, y, units = value if len(value) == 3 else (value[0], value[1], 3)
        return struct.pack(">iib", int(x), int(y), int(units))
    if tag == DATETIME:  # 11 bytes (RFC 8010 §3.9); decoded values are kept as hex
        return bytes.fromhex(value) if isinstance(value, str) else bytes(value)
    if tag in STRING_TAGS or tag in (TEXT_LANG, NAME_LANG):
        return value if isinstance(value, bytes) else str(value).encode("utf-8")
    if tag in OUT_OF_BAND:
        return b""
    raise ValueError(f"cannot encode IPP value tag 0x{tag:02x}")


def _attribute(name, tag, values):
    """Bytes of one attribute with its values (additional values have an empty name)"""
    if tag in (RANGE, RESOLUTION):  # one value is itself a pair / triple of numbers
        values = [values] if values and not isinstance(values[0], (list, tuple)) else list(values)
    else:
        values = list(values) if isinstance(values, (list, tuple)) else [values]
    out = bytearray()
    for i, v in enumerate(values):
        n = name.encode("utf-8") if i == 0 else b""
        if tag == BEG_COLLECTION:
            out += struct.pack(">bh", BEG_COLLECTION, len(n)) + n + struct.pack(">h", 0)
            for mname, mtag, mvalues in v:
                m = mname.encode("utf-8")
                out += struct.pack(">bh", MEMBER, 0) + struct.pack(">h", len(m)) + m
                sub = _attribute("", mtag, mvalues)
                out += sub
            out += struct.pack(">bhh", END_COLLECTION, 0, 0)
        else:
            data = _value(tag, v)
            out += struct.pack(">bh", tag, len(n)) + n + struct.pack(">h", len(data)) + data
    return bytes(out)


def encode_request(operation, request_id, groups):
    """An IPP request: groups is [(group tag, [(name, tag, values), ...]), ...]"""
    out = bytearray(struct.pack(">bbhi", 2, 0, operation, request_id))
    for group, attrs in groups:
        out.append(group)
        for name, tag, values in attrs:
            out += _attribute(name, tag, values)
    out.append(END)
    return bytes(out)


def encode_response(status, request_id, groups):
    """An IPP response (used by the test printer)"""
    out = bytearray(struct.pack(">bbhi", 2, 0, status, request_id))
    for group, attrs in groups:
        out.append(group)
        for name, tag, values in attrs:
            out += _attribute(name, tag, values)
    out.append(END)
    return bytes(out)


# -- decoding -------------------------------------------------------------------
def _decode_value(tag, data):
    """Python value of one attribute value"""
    if tag in (INTEGER, ENUM):
        return struct.unpack(">i", data)[0]
    if tag == BOOLEAN:
        return data != b"\x00"
    if tag == RANGE:
        return tuple(struct.unpack(">ii", data))
    if tag == RESOLUTION:
        return tuple(struct.unpack(">iib", data))
    if tag == DATETIME:
        return data.hex()
    if tag in (TEXT_LANG, NAME_LANG):  # 2-byte lang length, lang, 2-byte text length, text
        n = struct.unpack(">h", data[:2])[0]
        m = struct.unpack(">h", data[2 + n : 4 + n])[0]
        return data[4 + n : 4 + n + m].decode("utf-8", "replace")
    if tag in OUT_OF_BAND:
        return None
    if tag == OCTET:
        return data.decode("utf-8", "replace")
    return data.decode("utf-8", "replace")


def _add(target, name, value):
    """Store a value: single values stay single, repeats become a list"""
    if name not in target:
        target[name] = value
    elif isinstance(target[name], list) and getattr(target[name], "_multi", False):
        target[name].append(value)
    else:
        multi = _Multi([target[name], value])
        target[name] = multi


class _Multi(list):
    """A list of several values of one attribute (a real list value, not a list of lists)"""

    _multi = True


def _read_collection(data, pos):
    """Decode collection members after a begCollection value; returns (dict, new position)"""
    result, member = OrderedDict(), None
    while pos < len(data):
        tag = data[pos]
        nlen = struct.unpack(">h", data[pos + 1 : pos + 3])[0]
        pos += 3 + nlen
        vlen = struct.unpack(">h", data[pos : pos + 2])[0]
        value = data[pos + 2 : pos + 2 + vlen]
        pos += 2 + vlen
        if tag == END_COLLECTION:
            return result, pos
        if tag == MEMBER:
            member = value.decode("utf-8", "replace")
            continue
        if tag == BEG_COLLECTION:
            sub, pos = _read_collection(data, pos)
            _add(result, member, sub)
        else:
            _add(result, member, _decode_value(tag, value))
    return result, pos


def decode_message(data):
    """(status or operation, request id, [(group tag, {name: value}), ...])"""
    if len(data) < 9:
        raise IppError("The printer sent an empty or short answer.", code="error")
    _major, _minor, code, request_id = struct.unpack(">bbhi", data[:8])
    pos, groups, current, last = 8, [], None, None
    while pos < len(data):
        tag = data[pos]
        if tag in GROUP_TAGS:
            pos += 1
            if tag == END:
                break
            current = OrderedDict()
            groups.append((tag, current))
            continue
        nlen = struct.unpack(">h", data[pos + 1 : pos + 3])[0]
        name = data[pos + 3 : pos + 3 + nlen].decode("utf-8", "replace")
        pos += 3 + nlen
        vlen = struct.unpack(">h", data[pos : pos + 2])[0]
        value = data[pos + 2 : pos + 2 + vlen]
        pos += 2 + vlen
        if nlen:
            last = name
        if current is None:
            continue
        if tag == BEG_COLLECTION:
            coll, pos = _read_collection(data, pos)
            _add(current, last, coll)
        else:
            _add(current, last, _decode_value(tag, value))
    return code, request_id, groups


def values(attrs, name):
    """An attribute's values as a list (empty if missing)"""
    v = attrs.get(name)
    if v is None:
        return []
    return list(v) if isinstance(v, _Multi) else [v]


# -- client ---------------------------------------------------------------------
def _base_operation_attrs(uri, requesting_user="linprinter"):
    """The operation attributes every request starts with"""
    return [
        ("attributes-charset", CHARSET, "utf-8"),
        ("attributes-natural-language", LANGUAGE, "en"),
        ("printer-uri", URI, uri),
        ("requesting-user-name", NAME, requesting_user),
    ]


def status_text(status):
    """Plain name of an IPP status code"""
    return {
        0x0000: "successful-ok",
        0x0001: "successful-ok-ignored-or-substituted-attributes",
        0x0002: "successful-ok-conflicting-attributes",
        0x0400: "client-error-bad-request",
        0x040B: "client-error-attributes-or-values-not-supported",
        0x040A: "client-error-document-format-not-supported",
        0x0406: "client-error-not-found",
        0x0500: "server-error-internal-error",
        0x0501: "server-error-operation-not-supported",
        0x0506: "server-error-not-accepting-jobs",
        0x0507: "server-error-busy",
    }.get(status, f"0x{status:04x}")


class IppClient:
    """Talks IPP to one printer URI (only loopback addresses: USB printers through ipp-usb)"""

    def __init__(self, uri, timeout=15):
        """uri: e.g. ipp://127.0.0.1:60000/ipp/print"""
        parts = urllib.parse.urlsplit(uri)
        self.uri = uri
        self.host = parts.hostname or "127.0.0.1"
        self.port = parts.port or 631
        self.path = parts.path or "/ipp/print"
        self.timeout = timeout
        self._request_id = 0

    def _next_id(self):
        """A new request id"""
        self._request_id += 1
        return self._request_id

    def request(self, operation, groups, document=None, timeout=None):
        """Send a request (optionally streaming a document file); returns (status, groups)"""
        body = encode_request(operation, self._next_id(), groups)
        size = len(body) + (os.path.getsize(document) if document else 0)
        try:
            conn = http.client.HTTPConnection(self.host, self.port, timeout=timeout or self.timeout)
            conn.putrequest("POST", self.path)
            conn.putheader("Content-Type", "application/ipp")
            conn.putheader("Content-Length", str(size))
            conn.endheaders()
            conn.send(body)
            if document:
                with open(document, "rb") as f:
                    while True:
                        chunk = f.read(1 << 16)
                        if not chunk:
                            break
                        conn.send(chunk)
            response = conn.getresponse()
            data = response.read()
            conn.close()
        except (OSError, http.client.HTTPException) as e:
            raise IppError(f"The printer didn't answer ({e}).", code="unreachable")
        if response.status != 200:
            raise IppError(f"The printer answered HTTP {response.status}.", code="error")
        status, _rid, groups_out = decode_message(data)
        return status, groups_out

    def _ok(self, operation, status, groups):
        """Raise IppError unless the status is successful"""
        if status >= 0x0400:
            code = {0x040B: "unsupported", 0x040A: "unsupported", 0x0507: "busy", 0x0506: "busy"}.get(
                status, "rejected"
            )
            reason = ""
            for tag, attrs in groups:
                if tag == OPERATION and attrs.get("status-message"):
                    reason = f": {attrs['status-message']}"
            raise IppError(
                f"{OPERATION_NAMES.get(operation, operation)} failed ({status_text(status)}){reason}",
                status,
                code,
            )

    @staticmethod
    def _group(groups, tag):
        """Merged attributes of one group tag"""
        out = OrderedDict()
        for t, attrs in groups:
            if t == tag:
                out.update(attrs)
        return out

    def get_printer_attributes(self, requested=("all", "media-col-database")):
        """All printer attributes as {name: value}"""
        ops = _base_operation_attrs(self.uri) + [("requested-attributes", KEYWORD, list(requested))]
        status, groups = self.request(GET_PRINTER_ATTRIBUTES, [(OPERATION, ops)])
        self._ok(GET_PRINTER_ATTRIBUTES, status, groups)
        return self._group(groups, PRINTER)

    def validate_job(self, job_attrs, document_format):
        """Check a job ticket; returns (status, unsupported attributes)"""
        ops = _base_operation_attrs(self.uri) + [("document-format", MIME, document_format)]
        status, groups = self.request(VALIDATE_JOB, [(OPERATION, ops), (JOB, job_attrs)])
        self._ok(VALIDATE_JOB, status, groups)
        return status, self._group(groups, UNSUPPORTED_GROUP)

    def print_job(self, path, document_format, job_attrs, job_name="LinPrinter job", timeout=600):
        """Send a document; returns the job attributes (job-id, job-state, ...)"""
        ops = _base_operation_attrs(self.uri) + [
            ("job-name", NAME, job_name[:255]),
            ("document-format", MIME, document_format),
        ]
        status, groups = self.request(
            PRINT_JOB, [(OPERATION, ops), (JOB, job_attrs)], document=path, timeout=timeout
        )
        self._ok(PRINT_JOB, status, groups)
        return self._group(groups, JOB)

    def get_jobs(self, which="not-completed", limit=50):
        """Jobs on the printer: [{job-id, job-name, job-state, ...}]"""
        ops = _base_operation_attrs(self.uri) + [
            ("which-jobs", KEYWORD, which),
            ("limit", INTEGER, limit),
            (
                "requested-attributes",
                KEYWORD,
                [
                    "job-id",
                    "job-name",
                    "job-state",
                    "job-state-reasons",
                    "job-impressions-completed",
                    "time-at-creation",
                    "time-at-completed",
                ],
            ),
        ]
        status, groups = self.request(GET_JOBS, [(OPERATION, ops)])
        self._ok(GET_JOBS, status, groups)
        return [dict(attrs) for tag, attrs in groups if tag == JOB]

    def get_job(self, job_id):
        """One job's attributes"""
        ops = _base_operation_attrs(self.uri) + [("job-id", INTEGER, int(job_id))]
        status, groups = self.request(GET_JOB_ATTRIBUTES, [(OPERATION, ops)])
        self._ok(GET_JOB_ATTRIBUTES, status, groups)
        return self._group(groups, JOB)

    def cancel_job(self, job_id):
        """Cancel a job"""
        ops = _base_operation_attrs(self.uri) + [("job-id", INTEGER, int(job_id))]
        status, groups = self.request(CANCEL_JOB, [(OPERATION, ops)])
        self._ok(CANCEL_JOB, status, groups)

    def identify(self, action="flash"):
        """Make the printer identify itself (flash its lights / beep)"""
        ops = _base_operation_attrs(self.uri) + [("identify-actions", KEYWORD, action)]
        status, groups = self.request(IDENTIFY_PRINTER, [(OPERATION, ops)])
        self._ok(IDENTIFY_PRINTER, status, groups)


def decode_typed(data):
    """[(group tag, [(name, tag, values), ...]), ...] keeping IPP value tags (for fixtures / the test printer)"""
    pos, groups, current = 8, [], None

    def read_value(p):
        tag = data[p]
        nlen = struct.unpack(">h", data[p + 1 : p + 3])[0]
        name = data[p + 3 : p + 3 + nlen].decode("utf-8", "replace")
        p += 3 + nlen
        vlen = struct.unpack(">h", data[p : p + 2])[0]
        return tag, name, data[p + 2 : p + 2 + vlen], p + 2 + vlen

    def read_collection(p):
        members, member = [], None
        while p < len(data):
            tag, _n, value, p = read_value(p)
            if tag == END_COLLECTION:
                return members, p
            if tag == MEMBER:
                member = [value.decode("utf-8", "replace"), None, []]
                members.append(member)
                continue
            if tag == BEG_COLLECTION:
                sub, p = read_collection(p)
                member[1] = BEG_COLLECTION
                member[2].append(sub)
            else:
                member[1] = tag
                member[2].append(_decode_value(tag, value))
        return members, p

    while pos < len(data):
        tag = data[pos]
        if tag in GROUP_TAGS:
            pos += 1
            if tag == END:
                break
            current = []
            groups.append((tag, current))
            continue
        tag, name, value, pos = read_value(pos)
        if tag == BEG_COLLECTION:
            coll, pos = read_collection(pos)
            value = coll
        else:
            value = _decode_value(tag, value)
        if name:
            current.append([name, tag, [value]])
        elif current:
            current[-1][2].append(value)
    return groups
