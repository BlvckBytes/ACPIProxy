"""
Translate a list of bytes as hex strings to an ascii word by
only looking at the actual ACPI name and skipping the preamble
"""
def hexbytes_to_ascii_name(bytes):
  return ''.join([chr(int(x, 16)) for x in bytes[-4:]])
