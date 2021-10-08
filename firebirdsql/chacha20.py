##############################################################################
# Copyright (c) 2021 Hajime Nakagami<nakagami@gmail.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#  this list of conditions and the following disclaimer in the documentation
#  and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# Python DB-API 2.0 module for Firebird.
##############################################################################
import sys
import struct
import copy

sigma = b"expand 32-byte k"

PYTHON_MAJOR_VER = sys.version_info[0]


if PYTHON_MAJOR_VER == 3:
    def ord(c):
        return c


def bytes_to_int(b):        # Read as little endian.
    fmt = {1: 'B', 2: '<H', 4: '<L', 8: '<Q'}[len(b)]
    return struct.unpack(fmt, b)[0]


def int_to_bytes(val, nbytes):  # Convert int value to little endian bytes.
    v = abs(val)
    byte_array = []
    for n in range(nbytes):
        byte_array.append((v >> (8 * n)) & 0xff)
    if val < 0:
        for i in range(nbytes):
            byte_array[i] = ~byte_array[i] + 256
        byte_array[0] += 1
        for i in range(nbytes):
            if byte_array[i] == 256:
                byte_array[i] = 0
                byte_array[i+1] += 1

    if PYTHON_MAJOR_VER == 2:
        return ''.join([chr(c) for c in byte_array])
    else:
        return bytes(byte_array)


def add_u32(x, y):
    return (x + y) & 0xffffffff


def rotate_u32(x, n):
    y = x << n
    z = x >> (32 - n)
    return (y | z) & 0xffffffff


def quaterround(a, b, c, d):
    a = add_u32(a, b)
    d ^= a
    d = rotate_u32(d, 16)

    c = add_u32(c, d)
    b ^= c
    b = rotate_u32(b, 12)

    a = add_u32(a, b)
    d ^= a
    d = rotate_u32(d, 8)

    c = add_u32(c, d)
    b ^= c
    b = rotate_u32(b, 7)

    return a, b, c, d


class ChaCha20:
    def __init__(self, key, nonce, pos=0):
        pos_len = 16 - len(nonce)
        assert len(key) == 32
        assert pos_len == 4 or pos_len == 8
        pos_bytes = int_to_bytes(pos, pos_len)
        block_bytes = sigma + key + pos_bytes + nonce
        assert len(block_bytes) == 64

        block = []
        for i in range(0, len(block_bytes), 4):
            block.append(bytes_to_int(block_bytes[i:i+4]))
        self.block = block
        self.xor_table = self.chacha20_round_bytes()
        self.xor_table_pos = 0
        self.pos_len = pos_len

    def chacha20_round_bytes(self):
        x = copy.copy(self.block)

        for i in range(10):
            # column rounds
            x[0], x[4], x[8], x[12] = quaterround(x[0], x[4], x[8], x[12])
            x[1], x[5], x[9], x[13] = quaterround(x[1], x[5], x[9], x[13])
            x[2], x[6], x[10], x[14] = quaterround(x[2], x[6], x[10], x[14])
            x[3], x[7], x[11], x[15] = quaterround(x[3], x[7], x[11], x[15])
            # diagonal rounds
            x[0], x[5], x[10], x[15] = quaterround(x[0], x[5], x[10], x[15])
            x[1], x[6], x[11], x[12] = quaterround(x[1], x[6], x[11], x[12])
            x[2], x[7], x[8], x[13] = quaterround(x[2], x[7], x[8], x[13])
            x[3], x[4], x[9], x[14] = quaterround(x[3], x[4], x[9], x[14])

        for i in range(16):
            x[i] = add_u32(x[i], self.block[i])

        return b''.join([int_to_bytes(i, 4) for i in x])

    def translate(self, plain):
        enc = b''

        for i in range(len(plain)):
            ord(plain[i]) ^ ord(self.xor_table[self.xor_table_pos])
            if PYTHON_MAJOR_VER == 3:
                enc += bytes([ord(plain[i]) ^ ord(self.xor_table[self.xor_table_pos])])
            else:
                enc += chr(ord(plain[i]) ^ ord(self.xor_table[self.xor_table_pos]))
            self.xor_table_pos += 1
            if len(self.xor_table) == self.xor_table_pos:
                self.block[12] = add_u32(self.block[12], 1)
                if self.pos_len == 8 and self.block[12] == 0:
                    self.block[13] = add_u32(self.block[13], 1)
                self.xor_table = self.chacha20_round_bytes()
                self.xor_table_pos = 0

        return enc

    # PyCrypto compatible method
    @staticmethod
    def new(key, nonce):
        return ChaCha20(key, nonce)
    encrypt = translate
    decrypt = translate