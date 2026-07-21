"""Read-only xiCAD FAS4 distribution inspection.

This module never executes compiled AutoLISP. It recovers container metadata,
decrypts the FAS4 resource stream, and reconstructs function entrypoint evidence.
The output is evidence for source coverage, not proof that a command is headless.
"""

from __future__ import annotations

import re
import struct
from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

FAS4_HEADER = b" FAS4-FILE ; Do not change it!\r\n"
CRUNCH_MARKER = b"\n;fas4 crunch\n;"


class Fas4Error(ValueError):
    """Raised when a file is not a supported or internally consistent FAS4."""


def _decode_text(raw: bytes) -> str:
    for encoding in ("ascii", "utf-8", "cp949", "euc-kr", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


@dataclass(frozen=True)
class Fas4Function:
    name: str
    start: int
    end: int

    @property
    def byte_length(self) -> int:
        return max(0, self.end - self.start)


@dataclass(frozen=True)
class Fas4Module:
    path: Path
    file_sha256: str
    file_size: int
    symbol_slots: int
    bytecode_size: int
    resource_size: int
    resource_items: int
    crunch_date: str | None
    symbols: tuple[str, ...]
    strings: tuple[str, ...]
    functions: tuple[Fas4Function, ...]

    @property
    def command_entrypoints(self) -> tuple[str, ...]:
        names = {name.upper() for name in self.symbols if name.upper().startswith("C:")}
        names.update(fn.name.upper() for fn in self.functions if fn.name.upper().startswith("C:"))
        return tuple(sorted(names))


def _find_key(data: bytes) -> bytes | None:
    pos = data.find(CRUNCH_MARKER)
    if pos < 0:
        return None
    for random_length in range(6, 12):
        key_start = pos - random_length
        key_end = pos + len(CRUNCH_MARKER)
        length_pos = key_start - 1
        if length_pos >= 0 and data[length_pos] == key_end - key_start:
            return data[key_start:key_end]
    return None


def _decrypt_stream(encrypted: bytes, key: bytes) -> bytes:
    result = bytearray(len(encrypted))
    previous = key[0]
    key_pos = 1
    for index, value in enumerate(encrypted):
        if key_pos >= len(key):
            key_pos = 0
        current = key[key_pos]
        result[index] = value ^ current ^ previous
        previous = current
        key_pos += 1
    return bytes(result)


def _read_u16(data: bytes, pos: int) -> int:
    if pos + 2 > len(data):
        raise Fas4Error("truncated uint16")
    return struct.unpack("<H", data[pos : pos + 2])[0]


def _read_i32(data: bytes, pos: int) -> int:
    if pos + 4 > len(data):
        raise Fas4Error("truncated int32")
    return struct.unpack("<i", data[pos : pos + 4])[0]


def _resource_literals(resource: bytes) -> tuple[list[str], list[str]]:
    pos = 0
    symbols: list[str] = []
    strings: list[str] = []
    while pos < len(resource):
        opcode = resource[pos]
        if opcode in (0x14, 0x15):
            pos += 5
        elif opcode == 0x55:
            count = _read_u16(resource, pos + 1)
            pos += 3
            for _ in range(count):
                length = _read_u16(resource, pos)
                pos += 2
                if pos + length > len(resource):
                    raise Fas4Error("truncated string table")
                strings.append(_decode_text(resource[pos : pos + length]))
                pos += length
        elif opcode in (0x56, 0x5B):
            pos += 1
            while pos < len(resource):
                end = resource.find(b"\x00", pos)
                if end < 0:
                    raise Fas4Error("unterminated symbol table")
                raw = resource[pos:end]
                pos = end + 1
                if not raw:
                    break
                symbols.append(_decode_text(raw))
        elif opcode == 0x43:
            pos += 5
        elif opcode == 0x34:
            pos += 3
        elif opcode in (0x35, 0x51):
            pos += 5
        elif opcode == 0x32:
            pos += 2
        elif opcode == 0x33:
            pos += 5
        elif opcode == 0x3B:
            end = resource.find(b"\x00", pos + 1)
            if end < 0:
                raise Fas4Error("unterminated real literal")
            pos = end + 1
        elif opcode in {
            0x03,
            0x05,
            0x06,
            0x07,
            0x09,
            0x0C,
            0x0D,
            0x0E,
            0x18,
            0x19,
            0x1A,
            0x1B,
            0x37,
            0x39,
            0x3C,
            0x3D,
            0x5C,
            0x5D,
            0x5E,
        }:
            pos += 3
        elif opcode in {0x57, 0x67, 0x68, 0x69, 0x6A, 0x6B}:
            pos += 5
        elif opcode in {0x1E, 0x1F}:
            pos += 2
        else:
            pos += 1
    return symbols, strings


def _build_variable_tables(resource: bytes, symbol_slots: int) -> tuple[list[Any], list[Any]]:
    tables: dict[int, list[Any]] = {0: [None] * symbol_slots, 1: [None] * symbol_slots}
    stack: list[Any] = []
    pos = 0

    def table0(index: int) -> Any:
        return tables[0][index] if 0 <= index < symbol_slots else None

    def pop(default: Any = None) -> Any:
        return stack.pop() if stack else default

    def pop_many(count: int) -> list[Any]:
        count = min(max(count, 0), len(stack))
        if count == 0:
            return []
        values = stack[-count:]
        del stack[-count:]
        return values

    while pos < len(resource):
        opcode = resource[pos]
        if opcode in (0x00, 0x01):
            stack.append(None)
            pos += 1
        elif opcode == 0x02:
            stack.append(True)
            pos += 1
        elif opcode == 0x0A:
            if stack:
                stack.pop()
            pos += 1
        elif opcode == 0x0B:
            if stack:
                stack.append(stack[-1])
            pos += 1
        elif opcode in (0x14, 0x15):
            if pos + 5 > len(resource):
                break
            stack.append(("DEFHDR", tuple(resource[pos + 1 : pos + 5])))
            pos += 5
        elif opcode in (0x03, 0x09):
            if pos + 3 > len(resource):
                break
            index = _read_u16(resource, pos + 1)
            stack.append(table0(index))
            pos += 3
        elif opcode == 0x06:
            if pos + 3 > len(resource):
                break
            index = _read_u16(resource, pos + 1)
            if 0 <= index < symbol_slots:
                tables[0][index] = pop()
            pos += 3
        elif opcode == 0x2A:
            if len(stack) >= 2:
                right = stack.pop()
                left = stack.pop()
                stack.append(("CONS", left, right))
            pos += 1
        elif opcode == 0x28:
            value = pop()
            if isinstance(value, tuple) and len(value) == 3 and value[0] == "CONS":
                stack.append(value[1])
            elif isinstance(value, tuple) and value:
                stack.append(value[0])
            else:
                stack.append(("CAR", value))
            pos += 1
        elif opcode == 0x29:
            value = pop()
            if isinstance(value, tuple) and len(value) == 3 and value[0] == "CONS":
                stack.append(value[2])
            elif isinstance(value, tuple) and len(value) > 1:
                stack.append(tuple(value[1:]))
            else:
                stack.append(("CDR", value))
            pos += 1
        elif opcode == 0x32:
            if pos + 2 > len(resource):
                break
            stack.append(struct.unpack("<b", resource[pos + 1 : pos + 2])[0])
            pos += 2
        elif opcode == 0x33:
            if pos + 5 > len(resource):
                break
            stack.append(_read_i32(resource, pos + 1))
            pos += 5
        elif opcode == 0x39:
            if pos + 3 > len(resource):
                break
            stack.append(tuple(pop_many(_read_u16(resource, pos + 1))))
            pos += 3
        elif opcode == 0x34:
            if pos + 3 > len(resource):
                break
            argc, flags = resource[pos + 1], resource[pos + 2]
            stack.append(("EVAL", argc, flags, tuple(pop_many(argc + 1))))
            pos += 3
        elif opcode in (0x35, 0x51):
            if pos + 5 > len(resource):
                break
            argc = resource[pos + 1]
            index = _read_u16(resource, pos + 2)
            flags = resource[pos + 4]
            stack.append(("CALL", table0(index), index, flags, tuple(pop_many(argc))))
            pos += 5
        elif opcode == 0x55:
            if pos + 3 > len(resource):
                break
            count = _read_u16(resource, pos + 1)
            pos += 3
            for _ in range(count):
                if pos + 2 > len(resource):
                    pos = len(resource)
                    break
                length = _read_u16(resource, pos)
                pos += 2
                if pos + length > len(resource):
                    pos = len(resource)
                    break
                stack.append(("STRING", _decode_text(resource[pos : pos + length])))
                pos += length
        elif opcode in (0x56, 0x5B):
            pos += 1
            while pos < len(resource):
                end = resource.find(b"\x00", pos)
                if end < 0:
                    pos = len(resource)
                    break
                name = _decode_text(resource[pos:end])
                pos = end + 1
                if not name:
                    break
                stack.append(("SYMBOL", name))
        elif opcode == 0x3A:
            if len(stack) >= 3:
                name = stack.pop()
                start = stack.pop()
                module = stack.pop()
                stack.append(("FUNC", name, start, module))
            pos += 1
        elif opcode == 0x43:
            if pos + 5 > len(resource):
                break
            variable_pos = _read_u16(resource, pos + 1)
            init_count = _read_u16(resource, pos + 3)
            module_id = stack.pop() if stack else None
            table_index = 0 if module_id is None else 1
            for index in range(variable_pos + init_count - 1, variable_pos - 1, -1):
                if not stack:
                    break
                value = stack.pop()
                if 0 <= index < symbol_slots:
                    tables[table_index][index] = value
            pos += 5
        elif opcode == 0x23:
            stack.append(("NOT", pop()))
            pos += 1
        elif opcode == 0x24:
            stack.append(("ATOM", pop()))
            pos += 1
        elif opcode in {0x57, 0x67, 0x68, 0x69, 0x6A, 0x6B}:
            pos += 5
        elif opcode in {0x05, 0x07, 0x0C, 0x0D, 0x0E, 0x1A, 0x1B, 0x37, 0x3C, 0x3D, 0x5C, 0x5D, 0x5E}:
            pos += 3
        elif opcode in {0x1E, 0x1F}:
            pos += 2
        elif opcode in {0x16, 0x1C, 0x20, 0x62, 0x63}:
            pos += 1
        elif opcode == 0x3B:
            end = resource.find(b"\x00", pos + 1)
            if end < 0:
                break
            stack.append(("REAL", _decode_text(resource[pos + 1 : end])))
            pos = end + 1
        else:
            pos += 1
    return tables[0], tables[1]


def _catalog_functions(tables: Iterable[list[Any]], bytecode_size: int) -> tuple[Fas4Function, ...]:
    found: dict[int, str] = {}

    def text(value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, tuple) and len(value) == 2 and value[0] in {"STRING", "SYMBOL", "REAL"}:
            return str(value[1])
        return ""

    def walk(value: Any) -> None:
        if not isinstance(value, tuple):
            return
        if len(value) >= 4 and value[0] == "FUNC":
            name, start = text(value[1]), value[2]
            if isinstance(start, int) and 0 <= start <= bytecode_size:
                found.setdefault(start, name)
            walk(value[3])
            return
        for item in value:
            walk(item)

    for table in tables:
        for value in table:
            walk(value)
    starts = sorted(found)
    return tuple(
        Fas4Function(found[start], start, starts[index + 1] if index + 1 < len(starts) else bytecode_size)
        for index, start in enumerate(starts)
    )


def parse_fas4(path: str | Path) -> Fas4Module:
    source = Path(path)
    data = source.read_bytes()
    header_pos = data.find(FAS4_HEADER)
    if header_pos < 0:
        raise Fas4Error(f"not FAS4: {source}")
    size_start = header_pos + len(FAS4_HEADER)
    size_end = data.find(b"\r\n", size_start)
    if size_end < 0:
        raise Fas4Error("missing payload size")
    try:
        payload_size = int(data[size_start:size_end])
    except ValueError as exc:
        raise Fas4Error("invalid payload size") from exc
    payload_start = size_end + 2
    payload = data[payload_start : payload_start + payload_size]
    match = re.match(rb"(\d+) \$", payload)
    if not match:
        raise Fas4Error("missing symbol count")
    symbol_slots = int(match.group(1))
    bytecode = payload[match.end() :]
    after_payload = payload_start + payload_size
    section_match = re.search(rb"(\d+) (\d+) \$", data[after_payload:])
    resource_size = resource_items = 0
    encrypted = b""
    if section_match:
        resource_size = int(section_match.group(1))
        resource_items = int(section_match.group(2))
        resource_start = after_payload + section_match.end()
        encrypted = data[resource_start : resource_start + resource_size]
    key = _find_key(data)
    resource = _decrypt_stream(encrypted, key) if key else encrypted
    symbols, strings = _resource_literals(resource)
    tables = _build_variable_tables(resource, symbol_slots)
    functions = _catalog_functions(tables, len(bytecode))
    crunch = re.search(rb";fas4 crunch\n;\$;A([\d/]+)", data)
    return Fas4Module(
        path=source,
        file_sha256=sha256(data).hexdigest(),
        file_size=len(data),
        symbol_slots=symbol_slots,
        bytecode_size=len(bytecode),
        resource_size=resource_size,
        resource_items=resource_items,
        crunch_date=crunch.group(1).decode("ascii") if crunch else None,
        symbols=tuple(symbols),
        strings=tuple(strings),
        functions=functions,
    )
