import os
import bitstring
import math
import base64
import sys

from enum import Enum

class FieldType(Enum):
    INTEGER = "i"
    FLOAT = "f"
    STRING = "s"
    ENUM = "e"

class Field:
    def __init__(self, name: str, type: FieldType, value: any):
        self.name: str = name
        self.type: FieldType = type
        self.value: any = value
    
    def encode(self, input: str) -> bytes:
        match self.type:
            case FieldType.INTEGER:
                value: int = int(input)
                return bitstring.pack(f"int:{self.value}", value).tobytes()
            case FieldType.FLOAT:
                value: float = float(input)
                return bitstring.pack(f"float:{self.value}", value).tobytes()
            case FieldType.STRING:
                value: str = input + '\0'
                return bitstring.pack(f"bytes:{len(value)}", value.encode("utf-8")).tobytes()
            case FieldType.ENUM:
                if input not in self.value:
                    raise Exception("invalid enum value, expected: (" + ", ".join(self.value) + "), but got '" + input + "'")
                bits = math.ceil(math.log2(len(self.value) + 1))
                return bitstring.pack(f"uint:{bits}", self.value.index(input)).tobytes()

    def decode(self, input: bytes, offset: int = 0) -> any:
        stream = bitstring.BitStream(bytes=input[offset:])
        match self.type:
            case FieldType.INTEGER: return stream.unpack(f"int:{self.value}")[0]
            case FieldType.FLOAT: return stream.unpack(f"float:{self.value}")[0]
            case FieldType.STRING:
                zero_at = input[offset:].index(0)
                stream = bitstring.BitStream(bytes=input[offset:offset+zero_at])
                return stream.bytes.decode("utf-8")
            case FieldType.ENUM:
                bits = math.ceil(math.log2(len(self.value) + 1))
                return self.value[stream.unpack(f"uint:{bits}")[0]]

    def size(self) -> int:
        match self.type:
            case FieldType.INTEGER: return self.value / 8
            case FieldType.FLOAT: return self.value / 8
            case FieldType.STRING: return 0
            case FieldType.ENUM: return math.ceil(math.log2(len(self.value) + 1) / 8)
        raise Exception("Unknown field type")

class Form:
    def __init__(self):
        self.fields: dict[str, Field] = []

    def add_field(self, field: Field):
        self.fields.append(field)

    def create_field(self, name: str, type: FieldType, value: any):
        self.add_field(Field(name, type, value))

    def encode(self):
        value: bytes = b""
        for field in self.fields:
            if field.type == FieldType.ENUM:
                items = ", ".join(field.value)
                value += field.encode(input(f"{field.name}({items}): "))
            else:
                value += field.encode(input(f"{field.name}: "))
        return value

    def decode(self, input: str):
        obj = {}
        offset: int = 0
        for field in self.fields:
            obj[field.name] = field.decode(input, offset)
            if field.type == FieldType.STRING:
                offset += len(obj[field.name]) + 1
            else:
                offset += int(field.size())
        return obj

class FormParser:
    def __init__(self):
        self.source: str = ""
        self.length: int = 0
        self.cursor: int = 0
        self.char: str = ""
    
    def parse_form(self, codeform: str) -> Form:
        self.source = codeform
        self.length = len(codeform)
        self.cursor = 0
        self.char = codeform[self.cursor]

        form = Form()

        while self.cursor < self.length:
            field_name = self.collect_word()
            self.expect(":")
            (field_type, field_value) = self.collect_type_and_value()
            form.create_field(field_name, field_type, field_value)

            if self.char != ",":
                break
            else:
                self.advance()

        return form

    def expect(self, char: str):
        if self.char == char:
            self.advance()
        else:
            raise Exception(f"expected {char} at position {self.cursor} but got '{self.char}'")

    def advance(self):
        self.cursor += 1
        if self.cursor < self.length:
            self.char = self.source[self.cursor]
        else:
            self.char = '\0'

    def collect_word(self):
        start: int = self.cursor

        if not self.char.isalpha():
            raise Exception(f"word must start with a letter. got '{self.char}' at position {self.cursor}")
        
        while self.char.isalnum() or self.char == "_":
            self.advance()
        
        return self.source[start:self.cursor]
    
    def collect_type_and_value(self):
        match self.char:
            case "i": self.advance(); return (FieldType.INTEGER, self.collect_bitsize_integer())
            case "f": self.advance(); return (FieldType.FLOAT, self.collect_bitsize_float())
            case "s": self.advance(); return (FieldType.STRING, None)
            case "e": self.advance(); return (FieldType.ENUM, self.collect_enum())
            case _:
                raise Exception(f"expected type (i, f, s, e) at position {self.cursor} but got '{self.char}'")
    
    def collect_integer(self):
        start: int = self.cursor
        while self.char.isnumeric():
            self.advance()
        return int(self.source[start:self.cursor])

    def collect_bitsize_integer(self):
        if self.char.isnumeric():
            bitsize: int = int(self.collect_integer())
            if bitsize not in [8, 16, 32, 64]:
                raise Exception(f"expected bitsize (8, 16, 32, 64) at position {self.cursor} but got '{bitsize}'")
            return bitsize
        else:
            return 8

    def collect_bitsize_float(self):
        if self.char.isnumeric():
            bitsize: int = int(self.collect_integer())
            if bitsize not in [32, 64]:
                raise Exception(f"expected bitsize (32, 64) at position {self.cursor} but got '{bitsize}'")
            return bitsize
        else:
            return 32
    
    def collect_enum(self):
        self.expect("[")
        items = []

        while True:
            items.append(self.collect_word())
            if self.char != ";":
                self.expect(",")
            else:
                self.advance()
                break

        return items
    
    def collect_integer(self):
        start: int = self.cursor
        while self.char.isnumeric():
            self.advance()
        return self.source[start:self.cursor]
    
    def collect_float(self):
        start: int = self.cursor
        while self.char.isnumeric() or self.char == ".":
            self.advance()

def main():
    form = sys.argv[1] if len(sys.argv) > 1 else input("input form: ")
    
    try:
        form = FormParser().parse_form(form)
    except Exception as e:
        print(f"\x1b[31m[Error]: {e}\x1b[0m")
        return

    try:
        operation = input("select operation (e/encode), (d/decode): ")
        if len(operation) == 0:
            return

        if operation == "encode" or operation == "e":
            value = base64.encodebytes(form.encode()).decode("utf-8")
            print(f"encoded form: \x1b[32m{value}\x1b[0m")
        elif operation == "decode" or operation == "d":
            value = input("input encoded form: ")
            value = base64.decodebytes(value.encode())
            value = form.decode(value)
            for k, v in value.items():
                print(f"\x1b[32m{k}: {v}\x1b[0m")
        else:
            raise Exception("invalid operation")
    except Exception as e:
        print(f"\x1b[31m[Error]: {e}\x1b[0m")
        main()
    finally:
        pass

if __name__ == "__main__":
    main()