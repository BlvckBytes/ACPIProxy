import sys
import re
import os
import subprocess
from shutil import copy, which

"""
Check that the required tool exists on the machine
"""
def tool_exists(name):
  return which(name) is not None

"""
Validate that all required files and folders exist within the
OC folder at the provided path
"""
def validate_oc_folder(path):
  # ACPI folder has to exist
  if not os.path.isdir(os.path.join(path, 'ACPI')):
    return False

  # config.plist has to exist
  if not os.path.exists(os.path.join(path, 'config.plist')):
    return False

  # Matches criteria
  return True

"""
Disassembles the provided AML and returns the file path
"""
def disassemble_acpi(path):
  # Create a carbon copy of this file to /tmp
  cc = copy(path, '/tmp')

  # Disassemble, result will also be saved in /tmp
  if subprocess.run(['iasl', '-da', cc], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
    print('Could not disassemble the provided AML file!')
    sys.exit()

  # Return path of disassembled file
  return cc.rsplit('.', 1)[0] + '.dsl'

"""
Check whether or not this character is a valid
acpi name ascii character
"""
def is_valid_acpiname_char(dec_ascii):
  return (
    (dec_ascii >= 65 and dec_ascii <= 90) or # A-Z
    (dec_ascii >= 97 and dec_ascii <= 122) or # a-z
    (dec_ascii >= 48 and dec_ascii <= 57) or # 0-9
    (dec_ascii == 95) # _
  )

"""
Find all method declarations as byte-sequences within a
binary AML file according to this algorithm:

https://wiki.osdev.org/AML
Wait for 0x14 (MethodOp)

https://github.com/KevinOConnor/seabios/blob/master/src/fw/acpi.c (u8* encodeLen)
Shift next byte >> 6, this is the amount of length bytes, zero based
Collect those bytes

Then 4 bytes of method name
If a byte is a non-allowed char, reset to last char and try again
Finish method (push & reset)
"""
def find_method_declarations(dsdt):
  results = []

  buf = [] # Method byte-buffer
  numread = 0 # How many bytes left to read
  read_len = True # Whether or not reading length

  # Read file binary
  with open(dsdt, "rb") as aml:
    data = None
    while True:
      # Save previous pointer position for resets
      prevpos = aml.tell()
      data = aml.read(1).hex().upper()

      # EOF, file done
      if data == '':
        break

      # Parse hex to dec
      intrepr = int(data, 16)

      # Wait for a method to begin
      if len(buf) == 0 and data != '14':
        continue

      # Just read in opcode
      buf.append(data)
      if len(buf) == 1:
        continue

      # First byte after opcode, this dictates amount of length bytes
      if len(buf) == 2:
        # Figure out how many length bytes remain and set flag
        numread = intrepr >> 6
        read_len = numread > 0
        
        # No more length to read, directly jump to name
        if numread == 0:
          numread = 4
        continue

      # Not a valid acpi name char, re-set and search again
      if not read_len and not is_valid_acpiname_char(intrepr):
        buf = []
        aml.seek(prevpos)
        continue

      # Read remaining bytes
      if numread > 1:
        numread = numread - 1
        continue

      else:
        # Read name finished, finish method
        if not read_len:
          results.append(buf)
          buf = []
          continue

        # Read length finished, read in name
        numread = 4
        read_len = False
        continue

  return results

"""
+ => any number
! => any number or _
- => any letter
@ => any letter or _
? => any number or letter
* => any number or letter or _
"""
def translate_pattern_char(char):
  if char == '+':
    return '[0-9]'
  if char == '!':
    return '[0-9_]'
  if char == '-':
    return '[A-Z]'
  if char == '@':
    return '[A-Z_]'
  if char == '?':
    return '[A-Z0-9]'
  if char == '*':
    return '[A-Z0-9_]'
  return char

"""
Compile a custom made pattern into a regex ready to
be evaluated against strings
"""
def compile_custom_pattern(pattern):
  return re.compile(''.join([translate_pattern_char(x) for x in pattern]))

"""
Check if a single method declaration's name is
matching the provided name pattern
"""
def is_declaration_matching(declaration, pattern):
  name = ''.join(list(map(lambda x: chr(int(x, 16)), declaration[-4:])))
  return compile_custom_pattern(pattern).match(name)

"""
Filter a list of method declarations to only
keep declarations that match the name pattern
"""
def filter_declarations(declarations, pattern):
  return list(filter(lambda x: is_declaration_matching(x, pattern), declarations))

"""
Main entry point of the program
"""
def main(args):
  # Has to have three args
  if len(args) != 3:
    print('Usage: acpiproxy.py <Pattern> <Path-To-OC-Folder> <Path-To-DSDT.aml>')
    sys.exit()

  # Destructure args into separate variables
  pattern, oc, dsdt = args

  # Pattern has to be valid
  if not re.compile('[A-Z0-9_+!\-@?*]{4}').match(pattern):
    print('Invalid pattern provided! Only use: A-Z,0-9,_,+,!,-,@,?,* exactly four times!')
    sys.exit()

  # OC has to be a valid OpenCore folder
  if not validate_oc_folder(oc):
    print('Please provide a valid OpenCore folder location!')
    sys.exit()

  # DSDT has to be a valid file
  if not os.path.exists(dsdt):
    print('Please provide a valid DSDT.aml!')
    sys.exit()

  # Make sure iasl is in $PATH
  if not tool_exists('iasl'):
    print('Please install "iasl" in your PATH!')
    sys.exit()

  # Find method declarations
  declarations = find_method_declarations(dsdt)

  # Filter based on input mask
  declarations = filter_declarations(declarations, pattern)

  # Debug print
  for x in declarations:
    print(''.join([chr(int(c, 16)) for c in x[-4:]]) + ' (' + ''.join(x) + ')')

# Invoke main function with cli args
if __name__ == '__main__':
  main(sys.argv[1:])